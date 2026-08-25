#!/usr/bin/env python3
"""
Corrected training script that properly initializes episodic training
"""

import matplotlib.pyplot as plt
import numpy as np
import os
import tempfile
from warehouse import Warehouse

def train_fresh_model_properly(episodes=100, robots=2):
    """Train using the proper episodic training setup"""
    
    print(f"🚀 PROPER EPISODIC TRAINING WITH VISUALIZATION")
    print(f"==================================================")
    print(f"📊 Training {robots} robots for {episodes} episodes using proper setup")
    print(f"============================================================")
    
    # Use existing config file
    config_path = 'layout.json'
    
    # Track training data
    episode_results = []
    deliveries_per_episode = []
    epsilon_values = []
    steps_per_episode = []
    
    # Training loop using proper episodic setup
    for episode in range(episodes):
        # Create model with proper parameters
        params = {'config_path': config_path}
        model = Warehouse(parameters=params)
        model.setup()
        model.auto_cycle_reset = False
        
        # Limit robots if specified
        if robots and robots < len(model.robots):
            model.robots = model.robots[:robots]
        
        # CRITICAL: Setup episodic training mode
        model.setup_episode_based_training()
        model.training_mode = True
        model.box_respawn_enabled = False
        
        # Reset Q-tables on first episode for fresh start
        if episode == 0:
            for robot in model.robots:
                robot.q_table = {}
            print(f"🔄 Reset all Q-tables for fresh start")
        
        # Compute episodic epsilon decay
        model._update_epsilon_episodic(episode, episodes)
        model.epsilon_override = model.global_epsilon
        
        # Run the episode
        step_count = 0
        max_steps = 100
        
        while model.running and step_count < max_steps:
            model.step()
            step_count += 1
        
        # Record results
        deliveries = getattr(model, 'episode_delivery_count', 0)
        won = 1 if deliveries >= robots else 0
        
        episode_results.append(won)
        deliveries_per_episode.append(deliveries)
        epsilon_values.append(model.global_epsilon)
        steps_per_episode.append(step_count)
        
        # Print progress
        if (episode + 1) % 10 == 0:
            recent_wins = sum(episode_results[-10:])
            win_rate = (recent_wins / 10) * 100
            avg_deliveries = np.mean(deliveries_per_episode[-10:])
            
            print(f"Episode {episode + 1:3d}: Win Rate: {win_rate:5.1f}% | "
                  f"Deliveries: {deliveries:1d} | "
                  f"Steps: {step_count:2d} | "
                  f"Epsilon: {model.global_epsilon:.3f}")
        
        # Clean up model
        del model
    
    # Create visualization
    visualize_proper_training_results(
        episode_results, deliveries_per_episode, epsilon_values, 
        steps_per_episode, robots
    )
    
    return episode_results

def visualize_proper_training_results(episode_results, deliveries_per_episode, 
                                    epsilon_values, steps_per_episode, robots):
    """Create visualization from proper training data"""
    
    episodes = list(range(1, len(episode_results) + 1))
    
    # Create comprehensive visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('🎯 Proper Episodic Training Results: Fresh Model Learning', 
                 fontsize=16, fontweight='bold')
    
    # 1. Win Rate Learning Curve
    def rolling_average(data, window):
        return [np.mean(data[max(0, i-window+1):i+1]) for i in range(len(data))]
    
    win_percentages = [w * 100 for w in episode_results]
    roll_5 = rolling_average(episode_results, 5)
    roll_10 = rolling_average(episode_results, 10)
    
    ax1.scatter(episodes, win_percentages, alpha=0.4, s=15, color='lightblue', label='Individual episodes')
    ax1.plot(episodes, np.array(roll_5) * 100, 'blue', linewidth=2, label='5-episode average')
    ax1.plot(episodes, np.array(roll_10) * 100, 'red', linewidth=3, label='10-episode average')
    
    ax1.set_title('Win Rate Learning Progression', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Win Rate (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-5, 105)
    
    # 2. Steps per Episode (engagement indicator)
    ax2.plot(episodes, steps_per_episode, 'orange', alpha=0.6, linewidth=1)
    ax2.axhline(y=np.mean(steps_per_episode), color='red', linestyle='--', 
                linewidth=2, label=f'Average: {np.mean(steps_per_episode):.1f} steps')
    
    ax2.set_title('Steps per Episode (Engagement Level)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Steps Taken')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Deliveries Progress
    ax3.plot(episodes, deliveries_per_episode, 'g-', alpha=0.6, linewidth=1)
    ax3.axhline(y=robots, color='red', linestyle='--', linewidth=2, label=f'Target: {robots} deliveries')
    
    # Highlight successful episodes
    success_episodes = [i+1 for i, d in enumerate(deliveries_per_episode) if d >= robots]
    success_deliveries = [d for d in deliveries_per_episode if d >= robots]
    if success_episodes:
        ax3.scatter(success_episodes, success_deliveries, color='green', s=40, alpha=0.8, label='Success!')
    
    ax3.set_title('Deliveries per Episode', fontsize=14, fontweight='bold')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Number of Deliveries')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, max(max(deliveries_per_episode), robots) + 1)
    
    # 4. Training Analysis
    early_performance = np.mean(episode_results[:20]) * 100 if len(episode_results) >= 20 else np.mean(episode_results) * 100
    late_performance = np.mean(episode_results[-20:]) * 100 if len(episode_results) >= 20 else np.mean(episode_results) * 100
    improvement = late_performance - early_performance
    
    total_successes = sum(episode_results)
    success_rate = (total_successes / len(episode_results)) * 100
    avg_steps = np.mean(steps_per_episode)
    
    # Check if learning is occurring
    learning_occurred = improvement > 5 and avg_steps > 10 and success_rate > 0
    
    analysis_text = f"""PROPER TRAINING ANALYSIS:

PERFORMANCE METRICS:
• Early Performance: {early_performance:.1f}%
• Late Performance: {late_performance:.1f}%
• Improvement: {improvement:+.1f}%
• Success Rate: {success_rate:.1f}%

ENGAGEMENT METRICS:
• Avg Steps/Episode: {avg_steps:.1f}
• Total Successes: {total_successes}
• Final Epsilon: {epsilon_values[-1]:.3f}

LEARNING INDICATORS:
{'✅' if improvement > 5 else '❌'} Performance Improvement
{'✅' if success_rate > 10 else '❌'} Reasonable Success Rate  
{'✅' if avg_steps > 10 else '❌'} Episode Engagement
{'✅' if len(success_episodes) > 0 else '❌'} Any Successful Episodes

TRAINING STATUS:
{'🎯 LEARNING DETECTED!' if learning_occurred else '⚠️  NO LEARNING - CHECK SETUP'}

NEXT STEPS:
{'Continue training for more episodes' if learning_occurred else 'Debug model setup and training configuration'}"""
    
    color = "lightgreen" if learning_occurred else "lightcoral"
    ax4.text(0.05, 0.95, analysis_text, transform=ax4.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.5", 
             facecolor=color, alpha=0.8))
    ax4.set_title('Training Analysis', fontsize=14, fontweight='bold')
    ax4.axis('off')
    
    # Save visualization
    plt.tight_layout()
    plt.savefig('proper_training_visualization.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\n🎯 PROPER TRAINING VISUALIZATION COMPLETE!")
    print(f"============================================================")
    print(f"📊 Performance: {early_performance:.1f}% → {late_performance:.1f}% ({improvement:+.1f}%)")
    print(f"📈 Success Rate: {success_rate:.1f}%")
    print(f"📊 Average Steps: {avg_steps:.1f}")
    print(f"{'🎯 Learning detected!' if learning_occurred else '⚠️  No learning detected - check setup'}")
    print(f"📊 Visualization saved as 'proper_training_visualization.png'")

if __name__ == "__main__":
    train_fresh_model_properly(episodes=100, robots=2)