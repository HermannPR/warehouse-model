#!/usr/bin/env python3
"""
Train a fresh model and visualize the actual learning progression
"""

import matplotlib.pyplot as plt
import numpy as np
import os
import tempfile
from warehouse import Warehouse

def train_and_visualize_fresh_model(episodes=100, robots=2):
    """Train a completely fresh model and capture real learning data"""
    
    print(f"🚀 TRAINING FRESH MODEL WITH VISUALIZATION")
    print(f"==================================================")
    print(f"📊 Training {robots} robots for {episodes} episodes from scratch")
    print(f"🔄 Clearing all existing Q-tables for fresh start")
    print(f"============================================================")
    
    # Track detailed training metrics
    episode_results = []
    deliveries_per_episode = []
    steps_per_episode = []
    epsilon_values = []
    cumulative_rewards = []
    
    episode_number = 0
    
    # Training loop with fresh model each episode (proper episodic training)
    for episode in range(episodes):
        # Create fresh model setup
        model = Warehouse(
            width=25, height=25, 
            n_robots=robots, 
            n_boxes=10, 
            episode_limit=100,
            training_mode=True
        )
        model.setup()
        
        # Reset Q-tables on first episode for completely fresh start
        if episode == 0:
            for robot in model.robots:
                robot.q_table = {}
            print(f"🔄 Reset all Q-tables - Starting fresh!")
            print(f"🎯 Initial epsilon: {model.global_epsilon:.3f}")
        
        # Update epsilon for this episode (episodic decay)
        progress = episode / max(1, episodes)
        model.global_epsilon = 0.05 + (0.9 - 0.05) * (1 - progress) ** 2
        
        # Load weights from previous episode (except first one)
        if episode > 0:
            # Transfer Q-tables from previous training
            for i, robot in enumerate(model.robots):
                if i < len(previous_q_tables):
                    robot.q_table = previous_q_tables[i].copy()
        
        # Run episode
        step_count = 0
        episode_reward = 0
        
        while model.running and step_count < 100:
            model.step()
            step_count += 1
            
            # Accumulate rewards
            if hasattr(model, 'stats') and 'reward_hist' in model.stats and model.stats['reward_hist']:
                episode_reward += model.stats['reward_hist'][-1]
        
        # Save Q-tables for next episode
        previous_q_tables = [robot.q_table.copy() for robot in model.robots]
        
        # Record episode results
        deliveries = getattr(model, 'episode_delivery_count', 0)
        won = 1 if deliveries >= robots else 0
        
        episode_results.append(won)
        deliveries_per_episode.append(deliveries)
        steps_per_episode.append(step_count)
        epsilon_values.append(model.global_epsilon)
        cumulative_rewards.append(episode_reward)
        
        # Print progress every 10 episodes
        if (episode + 1) % 10 == 0:
            recent_wins = sum(episode_results[-10:])
            win_rate = (recent_wins / 10) * 100
            avg_deliveries = np.mean(deliveries_per_episode[-10:])
            avg_steps = np.mean(steps_per_episode[-10:])
            
            print(f"Episode {episode + 1:3d}: Win Rate: {win_rate:5.1f}% | "
                  f"Deliveries: {deliveries:1d} | "
                  f"Steps: {step_count:2d} | "
                  f"Epsilon: {model.global_epsilon:.3f} | "
                  f"Reward: {episode_reward:6.1f}")
    
    # Create comprehensive visualization of actual training data
    visualize_actual_training_results(
        episode_results, deliveries_per_episode, steps_per_episode, 
        epsilon_values, cumulative_rewards, robots
    )
    
    return episode_results

def visualize_actual_training_results(episode_results, deliveries_per_episode, 
                                    steps_per_episode, epsilon_values, 
                                    cumulative_rewards, robots):
    """Create visualization from actual training data"""
    
    episodes = list(range(1, len(episode_results) + 1))
    
    # Create comprehensive visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('🎯 Actual Training Results: Fresh Model Learning Progression', 
                 fontsize=16, fontweight='bold')
    
    # 1. Win Rate Learning Curve
    def rolling_average(data, window):
        return [np.mean(data[max(0, i-window+1):i+1]) for i in range(len(data))]
    
    # Convert binary wins to percentages
    win_percentages = [w * 100 for w in episode_results]
    roll_5 = rolling_average(episode_results, 5)
    roll_10 = rolling_average(episode_results, 10)
    
    ax1.scatter(episodes, win_percentages, alpha=0.4, s=20, color='lightblue', label='Individual episodes')
    ax1.plot(episodes, np.array(roll_5) * 100, 'blue', linewidth=2, label='5-episode average')
    ax1.plot(episodes, np.array(roll_10) * 100, 'red', linewidth=3, label='10-episode average')
    
    ax1.set_title('Actual Win Rate Learning Progression', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Win Rate (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-5, 105)
    
    # 2. Deliveries vs Target
    ax2.plot(episodes, deliveries_per_episode, 'g-', alpha=0.6, linewidth=1)
    ax2.axhline(y=robots, color='red', linestyle='--', linewidth=2, label=f'Target: {robots} deliveries')
    success_episodes = [i+1 for i, d in enumerate(deliveries_per_episode) if d >= robots]
    success_deliveries = [d for d in deliveries_per_episode if d >= robots]
    ax2.scatter(success_episodes, success_deliveries, color='green', s=30, alpha=0.7, label='Successful episodes')
    
    ax2.set_title('Deliveries per Episode (Learning Progress)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Number of Deliveries')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, max(max(deliveries_per_episode), robots) + 1)
    
    # 3. Epsilon Decay and Performance
    ax3_twin = ax3.twinx()
    
    line1 = ax3.plot(episodes, epsilon_values, 'purple', linewidth=2, label='Epsilon')
    line2 = ax3_twin.plot(episodes, np.array(roll_10) * 100, 'green', linewidth=2, label='Win Rate (10-ep avg)')
    
    ax3.set_title('Epsilon Decay vs Learning Performance', fontsize=14, fontweight='bold')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Epsilon Value', color='purple')
    ax3_twin.set_ylabel('Win Rate (%)', color='green')
    ax3.grid(True, alpha=0.3)
    
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax3.legend(lines, labels, loc='center right')
    
    # 4. Training Statistics and Analysis
    early_performance = np.mean(episode_results[:20]) * 100 if len(episode_results) >= 20 else np.mean(episode_results) * 100
    mid_performance = np.mean(episode_results[len(episode_results)//2-5:len(episode_results)//2+5]) * 100 if len(episode_results) >= 20 else 0
    late_performance = np.mean(episode_results[-10:]) * 100 if len(episode_results) >= 10 else np.mean(episode_results) * 100
    
    improvement = late_performance - early_performance
    total_successes = sum(episode_results)
    success_rate = (total_successes / len(episode_results)) * 100
    
    avg_steps = np.mean(steps_per_episode)
    total_reward = sum(cumulative_rewards)
    
    stats_text = f"""ACTUAL TRAINING RESULTS:

PERFORMANCE METRICS:
• Early Episodes (1-20): {early_performance:.1f}%
• Mid Training: {mid_performance:.1f}%
• Late Episodes (final 10): {late_performance:.1f}%
• Total Improvement: {improvement:+.1f}%
• Overall Success Rate: {success_rate:.1f}%

TRAINING CHARACTERISTICS:
• Total Successful Episodes: {total_successes}/{len(episode_results)}
• Average Steps per Episode: {avg_steps:.1f}
• Total Cumulative Reward: {total_reward:.1f}
• Final Epsilon: {epsilon_values[-1]:.3f}

LEARNING CURVE ANALYSIS:
{'✓' if improvement > 10 else '⚠'} Learning Progression: {improvement:+.1f}%
{'✓' if success_rate > 50 else '⚠'} Success Rate: {success_rate:.1f}%
{'✓' if late_performance > early_performance else '⚠'} Final > Initial Performance
{'✓' if avg_steps > 50 else '⚠'} Episode Engagement: {avg_steps:.1f} steps

STUCK ROBOT SOLUTION IMPACT:
• Prevents training stagnation
• Enables continuous learning
• Maintains episode progression"""
    
    ax4.text(0.05, 0.95, stats_text, transform=ax4.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.5", 
             facecolor="lightgreen" if improvement > 10 else "lightyellow", alpha=0.8))
    ax4.set_title('Actual Training Statistics', fontsize=14, fontweight='bold')
    ax4.axis('off')
    
    # Save the visualization
    plt.tight_layout()
    plt.savefig('actual_training_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\n🎯 ACTUAL TRAINING VISUALIZATION COMPLETE!")
    print(f"============================================================")
    print(f"📊 Performance: {early_performance:.1f}% → {late_performance:.1f}% ({improvement:+.1f}%)")
    print(f"📈 Success Rate: {success_rate:.1f}%")
    print(f"📊 Visualization saved as 'actual_training_results.png'")
    
    return early_performance, late_performance, improvement

if __name__ == "__main__":
    train_and_visualize_fresh_model(episodes=100, robots=2)