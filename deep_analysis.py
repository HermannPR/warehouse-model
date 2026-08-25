#!/usr/bin/env python3
"""
Deep dive analysis: Why high initial win rate?
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def analyze_epsilon_vs_performance():
    """Analyze relationship between epsilon decay and performance"""
    
    per_episode_file = os.path.join("metrics_out", "per_episode.csv")
    df = pd.read_csv(per_episode_file)
    
    episodes = df['episode'].values
    success = df['success'].values
    rewards = df['total_reward'].values
    
    # Calculate epsilon values (based on the training formula)
    def calculate_epsilon(episode, total_episodes=2000):
        """Quadratic epsilon decay formula from training"""
        EPSILON_START = 0.9
        EPSILON_END = 0.05
        progress = episode / max(1, total_episodes)
        return float(EPSILON_END + (EPSILON_START - EPSILON_END) * (1 - progress) ** 2)
    
    epsilons = [calculate_epsilon(ep) for ep in episodes]
    
    # Create analysis plot
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 10))
    
    # 1. Epsilon decay over time
    ax1.plot(episodes, epsilons, color='red', linewidth=2)
    ax1.set_title('Epsilon Decay During Training', fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Epsilon (Exploration Rate)')
    ax1.grid(True, alpha=0.3)
    ax1.text(0.7, 0.8, f'Start ε: {epsilons[0]:.3f}\nEnd ε: {epsilons[-1]:.3f}', 
             transform=ax1.transAxes, bbox=dict(boxstyle='round', facecolor='wheat'))
    
    # 2. Win rate vs Epsilon correlation
    # Group by epsilon ranges
    epsilon_ranges = [(0.05, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.9)]
    epsilon_labels = ['Very Low\n(0.05-0.2)', 'Low\n(0.2-0.4)', 'Medium\n(0.4-0.6)', 'High\n(0.6-0.8)', 'Very High\n(0.8-0.9)']
    win_rates_by_epsilon = []
    
    for low, high in epsilon_ranges:
        mask = (np.array(epsilons) >= low) & (np.array(epsilons) < high)
        if np.any(mask):
            win_rate = np.mean(success[mask])
            win_rates_by_epsilon.append(win_rate)
        else:
            win_rates_by_epsilon.append(0)
    
    bars = ax2.bar(epsilon_labels, win_rates_by_epsilon, color=['darkgreen', 'green', 'orange', 'red', 'darkred'])
    ax2.set_title('Win Rate by Exploration Level', fontweight='bold')
    ax2.set_ylabel('Win Rate')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    
    # Add percentage labels on bars
    for bar, rate in zip(bars, win_rates_by_epsilon):
        if rate > 0:
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{rate:.1%}', ha='center', va='bottom', fontweight='bold')
    
    # 3. Reward efficiency over time (reward per successful episode)
    window_size = 100
    episode_chunks = []
    reward_efficiency = []
    win_rate_chunks = []
    
    for i in range(0, len(episodes), window_size):
        chunk_success = success[i:i+window_size]
        chunk_rewards = rewards[i:i+window_size]
        
        successful_rewards = chunk_rewards[chunk_success == 1]
        if len(successful_rewards) > 0:
            avg_successful_reward = np.mean(successful_rewards)
            reward_efficiency.append(avg_successful_reward)
        else:
            reward_efficiency.append(0)
        
        win_rate_chunks.append(np.mean(chunk_success))
        episode_chunks.append(i + window_size//2)
    
    ax3.plot(episode_chunks, reward_efficiency, 'o-', color='blue', linewidth=2, label='Reward per Success')
    ax3_twin = ax3.twinx()
    ax3_twin.plot(episode_chunks, win_rate_chunks, 'o-', color='red', alpha=0.7, linewidth=2, label='Win Rate')
    
    ax3.set_title('Reward Efficiency vs Win Rate Over Time', fontweight='bold')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Avg Reward per Successful Episode', color='blue')
    ax3_twin.set_ylabel('Win Rate', color='red')
    ax3_twin.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    ax3.grid(True, alpha=0.3)
    
    # 4. Early vs Late performance comparison
    early_episodes = episodes[:400]  # First 20%
    late_episodes = episodes[-400:]  # Last 20%
    
    early_success = success[:400]
    late_success = success[-400:]
    early_rewards = rewards[:400]
    late_rewards = rewards[-400:]
    
    comparison_data = {
        'Win Rate': [np.mean(early_success), np.mean(late_success)],
        'Avg Reward': [np.mean(early_rewards), np.mean(late_rewards)],
        'Reward Std': [np.std(early_rewards), np.std(late_rewards)],
        'Success Reward': [np.mean(early_rewards[early_success==1]) if np.any(early_success) else 0,
                          np.mean(late_rewards[late_success==1]) if np.any(late_success) else 0]
    }
    
    x_pos = np.arange(len(comparison_data))
    width = 0.35
    
    early_values = [comparison_data['Win Rate'][0], comparison_data['Avg Reward'][0]/100, 
                   comparison_data['Reward Std'][0]/100, comparison_data['Success Reward'][0]/100]
    late_values = [comparison_data['Win Rate'][1], comparison_data['Avg Reward'][1]/100,
                  comparison_data['Reward Std'][1]/100, comparison_data['Success Reward'][1]/100]
    
    ax4.bar(x_pos - width/2, early_values, width, label='Early Training (1-400)', color='lightblue')
    ax4.bar(x_pos + width/2, late_values, width, label='Late Training (1601-2000)', color='darkblue')
    
    ax4.set_title('Early vs Late Training Comparison', fontweight='bold')
    ax4.set_ylabel('Normalized Values')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(['Win Rate', 'Avg Reward\n(/100)', 'Reward Std\n(/100)', 'Success Reward\n(/100)'])
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.suptitle('Deep Analysis: High Initial Win Rate Phenomenon', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig('epsilon_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Print detailed findings
    print("\n" + "="*70)
    print("🔬 DEEP ANALYSIS: HIGH INITIAL WIN RATE PHENOMENON")
    print("="*70)
    
    print(f"\n📊 EPSILON-PERFORMANCE CORRELATION:")
    print("-" * 50)
    for i, (label, rate) in enumerate(zip(epsilon_labels, win_rates_by_epsilon)):
        if rate > 0:
            exploration_level = epsilon_ranges[i]
            print(f"{label.replace(chr(10), ' ')}: {rate:.1%} win rate")
    
    print(f"\n🎲 EXPLORATION PARADOX:")
    print("-" * 50)
    highest_epsilon_winrate = win_rates_by_epsilon[-1] if win_rates_by_epsilon[-1] > 0 else win_rates_by_epsilon[-2]
    lowest_epsilon_winrate = win_rates_by_epsilon[0]
    
    if highest_epsilon_winrate >= lowest_epsilon_winrate:
        print("🤔 COUNTER-INTUITIVE FINDING: High exploration (random actions) performs")
        print("   as well as or better than low exploration (learned policy)!")
        print("\n   POSSIBLE REASONS:")
        print("   • Task is simple enough that random coordination works")
        print("   • Warehouse layout naturally guides robots to success")
        print("   • Box placement makes accidental success likely")
        print("   • Early termination rewards any delivery combination")
    
    print(f"\n⚡ EFFICIENCY ANALYSIS:")
    print("-" * 50)
    early_efficiency = np.mean(early_rewards[early_success==1]) if np.any(early_success) else 0
    late_efficiency = np.mean(late_rewards[late_success==1]) if np.any(late_success) else 0
    
    print(f"Early Training Reward per Success: {early_efficiency:.1f}")
    print(f"Late Training Reward per Success:  {late_efficiency:.1f}")
    print(f"Efficiency Change: {late_efficiency - early_efficiency:+.1f}")
    
    if late_efficiency < early_efficiency:
        print("📉 EFFICIENCY DECREASED: Later episodes achieve success with lower rewards.")
        print("   This suggests faster/more direct task completion.")
    
    print(f"\n🧠 LEARNING HYPOTHESIS:")
    print("-" * 50)
    print("The warehouse coordination task appears to have these characteristics:")
    print("1. 🎯 NATURALLY SOLVABLE: Random actions often lead to success")
    print("2. 🚀 FAST CONVERGENCE: Optimal strategy learned very quickly") 
    print("3. 📊 STABLE PERFORMANCE: Little room for improvement beyond ~80%")
    print("4. ⚖️  EXPLORATION-EXPLOITATION BALANCE: High exploration doesn't hurt performance")
    
    return comparison_data

if __name__ == "__main__":
    comparison_data = analyze_epsilon_vs_performance()