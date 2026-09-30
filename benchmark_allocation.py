#!/usr/bin/env python3
"""Compare task allocation / conflict modes on the same seeded episodes.

Modes:
  baseline          greedy nearest-robot allocation + legacy multi-pass resolver (original)
  greedy+blackboard greedy allocation + blackboard next-cell reservations
  auction+legacy    Contract-Net auction + legacy resolver
  auction           Contract-Net auction + blackboard reservations (full coordination layer)

Every mode runs the same seeds, the same trained weights (weights/W_linear_best.npy)
and epsilon 0.05. Output: docs/benchmark_allocation.{csv,md,png}

Usage:
  python benchmark_allocation.py --episodes 20 --steps 400
"""
import argparse
import contextlib
import csv
import io
import math
import os
import random
import statistics as st
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

MODES = [
    ("baseline", "greedy", "legacy"),
    ("greedy+blackboard", "greedy", "blackboard"),
    ("auction+legacy", "auction", "legacy"),
    ("auction", "auction", "blackboard"),
]

METRICS = [
    ("valid_deliveries", "Entregas válidas / episodio"),
    ("steps_per_delivery", "Ticks por entrega"),
    ("ghost_pickups", "Recogidas fantasma"),
    ("duplicate_assignments", "Misiones duplicadas"),
    ("conflicts", "Esperas forzadas por conflicto"),
    ("collisions", "Colisiones (misma celda)"),
    ("stuck_events", "Eventos de atasco"),
    ("idle_pct", "Tiempo ocioso (%)"),
    ("reauctions", "Re-subastas"),
]


def run_episode(allocation, conflict, seed, steps, weights):
    from warehouse import Warehouse
    random.seed(seed)
    np.random.seed(seed)
    with contextlib.redirect_stdout(io.StringIO()):
        m = Warehouse(parameters={"config_path": os.path.join(ROOT, "layout.json"),
                                  "allocation_mode": allocation, "conflict_mode": conflict})
        m.setup()
        if weights and os.path.exists(weights):
            m.load_weights(weights)
        m.epsilon_override = 0.05
        for _ in range(steps):
            m.step()
    s = m.stats
    n_rob = len(m.robots)
    vd = s["valid_deliveries"]
    return {
        "valid_deliveries": vd,
        "raw_deliveries": s["deliveries"],
        "steps_per_delivery": steps / vd if vd else float("nan"),
        "ghost_pickups": s["ghost_pickups"],
        "duplicate_assignments": s["duplicate_assignments"],
        "conflicts": s["conflicts"],
        "collisions": s["collisions"],
        "swaps_through": s["swaps_through"],
        "stuck_events": s["stuck_events"],
        "idle_pct": 100.0 * s["idle_robot_steps"] / (n_rob * steps),
        "reauctions": m.blackboard.counters["reauctions"],
    }


def mean_ci(values):
    vals = [v for v in values if not math.isnan(v)]
    if not vals:
        return float("nan"), float("nan")
    m = st.mean(vals)
    ci = 1.96 * st.stdev(vals) / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
    return m, ci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--weights", default=os.path.join(ROOT, "weights", "W_linear_best.npy"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--plot-only", action="store_true", help="rebuild table and chart from the CSV")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    rows, results = [], {}
    t0 = time.time()
    csv_path = os.path.join(args.out, "benchmark_allocation.csv")
    if args.plot_only:
        with open(csv_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                r = {k: (v if k == "mode" else float(v)) for k, v in r.items()}
                rows.append(r)
                results.setdefault(r["mode"], []).append(r)
    for name, alloc, conf in ([] if args.plot_only else MODES):
        eps = []
        for i in range(args.episodes):
            r = run_episode(alloc, conf, args.seed0 + i, args.steps, args.weights)
            r.update({"mode": name, "seed": args.seed0 + i})
            rows.append(r)
            eps.append(r)
        results[name] = eps
        m, ci = mean_ci([e["valid_deliveries"] for e in eps])
        print(f"{name:18s} valid deliveries {m:6.2f} ± {ci:.2f}  ({time.time() - t0:.0f}s)", flush=True)

    # CSV (per episode)
    keys = ["mode", "seed", "valid_deliveries", "raw_deliveries", "steps_per_delivery",
            "ghost_pickups", "duplicate_assignments", "conflicts", "collisions", "swaps_through",
            "stuck_events", "idle_pct", "reauctions"]
    if not args.plot_only:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow({k: (round(r[k], 3) if isinstance(r[k], float) else r[k]) for k in keys})
    n_eps = len(results["baseline"])

    # Markdown table (means, 95% CI for deliveries)
    base = st.mean(e["valid_deliveries"] for e in results["baseline"])
    lines = [f"{n_eps} episodios con semilla por modo, {args.steps} ticks, 4 robots, "
             f"pesos `W_linear_best.npy`, epsilon 0.05.", "",
             "| Modo | " + " | ".join(label for _, label in METRICS) + " | vs baseline |",
             "|---|" + "---:|" * (len(METRICS) + 1)]
    for name, _, _ in MODES:
        eps = results[name]
        cells = []
        for key, _ in METRICS:
            m, ci = mean_ci([e[key] for e in eps])
            cells.append(f"{m:.1f} ± {ci:.1f}" if key == "valid_deliveries" else f"{m:.1f}")
        gain = 100.0 * (st.mean(e["valid_deliveries"] for e in eps) - base) / base if base else float("nan")
        cells.append("-" if name == "baseline" else f"{gain:+.0f}%")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    md_path = os.path.join(args.out, "benchmark_allocation.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # Chart
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, ink2, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    gray, blue = "#a9a8a2", "#2a78d6"
    names = [n for n, _, _ in MODES]
    colors = [blue if n == "auction" else gray for n in names]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), facecolor=surface)
    panels = [("valid_deliveries", "Entregas válidas por episodio"),
              ("steps_per_delivery", "Ticks por entrega (menos es mejor)"),
              ("idle_pct", "Tiempo ocioso de robots, % (menos es mejor)")]
    for ax, (key, title) in zip(axes, panels):
        stats = [mean_ci([e[key] for e in results[n]]) for n in names]
        means = [s[0] for s in stats]
        cis = [s[1] for s in stats]
        ax.set_facecolor(surface)
        bars = ax.bar(range(len(names)), means, color=colors, width=0.62,
                      yerr=cis if key == "valid_deliveries" else None,
                      error_kw={"ecolor": ink2, "elinewidth": 1.2, "capsize": 4},
                      edgecolor=surface, linewidth=2)
        for b, m, ci in zip(bars, means, cis):
            top = m + (ci if key == "valid_deliveries" else 0)
            ax.annotate(f"{m:.1f}", (b.get_x() + b.get_width() / 2, top), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=9, color=ink)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels([n.replace("+", "+\n") for n in names], fontsize=8.5, color=ink2)
        ax.set_title(title, fontsize=10.5, color=ink, loc="left")
        ax.tick_params(axis="y", colors=ink2, labelsize=8.5)
        ax.grid(axis="y", color=grid, linewidth=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(grid)
        ax.set_ylim(0, max(m + c for m, c in zip(means, cis)) * 1.15)
    fig.suptitle(f"Asignación de tareas: {n_eps} episodios con semilla x {args.steps} ticks "
                 f"(barras de error = IC 95%)", fontsize=11, color=ink, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    png_path = os.path.join(args.out, "benchmark_allocation.png")
    fig.savefig(png_path, dpi=130, facecolor=surface)
    print(f"\nSaved {csv_path}\nSaved {md_path}\nSaved {png_path}")


if __name__ == "__main__":
    main()
