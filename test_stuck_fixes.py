#!/usr/bin/env python3
"""
Test the stuck robot fixes with focused training and analysis.
This script runs training with the enhanced stuck detection and recovery system.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from warehouse import Warehouse
import argparse
import time

def test_stuck_robot_fixes(episodes=500, robots=2, analyze=True):
    """Test the stuck robot fixes with detailed analysis"""
    
    print(f"🤖 Testing stuck robot fixes with {robots} robots for {episodes} episodes")
    print("=" * 60)
    
    # Initialize model properly
    params = {'W': 20, 'H': 20, 'n_robots': robots}
    model = Warehouse(parameters=params)
    model.setup()
    
    # Configure for episodic training
    model.training_mode = True
    model.box_respawn_enabled = False
    
    # Robots are already created by setup(), just configure them
    for i, robot in enumerate(model.robots):
        robot.set_robot_id(i)
    
    # Training metrics
    episode_results = []
    win_rates = []
    stuck_recoveries = []
    mission_resets = []
    
    for episode in range(episodes):
        # Reset episode
        model.setup_episode_based_training()
        
        # Episode metrics
        episode_stuck_count = 0
        episode_mission_resets = 0
        episode_deliveries = 0
        steps_in_episode = 0
        
        # Track robot progress
        robot_progress = {robot.id: {'last_pos': robot.position, 'stuck_count': 0} for robot in model.robots}
        
        # Run episode
        max_steps = 100  # Prevent infinite episodes
        for step in range(max_steps):
            model.step()
            steps_in_episode += 1
            
            # Check for stuck robots and recoveries
            for robot in model.robots:
                if hasattr(robot, 'stuck_timer') and robot.stuck_timer > 0:
                    episode_stuck_count += 1
                
                if hasattr(robot, 'mission') and robot.mission is None:
                    # Check if this is a forced mission reset
                    if robot_progress[robot.id]['stuck_count'] > 0:
                        episode_mission_resets += 1
                
                # Track progress
                if robot.position != robot_progress[robot.id]['last_pos']:
                    robot_progress[robot.id]['last_pos'] = robot.position
                    robot_progress[robot.id]['stuck_count'] = 0
                else:
                    robot_progress[robot.id]['stuck_count'] += 1
            
            # Check episode termination
            if getattr(model, 'episode_terminated', False):
                episode_deliveries = model.episode_delivery_count
                break
            
            # Force termination if taking too long
            if step >= max_steps - 1:
                episode_deliveries = model.episode_delivery_count
                print(f"Episode {episode} timeout after {max_steps} steps")
        
        # Calculate win rate (all robots delivered at least 1 box)
        win = (episode_deliveries >= robots)
        win_rates.append(1 if win else 0)
        
        # Store episode results
        episode_results.append({
            'episode': episode,
            'win': win,
            'deliveries': episode_deliveries,
            'steps': steps_in_episode,
            'stuck_recoveries': episode_stuck_count,
            'mission_resets': episode_mission_resets,
            'avg_epsilon': model.global_epsilon
        })
        
        stuck_recoveries.append(episode_stuck_count)
        mission_resets.append(episode_mission_resets)
        
        # Progress reporting
        if (episode + 1) % 50 == 0:
            recent_win_rate = np.mean(win_rates[-50:]) * 100
            recent_stuck = np.mean(stuck_recoveries[-50:])
            recent_resets = np.mean(mission_resets[-50:])
            print(f"Episode {episode + 1:3d}: Win Rate: {recent_win_rate:.1f}% | "
                  f"Avg Stuck/Episode: {recent_stuck:.1f} | "
                  f"Avg Resets/Episode: {recent_resets:.1f} | "
                  f"Epsilon: {model.global_epsilon:.3f}")
    
    # Final analysis
    overall_win_rate = np.mean(win_rates) * 100
    final_50_win_rate = np.mean(win_rates[-50:]) * 100 if len(win_rates) >= 50 else overall_win_rate
    
    print("\n" + "=" * 60)
    print("🎯 STUCK ROBOT FIXES TEST RESULTS")
    print("=" * 60)
    print(f"Overall Win Rate: {overall_win_rate:.1f}%")
    print(f"Final 50 Episodes Win Rate: {final_50_win_rate:.1f}%")
    print(f"Total Stuck Recoveries: {sum(stuck_recoveries)}")
    print(f"Total Mission Resets: {sum(mission_resets)}")
    print(f"Average Steps per Episode: {np.mean([r['steps'] for r in episode_results]):.1f}")
    
    # Create analysis DataFrame
    df = pd.DataFrame(episode_results)
    
    if analyze:
        # Generate analysis plots
        create_stuck_fixes_analysis_plots(df, win_rates, stuck_recoveries, mission_resets)
    
    return df, overall_win_rate, final_50_win_rate

def create_stuck_fixes_analysis_plots(df, win_rates, stuck_recoveries, mission_resets):
    """Create comprehensive analysis plots for stuck robot fixes"""
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Stuck Robot Fixes Analysis', fontsize=16, fontweight='bold')
    
    # 1. Win Rate Over Time
    ax1 = axes[0, 0]
    episodes = range(len(win_rates))
    
    # Rolling average win rate
    window = 25
    rolling_win_rate = pd.Series(win_rates).rolling(window=window, min_periods=1).mean() * 100
    
    ax1.plot(episodes, rolling_win_rate, 'b-', linewidth=2, label=f'Rolling Win Rate ({window} episodes)')
    ax1.axhline(y=np.mean(win_rates) * 100, color='r', linestyle='--', alpha=0.7, label=f'Overall Average ({np.mean(win_rates)*100:.1f}%)')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Win Rate (%)')
    ax1.set_title('Win Rate Over Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Stuck Recoveries Over Time
    ax2 = axes[0, 1]
    rolling_stuck = pd.Series(stuck_recoveries).rolling(window=window, min_periods=1).mean()
    ax2.plot(episodes, rolling_stuck, 'orange', linewidth=2, label=f'Rolling Avg Stuck Recoveries')
    ax2.axhline(y=np.mean(stuck_recoveries), color='red', linestyle='--', alpha=0.7, label=f'Overall Average ({np.mean(stuck_recoveries):.1f})')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Stuck Recoveries per Episode')
    ax2.set_title('Stuck Recovery Interventions')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Mission Resets Over Time
    ax3 = axes[0, 2]
    rolling_resets = pd.Series(mission_resets).rolling(window=window, min_periods=1).mean()
    ax3.plot(episodes, rolling_resets, 'purple', linewidth=2, label=f'Rolling Avg Mission Resets')
    ax3.axhline(y=np.mean(mission_resets), color='red', linestyle='--', alpha=0.7, label=f'Overall Average ({np.mean(mission_resets):.1f})')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Mission Resets per Episode')
    ax3.set_title('Mission Reset Interventions')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. Episode Length Distribution
    ax4 = axes[1, 0]
    episode_lengths = df['steps'].values
    ax4.hist(episode_lengths, bins=20, alpha=0.7, color='green', edgecolor='black')
    ax4.axvline(x=np.mean(episode_lengths), color='red', linestyle='--', linewidth=2, label=f'Average ({np.mean(episode_lengths):.1f} steps)')
    ax4.set_xlabel('Steps per Episode')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Episode Length Distribution')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. Win Rate vs Interventions Correlation
    ax5 = axes[1, 1]
    interventions = np.array(stuck_recoveries) + np.array(mission_resets)
    win_binary = np.array(win_rates)
    
    # Create bins for interventions
    max_interventions = max(interventions) if len(interventions) > 0 else 1
    bins = np.arange(0, max_interventions + 2)
    
    win_rates_by_interventions = []
    intervention_counts = []
    
    for i in range(len(bins) - 1):
        mask = (interventions >= bins[i]) & (interventions < bins[i + 1])
        if np.sum(mask) > 0:
            win_rates_by_interventions.append(np.mean(win_binary[mask]) * 100)
            intervention_counts.append(np.sum(mask))
        else:
            win_rates_by_interventions.append(0)
            intervention_counts.append(0)
    
    bin_centers = (bins[:-1] + bins[1:]) / 2
    ax5.bar(bin_centers, win_rates_by_interventions, alpha=0.7, color='skyblue', edgecolor='black')
    ax5.set_xlabel('Interventions per Episode')
    ax5.set_ylabel('Win Rate (%)')
    ax5.set_title('Win Rate vs Stuck Interventions')
    ax5.grid(True, alpha=0.3)
    
    # 6. Improvement Over Time (Compare early vs late episodes)
    ax6 = axes[1, 2]
    
    # Split into phases
    phase_size = len(win_rates) // 4
    phases = ['Early\n(0-25%)', 'Mid-Early\n(25-50%)', 'Mid-Late\n(50-75%)', 'Late\n(75-100%)']
    phase_win_rates = []
    phase_stuck_rates = []
    
    for i in range(4):
        start_idx = i * phase_size
        end_idx = (i + 1) * phase_size if i < 3 else len(win_rates)
        
        phase_win_rates.append(np.mean(win_rates[start_idx:end_idx]) * 100)
        phase_stuck_rates.append(np.mean(stuck_recoveries[start_idx:end_idx]))
    
    x = np.arange(len(phases))
    width = 0.35
    
    bars1 = ax6.bar(x - width/2, phase_win_rates, width, label='Win Rate (%)', color='lightgreen', alpha=0.8)
    bars2 = ax6.bar(x + width/2, [s * 10 for s in phase_stuck_rates], width, label='Stuck Rate (×10)', color='lightcoral', alpha=0.8)
    
    ax6.set_xlabel('Training Phase')
    ax6.set_ylabel('Rate')
    ax6.set_title('Performance by Training Phase')
    ax6.set_xticks(x)
    ax6.set_xticklabels(phases)
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('stuck_fixes_analysis.png', dpi=150, bbox_inches='tight')
    print(f"📊 Analysis plots saved as 'stuck_fixes_analysis.png'")
    
    return fig

def compare_with_baseline(episodes=500, robots=2):
    """Compare stuck fixes performance with baseline (if available)"""
    
    # Try to load baseline metrics if available
    baseline_file = 'metrics_out/metrics.csv'
    try:
        baseline_df = pd.read_csv(baseline_file)
        baseline_win_rate = baseline_df['win_rate'].iloc[-1] if 'win_rate' in baseline_df.columns else None
        
        if baseline_win_rate is not None:
            print(f"\n📈 COMPARISON WITH BASELINE")
            print("=" * 40)
            print(f"Baseline Win Rate: {baseline_win_rate:.1f}%")
            
            # Run test with fixes
            _, _, final_win_rate = test_stuck_robot_fixes(episodes, robots, analyze=False)
            
            improvement = final_win_rate - baseline_win_rate
            print(f"With Stuck Fixes: {final_win_rate:.1f}%")
            print(f"Improvement: {improvement:+.1f} percentage points")
            
            if improvement > 0:
                print("✅ Stuck robot fixes IMPROVED performance!")
            else:
                print("❌ Stuck robot fixes did not improve performance")
                
            return improvement
        else:
            print("⚠️  No baseline win_rate found in metrics file")
            return None
            
    except FileNotFoundError:
        print("⚠️  No baseline metrics file found, running standalone test")
        test_stuck_robot_fixes(episodes, robots)
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test stuck robot fixes')
    parser.add_argument('--episodes', type=int, default=500, help='Number of episodes to run')
    parser.add_argument('--robots', type=int, default=2, help='Number of robots')
    parser.add_argument('--compare', action='store_true', help='Compare with baseline performance')
    
    args = parser.parse_args()
    
    print("🚀 STUCK ROBOT FIXES TEST")
    print("=" * 50)
    
    if args.compare:
        compare_with_baseline(args.episodes, args.robots)
    else:
        test_stuck_robot_fixes(args.episodes, args.robots)