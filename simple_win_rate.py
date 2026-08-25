#!/usr/bin/env python3
"""
Simple win rate graph generator
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def create_win_rate_graph(metrics_dir="metrics_out", output_file="training_win_rate.png"):
    """Create a clean win rate progression graph"""
    
    # Load data
    per_episode_file = os.path.join(metrics_dir, "per_episode.csv")
    if not os.path.exists(per_episode_file):
        print(f"Error: Training data not found at {per_episode_file}")
        return
    
    df = pd.read_csv(per_episode_file)
    episodes = df['episode'].values
    success = df['success'].values
    
    # Calculate rolling averages with different window sizes
    rolling_10 = pd.Series(success).rolling(window=10, min_periods=1).mean()
    rolling_50 = pd.Series(success).rolling(window=50, min_periods=1).mean()
    rolling_100 = pd.Series(success).rolling(window=100, min_periods=1).mean()
    
    # Create the plot
    plt.figure(figsize=(14, 8))
    
    # Individual episodes (very faded background)
    plt.scatter(episodes, success, alpha=0.1, s=0.5, color='gray', label='Individual Episodes')
    
    # Rolling averages
    plt.plot(episodes, rolling_10, alpha=0.5, color='lightblue', linewidth=1, label='10-Episode Average')
    plt.plot(episodes, rolling_50, color='blue', linewidth=2, label='50-Episode Average')
    plt.plot(episodes, rolling_100, color='darkblue', linewidth=3, label='100-Episode Average')
    
    # Overall average line
    overall_avg = np.mean(success)
    plt.axhline(y=overall_avg, color='red', linestyle='--', alpha=0.8,
                linewidth=2, label=f'Overall Average: {overall_avg:.1%}')
    
    # Formatting
    plt.xlabel('Training Episode', fontsize=14, fontweight='bold')
    plt.ylabel('Win Rate (Team Success Rate)', fontsize=14, fontweight='bold')
    plt.title('Warehouse Robot Training: Win Rate Progression\n' + 
              'Success = All Robots Complete Their Box Delivery', 
              fontsize=16, fontweight='bold', pad=20)
    
    plt.grid(True, alpha=0.3)
    plt.legend(loc='lower right', fontsize=12)
    
    # Format y-axis as percentages
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    plt.ylim(-0.02, 1.02)
    
    # Add final performance box
    final_win_rate = rolling_100.iloc[-1]
    best_win_rate = rolling_100.max()
    
    stats_text = f"""Final Performance:
Win Rate: {final_win_rate:.1%}
Best Rate: {best_win_rate:.1%}
Total Episodes: {len(episodes):,}

Success = ALL robots deliver ≥1 box"""
    
    plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
             verticalalignment='top', fontsize=11,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8))
    
    # Save with high quality
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white')
    plt.show()
    
    print(f"\n🎯 Win Rate Graph Generated!")
    print(f"📊 File saved as: {output_file}")
    print(f"📈 Final win rate: {final_win_rate:.1%}")
    print(f"🏆 Best win rate achieved: {best_win_rate:.1%}")

if __name__ == "__main__":
    create_win_rate_graph()