#!/usr/bin/env python3
"""
Training script for warehouse Q-learning model
"""

import argparse
import os
import sys
import time
import json
import csv
import numpy as np
import matplotlib.pyplot as plt
from warehouse import train_model, run_simulation, Warehouse, EPSILON_END, DECAY_STEPS, EPSILON_TAU, EPSILON_START

# ----------------------- Helpers (plot/stat) -----------------------
def rolling_mean(vals, w):
    if not vals or w <= 1:
        return []
    w = max(1, int(w))
    c = np.cumsum([0.0] + list(vals))
    return [(c[i] - c[i-w]) / w for i in range(w, len(vals)+1)]

def ema(series: np.ndarray, alpha: float) -> np.ndarray:
    if series.size == 0:
        return np.array([], dtype=float)
    out = np.empty_like(series, dtype=float)
    out[0] = series[0]
    for i in range(1, series.size):
        out[i] = alpha * series[i] + (1 - alpha) * out[i - 1]
    return out

def plot_metrics_from_files(out_dir: str, save_path: str = None, show: bool = False):
    """Plot training/eval charts from exported CSV metrics.
    Reads:
      - per_step.csv: step, reward, td_error, success_gt0, delivered, bumps, forced_waits
      - per_episode.csv: episode, total_reward, deliveries
    """
    try:
        step_csv = os.path.join(out_dir, "per_step.csv")
        epi_csv = os.path.join(out_dir, "per_episode.csv")

        # Load per-step
        steps, rewards, tds, succ, deliv = [], [], [], [], []
        bumps, fwaits = [], []
        with open(step_csv, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                steps.append(int(row["step"]))
                rewards.append(float(row["reward"]) if row["reward"] != "" else 0.0)
                tds.append(float(row["td_error"]) if row["td_error"] != "" else 0.0)
                succ.append(int(row["success_gt0"]) if row["success_gt0"] != "" else 0)
                deliv.append(int(row["delivered"]) if row["delivered"] != "" else 0)
                bumps.append(int(row.get("bumps", 0)) if row.get("bumps", "") != "" else 0)
                fwaits.append(int(row.get("forced_waits", 0)) if row.get("forced_waits", "") != "" else 0)

        # Load per-episode
        epis, epi_rewards, epi_deliv = [], [], []
        if os.path.exists(epi_csv):
            with open(epi_csv, newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    epis.append(int(row["episode"]))
                    epi_rewards.append(float(row["total_reward"]))
                    if "deliveries" in row and row["deliveries"] != "":
                        epi_deliv.append(int(row["deliveries"]))

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # Reward per step (thin raw + smoothed overlay)
        if rewards:
            ax1.plot(steps, rewards, alpha=0.25, lw=0.7, color="#666666", label="raw")
            ax1.set_title("Reward per Step")
            ax1.set_xlabel("Step")
            ax1.set_ylabel("Reward")
            ax1.grid(True)
            w1 = max(100, len(rewards)//20)
            rma1 = rolling_mean(rewards, w1)
            if rma1:
                ax1.plot(range(w1, len(rewards)+1), rma1, lw=2.0, color="#1f77b4", label=f"Rolling mean ({w1})")
            ax1.legend()

        # (rolling_mean now shared)

        # Deliveries per episode (use exact exported numbers if available)
        if epi_deliv:
            ax2.plot(range(1, len(epi_deliv) + 1), epi_deliv, alpha=0.7, label="Deliveries/episode")
            w2 = max(3, len(epi_deliv) // 3)
            rma2 = rolling_mean(epi_deliv, w2)
            if rma2:
                ax2.plot(range(w2, len(epi_deliv) + 1), rma2, lw=2.0, label=f"Rolling avg ({w2})")
            ax2.set_title("Deliveries per Episode")
            ax2.set_xlabel("Episode")
            ax2.set_ylabel("Deliveries")
            ax2.legend()
            ax2.grid(True)
        elif tds:
            ax2.plot(steps, tds)
            ax2.set_title("TD Error per Step")
            ax2.set_xlabel("Step")
            ax2.set_ylabel("TD Error")
            ax2.grid(True)

        # Total Reward per Episode with rolling avg
        if epi_rewards:
            ax3.plot(epis, epi_rewards, alpha=0.6, label="Episode reward")
            w = max(3, len(epi_rewards) // 3)
            rma = rolling_mean(epi_rewards, w)
            if rma:
                ax3.plot(range(w, len(epi_rewards) + 1), rma, lw=2.0, label=f"Rolling avg ({w})")
            ax3.set_title("Total Reward per Episode")
            ax3.set_xlabel("Episode")
            ax3.set_ylabel("Total Reward")
            ax3.legend()
            ax3.grid(True)

        # Epsilon curve + Delivery-based win rate and success proxy
        if steps:
            tau = float(EPSILON_TAU) if EPSILON_TAU else max(1.0, DECAY_STEPS / 4.0)
            eps_x = steps[::max(1, len(steps) // 200)]
            eps_y = [float(EPSILON_END + (EPSILON_START - EPSILON_END) * np.exp(-s / tau)) for s in eps_x]
            if eps_y:
                ax4.plot(eps_x, eps_y, label="Epsilon")

        if deliv:
            d = np.array(deliv, dtype=float)
            alpha = 0.02 if d.size >= 1000 else 0.05
            d_ema = ema(d, alpha)
            ax4.plot(range(1, len(d_ema) + 1), d_ema, color="#1f77b4", lw=2.0, label=f"Delivery EMA (α={alpha:.02f})")
            cum = np.cumsum(d)
            denom = np.maximum(1, np.arange(1, d.size + 1))
            cum_rate = cum / denom
            ax4.plot(range(1, len(cum_rate) + 1), cum_rate, color="#2ca02c", lw=2.0, alpha=0.6, label="Delivery cumulative")

        if succ:
            arr = np.array(succ, dtype=float)
            window = min(800, max(50, len(arr) // 8))
            if len(arr) >= max(10, window // 2):
                kernel = np.ones(window) / window
                roll = np.convolve(arr, kernel, mode='valid')
                ax4.plot(range(window, window + len(roll)), roll, color="#ff7f0e", lw=1.0, ls=":", alpha=0.3, label=f"Reward>0% ({window}-step)")

        # Metrics: bumps and forced waits per 1k steps (smoothed) on twin axis
        ax4b = ax4.twinx()
        if bumps or fwaits:
            def per_k(series, k=1000):
                if not series:
                    return []
                arr = np.array(series, dtype=float)
                # moving sum over k, then per-k rate
                wlen = min(k, max(10, len(arr)//10))
                ker = np.ones(wlen)
                mov = np.convolve(arr, ker, mode='valid')
                return (mov / wlen) * k
            bpk = per_k(bumps)
            fwk = per_k(fwaits)
            if len(bpk) > 0:
                ax4b.plot(range(1, len(bpk)+1), bpk, color="#d62728", lw=1.0, alpha=0.8, label="bumps/1k (smoothed)")
            if len(fwk) > 0:
                ax4b.plot(range(1, len(fwk)+1), fwk, color="#9467bd", lw=1.0, alpha=0.8, label="forced_waits/1k (smoothed)")
            ax4b.set_ylabel("per 1k steps")

        ax4.set_ylim(0, 1)
        ax4.set_title("Epsilon, Delivery, and Congestion Signals")
        ax4.set_xlabel("Step")
        ax4.set_ylabel("Value")
        # Merge legends from both axes
        lines1, labels1 = ax4.get_legend_handles_labels()
        lines2, labels2 = ax4b.get_legend_handles_labels()
        ax4.legend(lines1 + lines2, labels1 + labels2, loc="best")
        ax4.grid(True)

        plt.tight_layout()
        out_png = save_path or os.path.join(out_dir, "training_results.png")
        plt.savefig(out_png, dpi=300, bbox_inches='tight')
        if show:
            plt.show()
        else:
            plt.close(fig)
        print(f"Charts saved to {out_png}")

    except Exception as e:
        print(f"Error plotting from CSV: {e}")

def print_training_summary(model):
    """Print comprehensive training summary"""
    stats = model._stats
    
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    
    print(f"Total Steps: {stats['step']}")
    print(f"Total Episodes: {stats.get('episodes', 'N/A')}")
    print(f"Final Epsilon: {model.global_epsilon:.4f}")
    
    print(f"\nPerformance Metrics:")
    print(f"  Total Deliveries: {stats['deliveries']}")
    print(f"  Total Pickups: {stats['pickups']}")
    print(f"  Total Conflicts: {stats['conflicts']}")
    print(f"  Total Moves: {stats['moves']}")
    print(f"  Total Waits: {stats['waits']}")
    print(f"  Total Recharges: {stats['recharges']}")
    # Diagnostics
    if 'pickup_opportunities' in stats:
        print(f"  Pickup Opportunities: {stats['pickup_opportunities']}  Missed: {stats['pickup_missed']}")
    if 'drop_opportunities' in stats:
        print(f"  Drop Opportunities:   {stats['drop_opportunities']}  Missed: {stats['drop_missed']}")
    
    if stats['deliveries'] > 0:
        print(f"  Delivery Rate: {stats['deliveries']/stats['step']*100:.2f}%")
    
    if len(stats['reward_hist']) > 0:
        recent_rewards = stats['reward_hist'][-1000:] if len(stats['reward_hist']) >= 1000 else stats['reward_hist']
        print(f"\nReward Statistics:")
        print(f"  Average Reward (recent): {np.mean(recent_rewards):.4f}")
        print(f"  Total Reward: {sum(stats['reward_hist']):.2f}")
        print(f"  Best Reward: {max(stats['reward_hist']):.4f}")
        print(f"  Worst Reward: {min(stats['reward_hist']):.4f}")
    
    if len(stats['episode_rewards']) > 0:
        print(f"\nEpisode Statistics:")
        print(f"  Average Episode Reward: {np.mean(stats['episode_rewards']):.2f}")
        print(f"  Best Episode: {max(stats['episode_rewards']):.2f}")
        print(f"  Recent Episodes Avg: {np.mean(stats['episode_rewards'][-10:]):.2f}")
    
    print("\nRobot Status:")
    for robot in model.robots:
        print(f"  Robot {robot.id}: {robot.mission or 'IDLE'} | "
              f"Battery: {robot.battery:.0f}% | "
              f"Position: {robot.position} | "
              f"Carrying: {robot.carrying}")
    
    print("="*60)

def export_metrics(model, out_dir: str):
    """Export metrics to JSON and CSV files."""
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass

    stats = model._stats if hasattr(model, "_stats") else getattr(model, "stats", {})
    # Summary JSON
    summary = {
        "total_steps": int(stats.get("step", 0)),
        "episodes": int(stats.get("episodes", 0)),
        "final_epsilon": float(getattr(model, "global_epsilon", stats.get("epsilon", 0.0))),
        "totals": {
            k: int(stats.get(k, 0)) for k in [
                "deliveries","pickups","conflicts","moves","waits","recharges",
                "pickup_opportunities","pickup_missed","drop_opportunities","drop_missed",
                "bumps","forced_waits"
            ] if k in stats
        },
        "total_reward_all": float(stats.get("total_reward_all", sum(stats.get("reward_hist", []))))
    }
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Per-episode CSV
    episodes = stats.get("episode_rewards", []) or []
    deliveries_per_episode = stats.get("deliveries_per_episode", []) or []
    success_hist = stats.get("episode_success_history", []) or []
    with open(os.path.join(out_dir, "per_episode.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # Add success flag column if episodic training present
        header = ["episode", "total_reward", "deliveries"]
        if success_hist:
            header.append("success")
        w.writerow(header)
        for i, r in enumerate(episodes, start=1):
            d = int(deliveries_per_episode[i-1]) if i-1 < len(deliveries_per_episode) else ""
            row = [i, float(r), d]
            if success_hist:
                s = int(success_hist[i-1]) if i-1 < len(success_hist) else ""
                row.append(s)
            w.writerow(row)

    # Separate success CSV for direct plotting if desired
    if success_hist:
        try:
            with open(os.path.join(out_dir, "episode_success.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["episode", "success"])
                for i, s in enumerate(success_hist, start=1):
                    w.writerow([i, int(s)])
        except Exception as e:
            print(f"Warning: could not write episode_success.csv: {e}")

    # Per-step CSV (aggregated histories after training)
    reward_hist = stats.get("reward_hist", []) or []
    td_hist = stats.get("td_hist", []) or []
    succ_hist = stats.get("success_hist", []) or []
    deliv_hist = stats.get("delivery_hist", []) or []
    bump_hist = stats.get("bump_hist", []) or []
    forced_wait_hist = stats.get("forced_wait_hist", []) or []
    n = max(len(reward_hist), len(td_hist), len(succ_hist), len(deliv_hist), len(bump_hist), len(forced_wait_hist))
    with open(os.path.join(out_dir, "per_step.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["step", "reward", "td_error", "success_gt0", "delivered", "bumps", "forced_waits"])
        for i in range(n):
            w.writerow([
                i+1,
                float(reward_hist[i]) if i < len(reward_hist) else "",
                float(td_hist[i]) if i < len(td_hist) else "",
                int(succ_hist[i]) if i < len(succ_hist) else "",
                int(deliv_hist[i]) if i < len(deliv_hist) else "",
                int(bump_hist[i]) if i < len(bump_hist) else "",
                int(forced_wait_hist[i]) if i < len(forced_wait_hist) else "",
            ])

    print(f"Exported metrics to {out_dir}")

def main():
    parser = argparse.ArgumentParser(description="Warehouse Q-Learning Training")
    parser.add_argument("command", choices=["train", "test", "visualize", "eval"], 
                       help="Command to execute")
    parser.add_argument("--episodes", type=int, default=1000,
                       help="Number of training episodes (default: 1000)")
    parser.add_argument("--steps", type=int, default=1000,
                       help="Number of steps for test/visualize (default: 1000)")
    parser.add_argument("--config", default="layout.json",
                       help="Path to configuration file (default: layout.json)")
    parser.add_argument("--save-every", type=int, default=100,
                       help="Save weights every N episodes (default: 100)")
    parser.add_argument("--no-pretrain", action="store_true",
                       help="Don't use pretrained weights")
    parser.add_argument("--plot", action="store_true",
                       help="Generate training plots")
    parser.add_argument("--export-metrics", default=None,
                       help="Directory to export metrics (JSON/CSV)")
    parser.add_argument("--fps", type=int, default=10,
                       help="FPS for visualization (default: 10)")
    parser.add_argument("--cell-size", type=int, default=30,
                       help="Cell size for visualization (default: 30)")
    parser.add_argument("--epsilon", type=float, default=None,
                       help="Override epsilon during visualization (default: use EPSILON_END)")
    parser.add_argument("--episodic", action="store_true",
                        help="Use episode-based training with success tracking")
    parser.add_argument("--single-robot", action="store_true",
                        help="Train with single robot only (episodic mode)")
    parser.add_argument("--two-robots", action="store_true",
                        help="Train with two robots only (episodic mode)")
    parser.add_argument("--progressive", action="store_true",
                        help="Run progressive multi-phase training strategy")
    parser.add_argument("--n-robots", type=int, default=None,
                        help="Restrict simulation to first N robots (visualize/test/eval); also sets cycle target to N for auto resets")
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        print(f"Error: Configuration file '{args.config}' not found.")
        sys.exit(1)
    
    # Set global flags
    import warehouse
    if args.no_pretrain:
        warehouse.PRETRAIN_ENABLED = False
    
    print(f"Using configuration: {args.config}")
    print(f"Pretrained weights: {'Enabled' if warehouse.PRETRAIN_ENABLED else 'Disabled'}")
    
    if args.command == "train":
        start_time = time.time()
        if args.progressive:
            from warehouse import progressive_training_strategy
            final_model, _ = progressive_training_strategy()
            model = final_model
        elif args.episodic or args.single_robot or args.two_robots:
            if args.single_robot:
                from warehouse import train_single_robot
                model, _ = train_single_robot(episodes=args.episodes)
            elif args.two_robots:
                from warehouse import train_two_robots
                model, _ = train_two_robots(episodes=args.episodes)
            else:
                from warehouse import train_model_episodic
                model, _ = train_model_episodic(episodes=args.episodes, n_robots=args.n_robots)
        else:
            print(f"Starting (legacy wrapper -> episodic) training for {args.episodes} episodes...")
            model, _ = train_model(
                episodes=args.episodes,
                steps_per_episode=200,
                config_path=args.config,
                save_every=args.save_every
            )
        end_time = time.time()
        print(f"Training completed in {end_time - start_time:.2f} seconds")

        print_training_summary(model)

        if args.export_metrics:
            export_metrics(model, args.export_metrics)
        if args.plot:
            if args.export_metrics:
                plot_metrics_from_files(args.export_metrics, show=False)
            else:
                print("Tip: Use --export-metrics <dir> to enable CSV-based plotting.")
    
    elif args.command == "test":
        print(f"Running test simulation for {args.steps} steps...")
        
        model = run_simulation(
            steps=args.steps,
            config_path=args.config,
            visualize=False
        )
        # Restrict robot count if requested
        if args.n_robots is not None and args.n_robots > 0:
            if len(model.robots) > args.n_robots:
                model.robots = model.robots[:args.n_robots]
            try:
                model.set_cycle_target(args.n_robots)
            except Exception:
                pass
        # Optional epsilon override for testing (persistent)
        if args.epsilon is not None:
            model.epsilon_override = float(args.epsilon)
        else:
            model.epsilon_override = float(EPSILON_END)
        
        print_training_summary(model)
        if args.export_metrics:
            export_metrics(model, args.export_metrics)
        if args.plot:
            if args.export_metrics:
                plot_metrics_from_files(args.export_metrics, show=False)
            else:
                print("Tip: Use --export-metrics <dir> to enable CSV-based plotting.")
    
    elif args.command == "visualize":
        print(f"Starting visualization for {args.steps} steps...")
        print("Controls: SPACE=Pause, S=Step, R=Reset, Q=Quit, +/-=Speed")
        
        try:
            from visualize import WarehouseVisualizer
            
            params = {'config_path': args.config}
            model = Warehouse(parameters=params)
            # Ensure the model is initialized before visualization
            model.setup()
            # ENABLE box respawning for visualization/simulation mode
            model.training_mode = False
            model.box_respawn_enabled = True
            # If user requested a specific number of robots, trim and adapt cycle target
            if args.n_robots is not None and args.n_robots > 0:
                if len(model.robots) > args.n_robots:
                    model.robots = model.robots[:args.n_robots]
                try:
                    model.set_cycle_target(args.n_robots)
                except Exception:
                    pass
            # Reset cycles automatically during visualization to show repeated runs of 4 deliveries
            try:
                model.auto_cycle_reset = True
            except Exception:
                pass
            
            # Load best available weights for a trained policy
            candidates = [
                os.path.join("weights", "W_linear_best.npy"),
                os.path.join("weights", "W_linear.npy"),
                "W_linear_best.npy",
                "W_linear.npy",
            ]
            loaded = False
            for path in candidates:
                if os.path.exists(path) and model.load_weights(path):
                    loaded = True
                    break
            
            # Force low epsilon for evaluation-style visualization
            eval_eps = args.epsilon if args.epsilon is not None else EPSILON_END
            model.epsilon_override = float(eval_eps)
            
            # Calculate interval from FPS
            interval = int(1000 / args.fps)  # Convert FPS to milliseconds
            
            visualizer = WarehouseVisualizer(model, interval=interval)
            visualizer.run(max_steps=args.steps)
            
        except ImportError as e:
            print(f"Error: {e}")
            print("Make sure matplotlib is installed: pip install matplotlib")
            sys.exit(1)
        except Exception as e:
            print(f"Visualization error: {e}")
            sys.exit(1)
    
    elif args.command == "eval":
        print(f"Running evaluation for {args.steps} steps...")
        params = {'config_path': args.config}
        model = Warehouse(parameters=params)
        model.setup()
        if args.n_robots is not None and args.n_robots > 0 and len(model.robots) > args.n_robots:
            model.robots = model.robots[:args.n_robots]
            try:
                model.set_cycle_target(args.n_robots)
            except Exception:
                pass
        try:
            model.auto_cycle_reset = True
        except Exception:
            pass
        # Load best available weights
        candidates = [
            os.path.join("weights", "W_linear_best.npy"),
            os.path.join("weights", "W_linear.npy"),
            "W_linear_best.npy",
            "W_linear.npy",
        ]
        for path in candidates:
            if os.path.exists(path) and model.load_weights(path):
                break
        # Low epsilon for evaluation (persistent override)
        eval_eps = args.epsilon if args.epsilon is not None else EPSILON_END
        model.epsilon_override = float(eval_eps)
        # Run
        for _ in range(args.steps):
            model.step()
        print_training_summary(model)
        if args.export_metrics:
            export_metrics(model, args.export_metrics)
        if args.plot:
            if args.export_metrics:
                plot_metrics_from_files(args.export_metrics, show=False)
            else:
                print("Tip: Use --export-metrics <dir> to enable CSV-based plotting.")

if __name__ == "__main__":
    main()