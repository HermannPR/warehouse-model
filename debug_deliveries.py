#!/usr/bin/env python3
"""
Debug script to understand delivery counting with 2 robots
"""

from warehouse import Warehouse
import numpy as np

def debug_box_counting():
    print("=== Debugging Box Counting with 2 Robots ===")
    
    # Create model with 2 robots
    params = {'config_path': 'layout.json'}
    model = Warehouse(parameters=params)
    model.setup()
    model.training_mode = True
    model.box_respawn_enabled = False
    
    # Limit to 2 robots
    model.robots = model.robots[:2]
    model.setup_episode_based_training()
    
    print(f"Number of robots: {len(model.robots)}")
    print(f"Number of initial boxes: {len(model.boxes)}")
    print(f"Training mode: {model.training_mode}")
    print(f"Box respawn enabled: {model.box_respawn_enabled}")
    
    # Show box positions
    print("\nInitial box positions:")
    for i, box in enumerate(model.boxes):
        if isinstance(box, dict) and 'pos' in box:
            print(f"  Box {i}: {box['pos']}")
    
    # Show robot positions  
    print("\nInitial robot positions:")
    for i, robot in enumerate(model.robots):
        print(f"  Robot {i}: {getattr(robot, 'pos', 'No position')}")
    
    # Simulate an episode step by step and track deliveries
    print("\n=== Simulating Episode ===")
    episode_deliveries = 0
    delivered_boxes_total = set()
    
    for step in range(500):  # Max 500 steps
        model.step()
        
        # Check for deliveries this step
        step_deliveries = getattr(model, '_delivered_this_step', 0)
        if step_deliveries > 0:
            episode_deliveries += step_deliveries
            print(f"Step {step}: {step_deliveries} deliveries (total: {episode_deliveries})")
            
            # Track which boxes have been delivered
            if hasattr(model, 'delivered_boxes'):
                for box_key in model.delivered_boxes:
                    if box_key not in delivered_boxes_total:
                        delivered_boxes_total.add(box_key)
                        print(f"  New delivered box: {box_key}")
        
        # Check episode termination
        if model.check_training_episode_complete():
            print(f"Training episode complete at step {step}!")
            break
    
    print(f"\nFinal episode deliveries: {episode_deliveries}")
    print(f"Total unique boxes delivered: {len(delivered_boxes_total)}")
    print(f"Delivered boxes: {delivered_boxes_total}")
    print(f"Picked boxes remaining: {model.picked_boxes}")
    
    # Check robot delivery counts
    print("\nRobot delivery counts:")
    for i, robot in enumerate(model.robots):
        deliveries = getattr(robot, 'deliveries_this_episode', 0)
        print(f"  Robot {i}: {deliveries} deliveries")
    
    # Check success criteria
    success = model.check_episode_success()
    print(f"\nEpisode success: {success}")

if __name__ == "__main__":
    debug_box_counting()