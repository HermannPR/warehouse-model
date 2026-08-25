#!/usr/bin/env python3
"""
Analyze actual training progression to diagnose learning curve issues
"""

import matplotlib.pyplot as plt
import numpy as np
from warehouse import Warehouse

def analyze_training_progression(episodes=100, robots=2):
    """Analyze actual training progression from scratch"""
    
    print(f"🔍 ANALYZING TRAINING PROGRESSION")
    print(f"==================================================")
    print(f"📊 Fresh training with {robots} robots for {episodes} episodes")
    print(f"============================================================")
    
    # Track detailed metrics
    episode_results = []
    deliveries_per_episode = []
    steps_per_episode = []
    epsilon_values = []
    
    # Create fresh model with no pre-trained weights
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
        
        # Reset Q-tables for truly fresh start (optional - test both ways)
        if episode == 0:
            print(f"🎯 Starting fresh training - Initial epsilon: {model.global_epsilon:.3f}")
            # Optionally reset Q-tables completely for truly fresh start
            for robot in model.robots:
                robot.q_table = {}
            print("🔄 Reset all Q-tables for fresh learning")
        
        step_count = 0
        while model.running and step_count < 100:
            model.step()
            step_count += 1
        
        # Record episode results
        deliveries = getattr(model, 'episode_delivery_count', 0)
        won = 1 if deliveries >= robots else 0
        episode_results.append(won)
        deliveries_per_episode.append(deliveries)
        steps_per_episode.append(step_count)
        epsilon_values.append(model.global_epsilon)
        
        # Print progress every 10 episodes
        if (episode + 1) % 10 == 0:
            recent_wins = sum(episode_results[-10:])
            win_rate = (recent_wins / 10) * 100
            avg_deliveries = np.mean(deliveries_per_episode[-10:])
            
            print(f"Episode {episode + 1:3d}: Win Rate: {win_rate:5.1f}% | "
                  f"Avg Deliveries: {avg_deliveries:.1f} | "
                  f"Steps: {step_count:2d} | "
                  f"Epsilon: {model.global_epsilon:.3f}")
    
    # Analysis and visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('🔍 Training Progression Analysis: Learning Curve Diagnosis', fontsize=16, fontweight='bold')
    
    # 1. Win Rate Progression (rolling average)
    def rolling_average(data, window):
        return [np.mean(data[max(0, i-window+1):i+1]) for i in range(len(data))]
    
    episodes_x = range(1, len(episode_results) + 1)
    roll_5 = rolling_average(episode_results, 5)
    roll_10 = rolling_average(episode_results, 10)
    
    ax1.plot(episodes_x, np.array(roll_5) * 100, 'r-', label='5-episode avg', alpha=0.6)
    ax1.plot(episodes_x, np.array(roll_10) * 100, 'b-', label='10-episode avg', linewidth=2)
    ax1.scatter(episodes_x, np.array(episode_results) * 100, alpha=0.3, s=20, label='Individual episodes')
    ax1.set_title('Win Rate Learning Curve', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Win Rate (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-5, 105)
    
    # 2. Deliveries per Episode
    ax2.plot(episodes_x, deliveries_per_episode, 'g-', alpha=0.6)
    ax2.axhline(y=robots, color='red', linestyle='--', linewidth=2, label=f'Target: {robots} deliveries')
    ax2.fill_between(episodes_x, deliveries_per_episode, alpha=0.3, color='green')
    ax2.set_title('Deliveries per Episode', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Number of Deliveries')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, max(max(deliveries_per_episode), robots) + 1)
    
    # 3. Epsilon Decay
    ax3.plot(episodes_x, epsilon_values, 'purple', linewidth=2)
    ax3.set_title('Epsilon Decay (Exploration vs Exploitation)', fontsize=14, fontweight='bold')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Epsilon Value')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 1)
    
    # 4. Learning Analysis
    early_performance = np.mean(episode_results[:10]) * 100 if len(episode_results) >= 10 else 0
    mid_performance = np.mean(episode_results[len(episode_results)//2:len(episode_results)//2+10]) * 100 if len(episode_results) >= 20 else 0
    late_performance = np.mean(episode_results[-10:]) * 100 if len(episode_results) >= 10 else 0
    
    improvement = late_performance - early_performance
    
    analysis_text = f"""LEARNING CURVE DIAGNOSIS:

📊 Performance Progression:
• Early Episodes (1-10): {early_performance:.1f}%
• Mid Training: {mid_performance:.1f}%  
• Late Episodes (-10): {late_performance:.1f}%
• Total Improvement: {improvement:+.1f}%

🎯 Expected Learning Pattern:
• Should start LOW (0-20%)
• Gradually increase with experience
• Plateau at high performance (80-95%)

⚠️ Potential Issues Detected:
• High initial performance = pre-trained weights?
• Declining performance = exploration interference?
• Need proper learning curve analysis

🔧 Recommendations:
• Reset Q-tables for fresh start
• Adjust epsilon decay rate
• Check reward structure"""
    
    ax4.text(0.05, 0.95, analysis_text, transform=ax4.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.5", 
             facecolor="lightyellow", alpha=0.8))
    ax4.set_title('Learning Curve Diagnosis', fontsize=14, fontweight='bold')
    ax4.axis('off')
    
    # Save the analysis
    plt.tight_layout()
    plt.savefig('training_progression_diagnosis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"\n🔍 TRAINING PROGRESSION ANALYSIS COMPLETE!")
    print(f"============================================================")
    print(f"📊 Early Performance: {early_performance:.1f}%")
    print(f"📈 Late Performance: {late_performance:.1f}%")
    print(f"📊 Total Improvement: {improvement:+.1f}%")
    print(f"📊 Analysis saved as 'training_progression_diagnosis.png'")
    
    return episode_results, early_performance, late_performance

if __name__ == "__main__":
    analyze_training_progression(episodes=100, robots=2)