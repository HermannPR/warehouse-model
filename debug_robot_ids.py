#!/usr/bin/env python3
"""
Debug robot ID tracking for delivery counting
"""

from warehouse import Warehouse

def debug_robot_ids():
    print("=== Debugging Robot ID Tracking ===")
    
    params = {'config_path': 'layout.json'}
    model = Warehouse(parameters=params)
    model.setup()
    model.training_mode = True
    model.box_respawn_enabled = False
    
    # Limit to 3 robots
    model.robots = model.robots[:3]
    model.setup_episode_based_training()
    
    print(f"Number of robots: {len(model.robots)}")
    print("Robot IDs:")
    for i, robot in enumerate(model.robots):
        robot_id = getattr(robot, 'id', id(robot))
        print(f"  Robot {i}: ID = {robot_id}")
    
    print(f"Robots delivered set: {getattr(model, 'robots_delivered_this_episode', 'Not initialized')}")

if __name__ == "__main__":
    debug_robot_ids()