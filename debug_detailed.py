#!/usr/bin/env python3
"""
Detailed debug of delivery and termination timing
"""

from warehouse import Warehouse

def debug_detailed_termination():
    print("=== Detailed Termination Debug ===")
    
    params = {'config_path': 'layout.json'}
    model = Warehouse(parameters=params)
    model.setup()
    model.training_mode = True
    model.box_respawn_enabled = False
    model.robots = model.robots[:2]
    model.setup_episode_based_training()
    
    # Add debug prints to the model
    original_handle_delivery = model.handle_box_delivery
    def debug_handle_delivery(robot, box_location):
        print(f"    DELIVERY ATTEMPT: Robot delivering to {box_location}")
        print(f"    Episode terminated: {getattr(model, 'episode_terminated', False)}")
        result = original_handle_delivery(robot, box_location)
        print(f"    After delivery - Episode terminated: {getattr(model, 'episode_terminated', False)}")
        return result
    model.handle_box_delivery = debug_handle_delivery
    
    episode_deliveries = 0
    robot_deliveries = [0, 0]
    
    for step in range(100):
        print(f"\nStep {step}:")
        
        # Check status before step
        print(f"  Before step - Episode terminated: {getattr(model, 'episode_terminated', False)}")
        
        model.step()
        
        # Check deliveries after step
        step_deliveries = getattr(model, '_delivered_this_step', 0)
        if step_deliveries > 0:
            episode_deliveries += step_deliveries
            
            # Update robot delivery counts
            for i, robot in enumerate(model.robots):
                current_deliveries = getattr(robot, 'deliveries_this_episode', 0)
                robot_deliveries[i] = current_deliveries
            
            print(f"  After step - Deliveries this step: {step_deliveries}")
            print(f"  Total deliveries: {episode_deliveries}")
            print(f"  Robot deliveries: {robot_deliveries}")
        
        # Check termination
        terminated = getattr(model, 'episode_terminated', False)
        complete = model.check_training_episode_complete()
        print(f"  Episode terminated flag: {terminated}")
        print(f"  Training complete: {complete}")
        
        if terminated or complete:
            print(f"Episode should end at step {step}")
            break
    
    print(f"\nFinal: {episode_deliveries} deliveries, Robot counts: {robot_deliveries}")

if __name__ == "__main__":
    debug_detailed_termination()