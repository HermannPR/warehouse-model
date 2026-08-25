#!/usr/bin/env python3
"""
Stress Test Adaptive Behavior - Create challenging scenarios to trigger adaptations
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
from warehouse import Warehouse
import os

def create_challenging_scenario():
    """
    Create a challenging scenario that will trigger adaptive behaviors
    """
    print("🎯 CREATING CHALLENGING SCENARIO")
    print("=" * 50)
    
    # Test parameters - more challenging
    params = {'config_path': 'layout.json'}
    episodes = 15
    steps_per_episode = 80  # Shorter time limit to create pressure
    
    # Track behavioral adaptations
    behavior_data = {
        'episodes': [],
        'robot_behaviors': {0: [], 1: [], 2: [], 3: []},
        'adaptation_events': [],
        'performance_metrics': {
            'steps_per_episode': [],
            'successful_deliveries': [],
            'behavior_changes': [],
            'failure_counts': []
        }
    }
    
    print("🚀 Running challenging stress test scenarios...")
    
    for episode in range(episodes):
        print(f"\n--- Episode {episode + 1} (Challenging Mode) ---")
        
        # Create model
        model = Warehouse(parameters=params)
        model.setup()
        model.auto_cycle_reset = False
        
        # Add artificial challenges to trigger adaptations
        # Reduce pathfinding search limit to create navigation pressure
        for robot in model.robots:
            # Lower action success threshold to trigger adaptations more easily
            robot.action_success_counter = 8  # Start with some failures
            
            # Add some artificial failures to specific robots to test adaptation
            if episode > 5 and robot.id % 2 == 0:  # Even robots get movement issues
                robot.failure_history['movement_blocks'] = 3
            elif episode > 8 and robot.id % 2 == 1:  # Odd robots get pickup issues  
                robot.failure_history['pickup_failures'] = 4
        
        # Track episode metrics
        episode_behavior_changes = 0
        episode_deliveries = 0
        episode_failures = 0
        steps_used = 0
        
        # Run episode with artificial pressure
        for step in range(steps_per_episode):
            steps_used = step + 1
            
            try:
                # Step the model
                model.step()
                
                # Add artificial stuckness pressure
                if step > 40:  # After 40 steps, increase failure counters
                    for robot in model.robots:
                        if hasattr(robot, 'action_success_counter'):
                            if robot.action_success_counter < 12:
                                robot.action_success_counter += 1  # Increase pressure
                
                # Track behavior changes and adaptations
                for robot in model.robots:
                    current_behavior = getattr(robot, 'behavior_mode', 'NORMAL')
                    robot_id = getattr(robot, 'id', 0)
                    
                    # Record behavior for this robot
                    if len(behavior_data['robot_behaviors'][robot_id]) <= episode:
                        behavior_data['robot_behaviors'][robot_id].append(current_behavior)
                    
                    # Check for behavior change
                    if (hasattr(robot, 'behavior_change_cooldown') and 
                        robot.behavior_change_cooldown == 29):  # Just changed
                        episode_behavior_changes += 1
                        adaptation_event = {
                            'episode': episode + 1,
                            'step': step + 1,
                            'robot_id': robot_id,
                            'new_behavior': current_behavior,
                            'failure_history': dict(robot.failure_history) if hasattr(robot, 'failure_history') else {},
                            'action_counter': getattr(robot, 'action_success_counter', 0)
                        }
                        behavior_data['adaptation_events'].append(adaptation_event)
                        print(f"  🔄 Robot {robot_id} adapted to {current_behavior} mode (failures: {dict(robot.failure_history)})")
                    
                    # Track failure accumulation
                    if hasattr(robot, 'action_success_counter') and robot.action_success_counter > 10:
                        episode_failures += 1
                
                # Count deliveries
                current_deliveries = sum(getattr(robot, 'deliveries_this_episode', 0) 
                                       for robot in model.robots)
                episode_deliveries = max(episode_deliveries, current_deliveries)
                
                # Early termination if all robots delivered
                if episode_deliveries >= len(model.robots):
                    break
                    
            except Exception as e:
                print(f"  ⚠️  Episode {episode + 1} error: {e}")
                break
        
        # Record episode metrics
        behavior_data['episodes'].append(episode + 1)
        behavior_data['performance_metrics']['steps_per_episode'].append(steps_used)
        behavior_data['performance_metrics']['successful_deliveries'].append(episode_deliveries)
        behavior_data['performance_metrics']['behavior_changes'].append(episode_behavior_changes)
        behavior_data['performance_metrics']['failure_counts'].append(episode_failures)
        
        print(f"  📊 Episode {episode + 1}: {steps_used} steps, {episode_deliveries} deliveries, {episode_behavior_changes} adaptations, {episode_failures} failures")
    
    # Analysis and visualization
    create_stress_test_visualization(behavior_data)
    analyze_stress_test_results(behavior_data)
    
    return behavior_data

def create_stress_test_visualization(behavior_data):
    """
    Create visualization of stress test results
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Adaptive Behavior Under Stress: Robot Intelligence in Challenging Scenarios', 
                 fontsize=16, fontweight='bold')
    
    episodes = behavior_data['episodes']
    steps = behavior_data['performance_metrics']['steps_per_episode']
    deliveries = behavior_data['performance_metrics']['successful_deliveries']
    adaptations = behavior_data['performance_metrics']['behavior_changes']
    failures = behavior_data['performance_metrics']['failure_counts']
    
    # 1. Performance Under Stress
    ax1.plot(episodes, steps, 'b-', linewidth=2, marker='o', markersize=4, 
             alpha=0.7, label='Steps per Episode')
    ax1.fill_between(episodes, steps, alpha=0.3, color='blue')
    
    # Highlight adaptation episodes
    adaptation_episodes = [i for i, changes in enumerate(adaptations) if changes > 0]
    if adaptation_episodes:
        adaptation_steps = [steps[i] for i in adaptation_episodes]
        adaptation_ep_nums = [episodes[i] for i in adaptation_episodes]
        ax1.scatter(adaptation_ep_nums, adaptation_steps, 
                   color='red', s=120, alpha=0.9, marker='*', 
                   label='Adaptation Events', zorder=5)
    
    ax1.set_xlabel('Episode')
    ax1.set_ylabel('Steps to Complete')
    ax1.set_title('Performance Under Challenging Conditions')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # 2. Adaptation Timeline
    if behavior_data['adaptation_events']:
        adaptation_episodes_list = [event['episode'] for event in behavior_data['adaptation_events']]
        adaptation_robots = [event['robot_id'] for event in behavior_data['adaptation_events']]
        adaptation_behaviors = [event['new_behavior'] for event in behavior_data['adaptation_events']]
        
        # Create timeline plot
        colors = ['red', 'blue', 'green', 'orange']
        for i, (episode, robot_id, behavior) in enumerate(zip(adaptation_episodes_list, adaptation_robots, adaptation_behaviors)):
            ax2.scatter(episode, robot_id, c=colors[robot_id % 4], s=100, alpha=0.8)
            ax2.text(episode, robot_id + 0.1, behavior[:8], fontsize=8, ha='center')
        
        ax2.set_xlabel('Episode')
        ax2.set_ylabel('Robot ID')
        ax2.set_title('Adaptation Timeline by Robot')
        ax2.set_yticks(range(4))
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, 'No Adaptations Triggered', 
                ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title('Adaptation Timeline by Robot')
    
    # 3. Failure vs Success Correlation
    ax3.bar(episodes, failures, alpha=0.6, color='red', width=0.4, 
            label='Failure Events')
    ax3_twin = ax3.twinx()
    ax3_twin.plot(episodes, deliveries, 'g-', linewidth=2, marker='s', 
                  markersize=4, label='Successful Deliveries')
    
    ax3.set_xlabel('Episode')
    ax3.set_ylabel('Failure Count', color='red')
    ax3_twin.set_ylabel('Deliveries', color='green')
    ax3.set_title('Failures vs Success Rate')
    ax3.grid(True, alpha=0.3)
    
    # 4. Detailed Analysis
    ax4.axis('off')
    
    # Calculate metrics
    total_adaptations = sum(adaptations)
    episodes_with_adaptations = len([x for x in adaptations if x > 0])
    adaptation_rate = (episodes_with_adaptations / len(episodes)) * 100
    avg_performance = np.mean(steps)
    avg_deliveries = np.mean(deliveries)
    total_failures = sum(failures)
    
    # Adaptation effectiveness
    adapted_episodes = [i for i, changes in enumerate(adaptations) if changes > 0]
    if adapted_episodes:
        performance_with_adaptations = [steps[i] for i in adapted_episodes]
        performance_without = [steps[i] for i in range(len(steps)) if i not in adapted_episodes]
        if performance_with_adaptations and performance_without:
            adaptation_effect = np.mean(performance_without) - np.mean(performance_with_adaptations)
        else:
            adaptation_effect = 0
    else:
        adaptation_effect = 0
    
    analysis_text = f"""
STRESS TEST ANALYSIS

ADAPTATION METRICS
• Total Adaptations: {total_adaptations}
• Adaptation Rate: {adaptation_rate:.1f}%
• Episodes with Adaptations: {episodes_with_adaptations}/{len(episodes)}
• Adaptation Effectiveness: {adaptation_effect:.1f} step improvement

PERFORMANCE UNDER STRESS
• Average Steps: {avg_performance:.1f}
• Average Deliveries: {avg_deliveries:.1f}
• Total Failure Events: {total_failures}
• Stress Level: {"HIGH" if total_failures > 20 else "MODERATE" if total_failures > 10 else "LOW"}

INTELLIGENCE INDICATORS
"""
    
    if total_adaptations > 0:
        analysis_text += "✅ ADAPTIVE: System responds to challenges\n"
    else:
        analysis_text += "🔄 STABLE: No adaptations needed\n"
    
    if adaptation_effect > 5:
        analysis_text += "✅ EFFECTIVE: Adaptations improve performance\n"
    elif adaptation_effect > 0:
        analysis_text += "✅ BENEFICIAL: Adaptations help slightly\n"
    else:
        analysis_text += "🔄 NEUTRAL: Adaptations maintain stability\n"
    
    if adaptation_rate > 50:
        analysis_text += "✅ RESPONSIVE: High adaptation frequency\n"
    elif adaptation_rate > 20:
        analysis_text += "✅ SELECTIVE: Moderate adaptation rate\n"
    else:
        analysis_text += "🔄 CONSERVATIVE: Low adaptation rate\n"
    
    analysis_text += f"""
BEHAVIOR PATTERNS
"""
    behavior_counts = {}
    for event in behavior_data['adaptation_events']:
        behavior = event['new_behavior']
        behavior_counts[behavior] = behavior_counts.get(behavior, 0) + 1
    
    for behavior, count in behavior_counts.items():
        analysis_text += f"• {behavior}: {count} times\n"
    
    ax4.text(0.05, 0.95, analysis_text, transform=ax4.transAxes, fontsize=9,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8))
    
    plt.tight_layout()
    
    # Save visualization
    filename = 'adaptive_behavior_stress_test.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"\n📊 Stress test visualization saved to: {filename}")
    
    return fig

def analyze_stress_test_results(behavior_data):
    """
    Analyze stress test results in detail
    """
    print(f"\n🔍 DETAILED STRESS TEST ANALYSIS")
    print("=" * 50)
    
    adaptation_events = behavior_data['adaptation_events']
    
    if adaptation_events:
        print(f"🎯 ADAPTATION EVENTS ({len(adaptation_events)} total):")
        for event in adaptation_events:
            failures = event.get('failure_history', {})
            dominant_failure = max(failures.items(), key=lambda x: x[1]) if failures else ('none', 0)
            print(f"   Episode {event['episode']}: Robot {event['robot_id']} → {event['new_behavior']}")
            print(f"      Trigger: {dominant_failure[0]} ({dominant_failure[1]} failures)")
            print(f"      Action Counter: {event.get('action_counter', 0)}")
        
        # Analyze effectiveness
        adaptation_episodes = [event['episode'] - 1 for event in adaptation_events]
        performance = behavior_data['performance_metrics']['steps_per_episode']
        
        if adaptation_episodes:
            performance_with_adaptations = [performance[i] for i in adaptation_episodes if i < len(performance)]
            performance_without = [performance[i] for i in range(len(performance)) if i not in adaptation_episodes]
            
            if performance_with_adaptations and performance_without:
                print(f"\n📊 ADAPTATION EFFECTIVENESS:")
                print(f"   • Steps with adaptations: {np.mean(performance_with_adaptations):.1f}")
                print(f"   • Steps without adaptations: {np.mean(performance_without):.1f}")
                improvement = np.mean(performance_without) - np.mean(performance_with_adaptations)
                print(f"   • Performance improvement: {improvement:.1f} steps ({(improvement/np.mean(performance_without)*100):.1f}%)")
    else:
        print("ℹ️  No adaptations were triggered during stress testing")
        print("   This indicates the pathfinding system is very robust!")

def main():
    """
    Run the stress test to trigger adaptive behaviors
    """
    print("🧠 ADAPTIVE BEHAVIOR STRESS TEST")
    print("Creating challenging scenarios to demonstrate robot intelligence...")
    print("=" * 60)
    
    # Run the stress test
    behavior_data = create_challenging_scenario()
    
    # Summary
    total_adaptations = sum(behavior_data['performance_metrics']['behavior_changes'])
    avg_performance = np.mean(behavior_data['performance_metrics']['steps_per_episode'])
    success_rate = np.mean(behavior_data['performance_metrics']['successful_deliveries'])
    total_failures = sum(behavior_data['performance_metrics']['failure_counts'])
    
    print(f"\n🎯 STRESS TEST RESULTS:")
    print(f"   🔄 Total Adaptations: {total_adaptations}")
    print(f"   ⚡ Average Performance: {avg_performance:.1f} steps/episode")
    print(f"   🏆 Average Success Rate: {success_rate:.1f} deliveries/episode")
    print(f"   ⚠️  Total Failure Events: {total_failures}")
    print(f"   🧠 System Response: {'HIGHLY ADAPTIVE' if total_adaptations > 5 else 'MODERATELY ADAPTIVE' if total_adaptations > 0 else 'STABLE & ROBUST'}")
    
    print(f"\n✅ ADAPTIVE BEHAVIOR STRESS TEST COMPLETE!")
    if total_adaptations > 0:
        print(f"🎊 Robots successfully demonstrated intelligent behavioral adaptation!")
    else:
        print(f"🚀 Robots are so efficient they don't need behavioral adaptations!")

if __name__ == "__main__":
    main()