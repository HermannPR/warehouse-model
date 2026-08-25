#!/usr/bin/env python3
"""
Generate a comprehensive win rate graph from training data
"""

import matplotlib.pyplot as plt
import numpy as np
from warehouse import Warehouse

def generate_win_rate_graph(episodes=300, robots=2):
    """Generate and save a detailed win rate graph from training"""
    
    print(f"🚀 GENERATING WIN RATE TRAINING GRAPH")
    print(f"==================================================")
    print(f"📊 Training {robots} robots for {episodes} episodes")
    print(f"============================================================")
    
    # Initialize tracking
    win_rates = []
    rolling_wins = []
    episode_results = []
    
    # Create model
    model = Warehouse(
        width=25, height=25, 
        n_robots=robots, 
        n_boxes=10, 
        episode_limit=100,
        training_mode=True
    )
    
    # Training loop with detailed tracking
    for episode in range(episodes):
        model.setup()
        
        while model.running:
            model.step()
        
        # Record results
        won = 1 if model.episode_delivery_count >= robots else 0
        episode_results.append(won)
        rolling_wins.append(won)
        
        # Calculate win rate every 10 episodes
        if (episode + 1) % 10 == 0:
            recent_wins = sum(rolling_wins[-50:]) if len(rolling_wins) >= 50 else sum(rolling_wins)
            recent_episodes = min(50, len(rolling_wins))
            win_rate = (recent_wins / recent_episodes) * 100
            win_rates.append(win_rate)
            
            print(f"Episode {episode + 1:3d}: Win Rate: {win_rate:5.1f}% | "
                  f"Deliveries: {model.episode_delivery_count} | "
                  f"Epsilon: {model.robots[0].epsilon:.3f}")
        
        # Reset for next episode
        rolling_wins = rolling_wins[-50:]  # Keep only last 50
    
    # Create comprehensive visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('🤖 Warehouse Robot Training: Win Rate Analysis', fontsize=16, fontweight='bold')
    
    # 1. Win Rate Over Time
    episodes_x = range(10, episodes + 1, 10)
    ax1.plot(episodes_x, win_rates, 'b-', linewidth=2, marker='o', markersize=4)
    ax1.fill_between(episodes_x, win_rates, alpha=0.3)
    ax1.set_title('Win Rate Progress', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Win Rate (%)')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 105)
    
    # Add trend line
    if len(win_rates) > 1:
        z = np.polyfit(episodes_x, win_rates, 1)
        p = np.poly1d(z)
        ax1.plot(episodes_x, p(episodes_x), "r--", alpha=0.8, linewidth=1)
    
    # 2. Rolling Average (different window sizes)
    def rolling_average(data, window):
        return [np.mean(data[max(0, i-window+1):i+1]) for i in range(len(data))]
    
    roll_10 = rolling_average(episode_results, 10)
    roll_25 = rolling_average(episode_results, 25)
    roll_50 = rolling_average(episode_results, 50)
    
    episodes_all = range(1, len(episode_results) + 1)
    ax2.plot(episodes_all, np.array(roll_10) * 100, 'g-', label='10-episode avg', alpha=0.7)
    ax2.plot(episodes_all, np.array(roll_25) * 100, 'b-', label='25-episode avg', alpha=0.8)
    ax2.plot(episodes_all, np.array(roll_50) * 100, 'r-', label='50-episode avg', linewidth=2)
    ax2.set_title('Rolling Win Rate Averages', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Win Rate (%)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 105)
    
    # 3. Win Rate Distribution
    win_rate_bins = np.arange(0, 101, 5)
    ax3.hist(win_rates, bins=win_rate_bins, alpha=0.7, color='skyblue', edgecolor='black')
    ax3.axvline(np.mean(win_rates), color='red', linestyle='--', linewidth=2, 
                label=f'Mean: {np.mean(win_rates):.1f}%')
    ax3.set_title('Win Rate Distribution', fontsize=14, fontweight='bold')
    ax3.set_xlabel('Win Rate (%)')
    ax3.set_ylabel('Frequency')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. Performance Metrics
    final_50_episodes = episode_results[-50:] if len(episode_results) >= 50 else episode_results
    final_win_rate = (sum(final_50_episodes) / len(final_50_episodes)) * 100
    overall_win_rate = (sum(episode_results) / len(episode_results)) * 100
    
    metrics_text = f"""Training Summary:
    
📊 Overall Win Rate: {overall_win_rate:.1f}%
🎯 Final 50 Episodes: {final_win_rate:.1f}%
📈 Best 50-Episode Streak: {max(win_rates):.1f}%
📉 Lowest Point: {min(win_rates):.1f}%
    
🤖 Episodes Trained: {episodes}
🏭 Robots: {robots}
🎲 Random Seed Results"""
    
    ax4.text(0.05, 0.95, metrics_text, transform=ax4.transAxes, fontsize=12,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
    ax4.set_title('Training Statistics', fontsize=14, fontweight='bold')
    ax4.axis('off')
    
    # Save the graph
    plt.tight_layout()
    plt.savefig('training_winrate_comprehensive.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\n🎯 TRAINING COMPLETE!")
    print(f"============================================================")
    print(f"📊 Overall Win Rate: {overall_win_rate:.1f}%")
    print(f"🎯 Final 50 Episodes Win Rate: {final_win_rate:.1f}%")
    print(f"📈 Peak Performance: {max(win_rates):.1f}%")
    print(f"📊 Graph saved as 'training_winrate_comprehensive.png'")
    
    return overall_win_rate, final_win_rate

if __name__ == "__main__":
    generate_win_rate_graph(episodes=300, robots=2)