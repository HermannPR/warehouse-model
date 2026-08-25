#!/usr/bin/env python3
"""
Debug training episode termination in detail
"""

from warehouse import Warehouse

def debug_training_termination():
    print("=== Debugging Training Episode Termination ===")
    
    # Create model with 2 robots in training mode
    params = {'config_path': 'layout.json'}
    model = Warehouse(parameters=params)
    model.setup()
    model.training_mode = True
    model.box_respawn_enabled = False
    model.robots = model.robots[:2]
    model.setup_episode_based_training()
    
    print(f"Training mode: {model.training_mode}")
    print(f"Number of robots: {len(model.robots)}")
    
    episode_deliveries = 0
    robot_deliveries = [0, 0]
    
    for step in range(300):  # Max steps
        model.step()
        
        # Track deliveries this step
        step_deliveries = getattr(model, '_delivered_this_step', 0)
        if step_deliveries > 0:
            episode_deliveries += step_deliveries
            
            # Update robot delivery counts
            for i, robot in enumerate(model.robots):
                current_deliveries = getattr(robot, 'deliveries_this_episode', 0)
                robot_deliveries[i] = current_deliveries
            
            print(f"Step {step}: +{step_deliveries} deliveries (total: {episode_deliveries})")
            print(f"  Robot deliveries: {robot_deliveries}")
            
            # Check termination condition
            complete = model.check_training_episode_complete()
            success = model.check_episode_success()
            print(f"  Training complete: {complete}, Episode success: {success}")
            
            if complete:
                print(f"Episode terminated at step {step}")
                break
    
    print(f"\nFinal results:")
    print(f"  Episode deliveries: {episode_deliveries}")
    print(f"  Robot deliveries: {robot_deliveries}")
    print(f"  Episode success: {model.check_episode_success()}")

if __name__ == "__main__":
    debug_training_termination()