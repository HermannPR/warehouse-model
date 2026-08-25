#!/usr/bin/env python3
"""
Reward Analysis and Diagnostic Tool

This script analyzes the current reward structure and identifies potential 
improvements for robot behavior near boxes and goals.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from warehouse import Warehouse
import numpy as np

def analyze_reward_structure():
    """Analyze current reward values and identify issues"""
    
    print("=== CURRENT REWARD STRUCTURE ANALYSIS ===")
    print()
    
    # Import current constants
    from config_constants import (
        R_STEP, R_SHAPING_K, R_PICKUP, R_DROP, R_RECHARGE,
        R_BUMP, R_CONFLICT, LOW_BATT_THR, R_LOW_BATT
    )
    
    print("Current Reward Values:")
    print(f"  R_STEP (per step): {R_STEP}")
    print(f"  R_SHAPING_K (distance shaping): {R_SHAPING_K}")
    print(f"  R_PICKUP (successful pickup): {R_PICKUP}")
    print(f"  R_DROP (successful delivery): {R_DROP}")
    print(f"  R_RECHARGE: {R_RECHARGE}")
    print(f"  R_BUMP (hitting wall/obstacle): {R_BUMP}")
    print(f"  R_CONFLICT (forced wait): {R_CONFLICT}")
    print(f"  R_LOW_BATT (low battery penalty): {R_LOW_BATT}")
    print()
    
    print("=== IDENTIFIED ISSUES ===")
    print()
    
    print("1. WEAK DISTANCE SHAPING:")
    print(f"   - Current R_SHAPING_K = {R_SHAPING_K}")
    print("   - For a robot 10 cells away from goal, moving 1 cell closer gives:")
    print(f"     Reward = {R_SHAPING_K} * (10 - 9) = {R_SHAPING_K * 1}")
    print("   - This is very weak compared to step penalty of", R_STEP)
    print("   - Robot gets more penalty per step than benefit from approaching!")
    print()
    
    print("2. APPROACH INCENTIVES:")
    print(f"   - Current approach bonus for moving closer to box: +0.2")
    print("   - But step penalty is", R_STEP, "so net benefit is only", 0.2 + R_STEP)
    print("   - This might not be enough to encourage active seeking")
    print()
    
    print("3. GUIDANCE LINE REWARDS:")
    print("   - Current guidance line bonus: +0.4")
    print("   - But if robot doesn't reach goal quickly, accumulates step penalties")
    print("   - May need stronger incentives for efficient pathfinding")
    print()
    
    print("=== RECOMMENDED IMPROVEMENTS ===")
    print()
    
    print("1. STRONGER DISTANCE SHAPING:")
    print("   - Increase R_SHAPING_K from 0.1 to 0.3-0.5")
    print("   - This makes getting closer more rewarding than step penalty")
    print()
    
    print("2. PROGRESSIVE PROXIMITY BONUS:")
    print("   - Add escalating bonuses as robot gets very close to target")
    print("   - E.g., +0.5 when within 3 cells, +1.0 when within 1 cell")
    print()
    
    print("3. EFFICIENCY REWARDS:")
    print("   - Bonus for taking shortest path actions")
    print("   - Penalty for inefficient moves (moving away from target)")
    print()
    
    print("4. ACTION SUCCESS AMPLIFICATION:")
    print("   - Current pickup reward:", R_PICKUP)
    print("   - Current drop reward:", R_DROP)
    print("   - These are good but need better approach incentives")
    print()

def simulate_reward_scenarios():
    """Simulate different reward scenarios to show the impact"""
    
    print("=== REWARD SCENARIO SIMULATION ===")
    print()
    
    # Current values
    from config_constants import R_STEP, R_SHAPING_K, R_PICKUP, R_DROP
    
    scenarios = [
        ("Robot 5 cells from box, moves 1 closer", R_STEP + R_SHAPING_K * 1),
        ("Robot 2 cells from box, moves 1 closer", R_STEP + R_SHAPING_K * 1 + 0.2),  # approach bonus
        ("Robot picks up box", R_PICKUP),
        ("Robot 3 cells from drop, moves 1 closer", R_STEP + R_SHAPING_K * 1),
        ("Robot delivers box", R_DROP),
        ("Robot waits (no progress)", R_STEP),
        ("Robot moves away from target", R_STEP + R_SHAPING_K * (-1))
    ]
    
    print("Current Reward Scenarios:")
    for description, reward in scenarios:
        print(f"  {description:40} = {reward:+6.2f}")
    print()
    
    # Improved values simulation
    print("With Improved Reward Structure:")
    R_SHAPING_K_NEW = 0.4
    scenarios_improved = [
        ("Robot 5 cells from box, moves 1 closer", R_STEP + R_SHAPING_K_NEW * 1),
        ("Robot 2 cells from box, moves 1 closer", R_STEP + R_SHAPING_K_NEW * 1 + 0.5),  # stronger approach
        ("Robot 1 cell from box, moves adjacent", R_STEP + R_SHAPING_K_NEW * 1 + 1.0),   # proximity bonus
        ("Robot picks up box", R_PICKUP + 2.0),  # success amplification
        ("Robot 3 cells from drop, moves 1 closer", R_STEP + R_SHAPING_K_NEW * 1),
        ("Robot delivers box", R_DROP + 3.0),  # delivery amplification
        ("Robot waits (no progress)", R_STEP - 0.1),  # extra wait penalty
        ("Robot moves away from target", R_STEP + R_SHAPING_K_NEW * (-1) - 0.2)  # inefficiency penalty
    ]
    
    for description, reward in scenarios_improved:
        print(f"  {description:40} = {reward:+6.2f}")
    print()

if __name__ == "__main__":
    analyze_reward_structure()
    print()
    simulate_reward_scenarios()
    print()
    print("=== NEXT STEPS ===")
    print("1. Update config_constants.py with improved reward values")
    print("2. Add proximity bonus system to reward_fun()")
    print("3. Test with short training episodes")
    print("4. Monitor robot behavior improvements")