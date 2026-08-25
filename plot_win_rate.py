#!/usr/bin/env python3
"""
Generate win rate (success rate) graph from training data
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def plot_win_rate(metrics_dir="metrics_out", output_file="win_rate_graph.png", window_size=50):
    """
    Plot win rate progression during training
    
    Args:
        metrics_dir: Directory containing training metrics
        output_file: Output PNG file name
        window_size: Window size for rolling average (default: 50 episodes)
    """
    
    # Load episode success data
    episode_success_file = os.path.join(metrics_dir, "episode_success.csv")
    per_episode_file = os.path.join(metrics_dir, "per_episode.csv")
    
    if not os.path.exists(per_episode_file):
        print(f"Error: {per_episode_file} not found!")
        return
    
    # Load per-episode data
    df = pd.read_csv(per_episode_file)
    episodes = df['episode'].values
    success = df['success'].values
    
    print(f"Loaded {len(episodes)} episodes of training data")
    print(f"Overall win rate: {np.mean(success):.1%}")
    
    # Calculate rolling win rate
    def rolling_win_rate(success_data, window):
        rolling_rates = []
        for i in range(len(success_data)):
            start_idx = max(0, i - window + 1)
            window_data = success_data[start_idx:i+1]
            rolling_rates.append(np.mean(window_data))
        return np.array(rolling_rates)
    
    rolling_success = rolling_win_rate(success, window_size)
    
    # Create the plot
    plt.figure(figsize=(12, 8))
    
    # Plot individual episode results (faded)
    plt.scatter(episodes, success, alpha=0.3, s=1, color='lightblue', label='Individual Episodes')
    
    # Plot rolling average
    plt.plot(episodes, rolling_success, color='red', linewidth=2, 
             label=f'Rolling Win Rate ({window_size} episodes)')
    
    # Add horizontal line for overall average
    overall_avg = np.mean(success)
    plt.axhline(y=overall_avg, color='green', linestyle='--', alpha=0.7,
                label=f'Overall Average: {overall_avg:.1%}')
    
    # Formatting
    plt.xlabel('Episode', fontsize=12)
    plt.ylabel('Win Rate (Success Rate)', fontsize=12)
    plt.title('Training Win Rate Progression\n(Success = All Robots Deliver ≥1 Box)', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Set y-axis to percentage format
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    plt.ylim(-0.05, 1.05)
    
    # Add statistics text box
    stats_text = f"""Training Statistics:
Episodes: {len(episodes):,}
Final Win Rate: {rolling_success[-1]:.1%}
Best Win Rate: {np.max(rolling_success):.1%}
Overall Average: {overall_avg:.1%}"""
    
    plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
             fontsize=10)
    
    # Save the plot
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Win rate graph saved as: {output_file}")
    
    # Show summary statistics by training phases
    print("\n=== Win Rate Analysis ===")
    total_episodes = len(episodes)
    
    # Early training (first 25%)
    early_end = total_episodes // 4
    early_rate = np.mean(success[:early_end])
    print(f"Early Training (Episodes 1-{early_end}): {early_rate:.1%}")
    
    # Mid training (25%-75%)
    mid_start = early_end
    mid_end = 3 * total_episodes // 4
    mid_rate = np.mean(success[mid_start:mid_end])
    print(f"Mid Training (Episodes {mid_start+1}-{mid_end}): {mid_rate:.1%}")
    
    # Late training (last 25%)
    late_start = mid_end
    late_rate = np.mean(success[late_start:])
    print(f"Late Training (Episodes {late_start+1}-{total_episodes}): {late_rate:.1%}")
    
    # Improvement calculation
    improvement = late_rate - early_rate
    print(f"\nOverall Improvement: {improvement:+.1%}")
    
    if improvement > 0:
        print("✅ Training is improving win rate!")
    elif improvement < -0.05:
        print("⚠️  Win rate decreased - possible overfitting")
    else:
        print("➡️  Win rate stabilized")

def plot_detailed_win_rate_analysis(metrics_dir="metrics_out", output_file="detailed_win_rate.png"):
    """Create a more detailed analysis with multiple subplots"""
    
    per_episode_file = os.path.join(metrics_dir, "per_episode.csv")
    if not os.path.exists(per_episode_file):
        print(f"Error: {per_episode_file} not found!")
        return
    
    df = pd.read_csv(per_episode_file)
    episodes = df['episode'].values
    success = df['success'].values
    deliveries = df['deliveries'].values
    rewards = df['total_reward'].values
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. Win Rate over time
    rolling_success = pd.Series(success).rolling(window=50, min_periods=1).mean()
    ax1.plot(episodes, rolling_success, color='red', linewidth=2)
    ax1.fill_between(episodes, rolling_success, alpha=0.3, color='red')
    ax1.set_title('Win Rate Progression', fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Win Rate')
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    
    # 2. Success vs Deliveries
    successful_episodes = deliveries[success == 1]
    failed_episodes = deliveries[success == 0]
    ax2.hist([failed_episodes, successful_episodes], bins=20, alpha=0.7, 
             label=['Failed Episodes', 'Successful Episodes'], color=['red', 'green'])
    ax2.set_title('Deliveries Distribution by Success', fontweight='bold')
    ax2.set_xlabel('Deliveries per Episode')
    ax2.set_ylabel('Frequency')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Reward vs Success
    successful_rewards = rewards[success == 1]
    failed_rewards = rewards[success == 0]
    ax3.scatter(episodes[success == 0], failed_rewards, alpha=0.5, color='red', s=1, label='Failed')
    ax3.scatter(episodes[success == 1], successful_rewards, alpha=0.5, color='green', s=1, label='Successful')
    ax3.set_title('Rewards by Episode Success', fontweight='bold')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Total Reward')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. Win Rate by Training Phase
    phases = ['Early\n(0-25%)', 'Mid-Early\n(25-50%)', 'Mid-Late\n(50-75%)', 'Late\n(75-100%)']
    total_episodes = len(episodes)
    phase_rates = []
    
    for i in range(4):
        start_idx = i * total_episodes // 4
        end_idx = (i + 1) * total_episodes // 4
        phase_rate = np.mean(success[start_idx:end_idx])
        phase_rates.append(phase_rate)
    
    bars = ax4.bar(phases, phase_rates, color=['lightcoral', 'orange', 'lightblue', 'lightgreen'])
    ax4.set_title('Win Rate by Training Phase', fontweight='bold')
    ax4.set_ylabel('Win Rate')
    ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    
    # Add percentage labels on bars
    for bar, rate in zip(bars, phase_rates):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{rate:.1%}', ha='center', va='bottom', fontweight='bold')
    
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.suptitle('Detailed Win Rate Analysis', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Detailed win rate analysis saved as: {output_file}")

if __name__ == "__main__":
    # Generate both graphs
    plot_win_rate()
    plot_detailed_win_rate_analysis()
    print("\n✅ Win rate graphs generated successfully!")