#!/usr/bin/env python3
"""
Diagnose why win rate is similar at start and end of training
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def diagnose_win_rate_pattern(metrics_dir="metrics_out"):
    """Analyze why win rate starts and ends at similar levels"""
    
    per_episode_file = os.path.join(metrics_dir, "per_episode.csv")
    if not os.path.exists(per_episode_file):
        print(f"Error: {per_episode_file} not found!")
        return
    
    df = pd.read_csv(per_episode_file)
    episodes = df['episode'].values
    success = df['success'].values
    rewards = df['total_reward'].values
    deliveries = df['deliveries'].values
    
    total_episodes = len(episodes)
    
    # Divide training into phases
    phase_size = total_episodes // 10  # 10 phases of equal size
    phases = []
    phase_labels = []
    
    for i in range(10):
        start_idx = i * phase_size
        end_idx = (i + 1) * phase_size if i < 9 else total_episodes
        phase_data = {
            'phase': i + 1,
            'episodes': f"{start_idx + 1}-{end_idx}",
            'win_rate': np.mean(success[start_idx:end_idx]),
            'avg_reward': np.mean(rewards[start_idx:end_idx]),
            'avg_deliveries': np.mean(deliveries[start_idx:end_idx]),
            'successful_episodes': np.sum(success[start_idx:end_idx]),
            'failed_episodes': np.sum(1 - success[start_idx:end_idx]),
            'reward_variance': np.var(rewards[start_idx:end_idx]),
            'success_variance': np.var(success[start_idx:end_idx])
        }
        phases.append(phase_data)
        phase_labels.append(f"Phase {i+1}")
    
    # Create comprehensive diagnostic plots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Win Rate by Phase
    win_rates = [p['win_rate'] for p in phases]
    ax1.plot(range(1, 11), win_rates, 'o-', linewidth=2, markersize=8, color='blue')
    ax1.axhline(y=win_rates[0], color='red', linestyle='--', alpha=0.7, label=f'Start: {win_rates[0]:.1%}')
    ax1.axhline(y=win_rates[-1], color='green', linestyle='--', alpha=0.7, label=f'End: {win_rates[-1]:.1%}')
    ax1.set_title('Win Rate Progression by Training Phase', fontweight='bold', fontsize=14)
    ax1.set_xlabel('Training Phase (10% intervals)')
    ax1.set_ylabel('Win Rate')
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # 2. Average Rewards by Phase
    avg_rewards = [p['avg_reward'] for p in phases]
    ax2.plot(range(1, 11), avg_rewards, 'o-', linewidth=2, markersize=8, color='orange')
    ax2.set_title('Average Reward by Training Phase', fontweight='bold', fontsize=14)
    ax2.set_xlabel('Training Phase')
    ax2.set_ylabel('Average Reward')
    ax2.grid(True, alpha=0.3)
    
    # 3. Success vs Failure Count by Phase
    successful_counts = [p['successful_episodes'] for p in phases]
    failed_counts = [p['failed_episodes'] for p in phases]
    
    x_pos = np.arange(1, 11)
    ax3.bar(x_pos - 0.2, successful_counts, 0.4, label='Successful Episodes', color='green', alpha=0.7)
    ax3.bar(x_pos + 0.2, failed_counts, 0.4, label='Failed Episodes', color='red', alpha=0.7)
    ax3.set_title('Success vs Failure Count by Phase', fontweight='bold', fontsize=14)
    ax3.set_xlabel('Training Phase')
    ax3.set_ylabel('Episode Count')
    ax3.legend()
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Reward Variance (Learning Stability)
    reward_variances = [p['reward_variance'] for p in phases]
    ax4.plot(range(1, 11), reward_variances, 'o-', linewidth=2, markersize=8, color='purple')
    ax4.set_title('Reward Variance by Phase (Learning Stability)', fontweight='bold', fontsize=14)
    ax4.set_xlabel('Training Phase')
    ax4.set_ylabel('Reward Variance')
    ax4.grid(True, alpha=0.3)
    
    plt.suptitle('Training Diagnosis: Why Win Rate Starts and Ends Similar', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig('training_diagnosis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Print detailed analysis
    print("="*60)
    print("🔍 TRAINING DIAGNOSIS: WIN RATE PATTERN ANALYSIS")
    print("="*60)
    
    print(f"\n📊 PHASE-BY-PHASE BREAKDOWN:")
    print("-" * 60)
    for phase in phases:
        print(f"Phase {phase['phase']:2d} (Episodes {phase['episodes']:>9}): "
              f"Win Rate: {phase['win_rate']:.1%} | "
              f"Avg Reward: {phase['avg_reward']:6.1f} | "
              f"Deliveries: {phase['avg_deliveries']:.2f}")
    
    # Calculate key insights
    start_win_rate = win_rates[0]
    end_win_rate = win_rates[-1]
    max_win_rate = max(win_rates)
    min_win_rate = min(win_rates)
    peak_phase = win_rates.index(max_win_rate) + 1
    
    print(f"\n🎯 KEY FINDINGS:")
    print("-" * 60)
    print(f"Start Win Rate:     {start_win_rate:.1%}")
    print(f"End Win Rate:       {end_win_rate:.1%}")
    print(f"Peak Win Rate:      {max_win_rate:.1%} (Phase {peak_phase})")
    print(f"Lowest Win Rate:    {min_win_rate:.1%}")
    print(f"Total Variation:    {max_win_rate - min_win_rate:.1%}")
    
    # Analyze possible causes
    print(f"\n🧠 POSSIBLE EXPLANATIONS:")
    print("-" * 60)
    
    # 1. Check if task is naturally easy
    if start_win_rate > 0.7:
        print("✅ TASK DIFFICULTY: The warehouse task may be naturally well-suited to")
        print("   random/simple policies, leading to high initial success rates.")
    
    # 2. Check for learning plateau
    if abs(end_win_rate - start_win_rate) < 0.05:
        print("📈 LEARNING PLATEAU: Win rate stabilized early, suggesting either:")
        print("   • Task complexity is well-matched to model capacity")
        print("   • Optimal coordination strategy was learned quickly")
    
    # 3. Check reward progression
    start_reward = avg_rewards[0]
    end_reward = avg_rewards[-1]
    if end_reward > start_reward:
        print("💰 REWARD IMPROVEMENT: Even with similar win rates, average rewards")
        print(f"   improved from {start_reward:.1f} to {end_reward:.1f}, indicating")
        print("   more efficient/faster task completion.")
    
    # 4. Check for epsilon decay effect
    print("🎲 EPSILON DECAY: High exploration (ε) early in training may have")
    print("   accidentally led to good coordination through random actions.")
    
    # 5. Analyze variance
    start_variance = reward_variances[0]
    end_variance = reward_variances[-1]
    if end_variance < start_variance:
        print("📊 CONSISTENCY IMPROVEMENT: Reward variance decreased from")
        print(f"   {start_variance:.1f} to {end_variance:.1f}, showing more stable performance.")
    
    # 6. Check for early stopping potential
    if max_win_rate > 0.9 and max_win_rate - end_win_rate > 0.1:
        print("⚠️  POTENTIAL OVERFITTING: Peak performance was higher than final,")
        print("   suggesting possible overfitting or need for early stopping.")
    
    print(f"\n🔬 TRAINING CHARACTERISTICS:")
    print("-" * 60)
    
    # Calculate learning speed
    first_half_avg = np.mean(win_rates[:5])
    second_half_avg = np.mean(win_rates[5:])
    
    if abs(first_half_avg - second_half_avg) < 0.03:
        print("🚀 FAST INITIAL LEARNING: The model learned effective coordination")
        print("   strategies very quickly, then maintained stable performance.")
    
    # Success pattern analysis
    total_successful = sum(p['successful_episodes'] for p in phases)
    total_failed = sum(p['failed_episodes'] for p in phases)
    
    print(f"📈 OVERALL PERFORMANCE:")
    print(f"   • Total Successful Episodes: {total_successful:,}/{total_episodes:,} ({total_successful/total_episodes:.1%})")
    print(f"   • Total Failed Episodes: {total_failed:,}/{total_episodes:,} ({total_failed/total_episodes:.1%})")
    print(f"   • Performance Stability: {'High' if max_win_rate - min_win_rate < 0.15 else 'Moderate'}")
    
    return phases

if __name__ == "__main__":
    phases = diagnose_win_rate_pattern()
    print(f"\n✅ Training diagnosis complete! Check 'training_diagnosis.png' for visual analysis.")