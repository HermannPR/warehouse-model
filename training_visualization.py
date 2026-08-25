#!/usr/bin/env python3
"""
Training Progress Visualization - Track steps per episode and show learning curves
"""

import matplotlib.pyplot as plt
import numpy as np
from warehouse import train_model_episodic
import json
import os
from datetime import datetime

def train_with_step_tracking(episodes=50, steps_per_episode=200, config_path='layout.json'):
    """
    Modified training function that tracks steps per episode for visualization
    """
    print(f"🏋️ TRAINING WITH STEP TRACKING")
    print(f"Episodes: {episodes} | Max Steps: {steps_per_episode}")
    print(f"Config: {config_path}")
    print("=" * 60)
    
    # Storage for metrics
    episode_data = {
        'episode_numbers': [],
        'total_steps_used': [],
        'successful_deliveries': [],
        'efficiency_score': [],
        'pathfinding_usage': [],
        'average_path_length': []
    }
    
    # Run training and collect data
    print("🚀 Starting training with progress tracking...")
    
    # We'll modify the training approach to collect step data
    from warehouse import Warehouse
    
    best_efficiency = float('inf')
    efficiency_history = []
    
    for episode in range(episodes):
        print(f"Episode {episode + 1}/{episodes}", end=" - ")
        
        # Create model for this episode
        params = {'config_path': config_path}
        model = Warehouse(parameters=params)
        model.setup()
        model.auto_cycle_reset = False
        
        # Load weights if not first episode
        if episode > 0:
            weights_file = "weights/W_linear.npy"
            if os.path.exists(weights_file):
                try:
                    model.load_weights(weights_file)
                except:
                    pass
        
        # Track episode metrics
        episode_steps = 0
        deliveries_completed = 0
        pathfinding_calls = 0
        total_path_length = 0
        
        # Run episode
        for step in range(steps_per_episode):
            # Count steps and track pathfinding usage
            episode_steps += 1
            
            # Track robot activities
            step_deliveries = sum(getattr(robot, 'deliveries_this_episode', 0) for robot in model.robots)
            if step_deliveries > deliveries_completed:
                deliveries_completed = step_deliveries
            
            # Simulate pathfinding usage (estimate based on robot actions)
            for robot in model.robots:
                if hasattr(robot, 'target_pos') and robot.target_pos:
                    # Estimate pathfinding usage
                    from warehouse import get_optimal_path
                    path = get_optimal_path(model, robot.position, robot.target_pos, 'maximum')
                    if path:
                        pathfinding_calls += 1
                        total_path_length += len(path)
            
            # Step the model
            try:
                model.step()
                
                # Check if episode should end (all deliveries complete)
                current_deliveries = sum(getattr(robot, 'deliveries_this_episode', 0) for robot in model.robots)
                if current_deliveries >= len(model.robots):  # Each robot delivered at least once
                    episode_steps = step + 1  # Actual steps used
                    break
                    
            except Exception as e:
                break
        
        # Calculate efficiency metrics
        efficiency_score = episode_steps / max(1, deliveries_completed) if deliveries_completed > 0 else steps_per_episode
        avg_path_length = total_path_length / max(1, pathfinding_calls) if pathfinding_calls > 0 else 0
        
        # Store episode data
        episode_data['episode_numbers'].append(episode + 1)
        episode_data['total_steps_used'].append(episode_steps)
        episode_data['successful_deliveries'].append(deliveries_completed)
        episode_data['efficiency_score'].append(efficiency_score)
        episode_data['pathfinding_usage'].append(pathfinding_calls)
        episode_data['average_path_length'].append(avg_path_length)
        
        # Track best efficiency
        if efficiency_score < best_efficiency:
            best_efficiency = efficiency_score
        
        efficiency_history.append(efficiency_score)
        
        # Save weights periodically
        if (episode + 1) % 10 == 0:
            os.makedirs("weights", exist_ok=True)
            try:
                model.save_weights("weights/W_linear.npy")
            except:
                pass
        
        # Progress output
        success_rate = (deliveries_completed / len(model.robots)) * 100 if len(model.robots) > 0 else 0
        print(f"Steps: {episode_steps:3d}, Deliveries: {deliveries_completed}, Efficiency: {efficiency_score:.1f}")
    
    return episode_data, model

def create_training_visualization(episode_data, save_path="training_progress.png"):
    """
    Create comprehensive visualization of training progress
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('🚀 Warehouse Robot Training Progress', fontsize=16, fontweight='bold')
    
    episodes = episode_data['episode_numbers']
    
    # 1. Steps per Episode (Main metric)
    ax1.plot(episodes, episode_data['total_steps_used'], 'b-', linewidth=2, marker='o', markersize=4)
    ax1.set_title('📉 Steps per Episode (Lower is Better)', fontweight='bold')
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Steps Used')
    ax1.grid(True, alpha=0.3)
    
    # Add trend line
    if len(episodes) > 1:
        z = np.polyfit(episodes, episode_data['total_steps_used'], 1)
        p = np.poly1d(z)
        ax1.plot(episodes, p(episodes), "r--", alpha=0.8, linewidth=2, label=f'Trend: {z[0]:.2f} steps/episode')
        ax1.legend()
    
    # 2. Efficiency Score (Steps per Delivery)
    ax2.plot(episodes, episode_data['efficiency_score'], 'g-', linewidth=2, marker='s', markersize=4)
    ax2.set_title('⚡ Efficiency Score (Steps per Delivery)', fontweight='bold')
    ax2.set_xlabel('Episode')
    ax2.set_ylabel('Steps per Delivery')
    ax2.grid(True, alpha=0.3)
    
    # 3. Successful Deliveries
    ax3.bar(episodes, episode_data['successful_deliveries'], alpha=0.7, color='orange')
    ax3.set_title('📦 Deliveries per Episode', fontweight='bold')
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Deliveries Completed')
    ax3.grid(True, alpha=0.3)
    
    # 4. Average Path Length (Pathfinding Optimization)
    if any(x > 0 for x in episode_data['average_path_length']):
        ax4.plot(episodes, episode_data['average_path_length'], 'm-', linewidth=2, marker='^', markersize=4)
        ax4.set_title('🧭 Average Path Length (Pathfinding Quality)', fontweight='bold')
        ax4.set_xlabel('Episode')
        ax4.set_ylabel('Average Steps per Path')
        ax4.grid(True, alpha=0.3)
    else:
        ax4.text(0.5, 0.5, 'Pathfinding data\nnot available', ha='center', va='center', transform=ax4.transAxes)
        ax4.set_title('🧭 Pathfinding Data', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"📊 Training visualization saved to: {save_path}")
    
    return fig

def analyze_training_trends(episode_data):
    """
    Analyze training trends and provide insights
    """
    print(f"\n📊 TRAINING ANALYSIS")
    print("=" * 50)
    
    episodes = episode_data['episode_numbers']
    steps = episode_data['total_steps_used']
    deliveries = episode_data['successful_deliveries']
    efficiency = episode_data['efficiency_score']
    
    if len(episodes) < 2:
        print("Need more episodes for trend analysis")
        return
    
    # Calculate trends
    step_trend = np.polyfit(episodes, steps, 1)[0]
    efficiency_trend = np.polyfit(episodes, efficiency, 1)[0]
    
    # Performance metrics
    initial_steps = np.mean(steps[:5]) if len(steps) >= 5 else steps[0]
    final_steps = np.mean(steps[-5:]) if len(steps) >= 5 else steps[-1]
    improvement = initial_steps - final_steps
    improvement_percent = (improvement / initial_steps) * 100 if initial_steps > 0 else 0
    
    print(f"📈 LEARNING PROGRESS:")
    print(f"   Initial Performance: {initial_steps:.1f} steps/episode")
    print(f"   Final Performance:   {final_steps:.1f} steps/episode")
    print(f"   Improvement:         {improvement:.1f} steps ({improvement_percent:.1f}%)")
    
    print(f"\n📉 TRENDS:")
    if step_trend < -0.5:
        print(f"   ✅ Steps per episode: DECREASING ({step_trend:.2f}/episode)")
        print(f"      Robots are learning to be more efficient!")
    elif step_trend > 0.5:
        print(f"   ⚠️ Steps per episode: INCREASING ({step_trend:.2f}/episode)")
        print(f"      May need training adjustments")
    else:
        print(f"   📊 Steps per episode: STABLE ({step_trend:.2f}/episode)")
        print(f"      Performance has converged")
    
    if efficiency_trend < -0.1:
        print(f"   ✅ Efficiency: IMPROVING ({efficiency_trend:.2f}/episode)")
    elif efficiency_trend > 0.1:
        print(f"   ⚠️ Efficiency: DECLINING ({efficiency_trend:.2f}/episode)")
    else:
        print(f"   📊 Efficiency: STABLE ({efficiency_trend:.2f}/episode)")
    
    # Success analysis
    avg_deliveries = np.mean(deliveries)
    delivery_success_rate = (avg_deliveries / 4) * 100  # Assuming 4 robots
    
    print(f"\n🎯 SUCCESS METRICS:")
    print(f"   Average Deliveries: {avg_deliveries:.1f} per episode")
    print(f"   Success Rate:       {delivery_success_rate:.1f}%")
    
    # Best performance
    best_episode = episodes[np.argmin(steps)]
    best_steps = min(steps)
    print(f"   Best Performance:   Episode {best_episode} ({best_steps} steps)")
    
    # Overall assessment
    print(f"\n🏆 TRAINING ASSESSMENT:")
    if improvement_percent > 20:
        print(f"   🌟 EXCELLENT: Major improvement in efficiency!")
    elif improvement_percent > 10:
        print(f"   ✅ GOOD: Solid learning progress")
    elif improvement_percent > 5:
        print(f"   👍 MODERATE: Some improvement observed")
    elif improvement_percent > 0:
        print(f"   📊 MINIMAL: Limited improvement")
    else:
        print(f"   ⚠️ CONCERNING: No clear improvement trend")
    
    return {
        'improvement_percent': improvement_percent,
        'step_trend': step_trend,
        'best_performance': best_steps,
        'avg_deliveries': avg_deliveries
    }

def main():
    """Run training with visualization"""
    print("🎯 WAREHOUSE TRAINING WITH STEP VISUALIZATION")
    print("=" * 60)
    
    # Run training with tracking
    episode_data, final_model = train_with_step_tracking(
        episodes=30,  # Reasonable number for visualization
        steps_per_episode=150,
        config_path='layout.json'
    )
    
    # Create visualization
    fig = create_training_visualization(episode_data)
    
    # Analyze trends
    analysis = analyze_training_trends(episode_data)
    
    # Show the plot
    plt.show()
    
    print(f"\n🎊 TRAINING VISUALIZATION COMPLETE!")
    print(f"📊 The graph shows how pathfinding optimization and learning")
    print(f"   reduce the steps needed per episode over time.")
    
    return episode_data, analysis

if __name__ == "__main__":
    try:
        episode_data, analysis = main()
        print(f"\n✅ Training visualization generated successfully!")
    except Exception as e:
        print(f"❌ Error creating visualization: {e}")
        print(f"Make sure matplotlib is installed: pip install matplotlib")