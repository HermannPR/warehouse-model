#!/usr/bin/env python3
"""
Test multiple training episodes to match actual training behavior
"""

from warehouse import Warehouse
import numpy as np

def test_multiple_episodes(n_episodes=5):
    print(f"=== Testing {n_episodes} Training Episodes ===")
    
    all_deliveries = []
    
    for episode in range(n_episodes):
        print(f"\n--- Episode {episode + 1} ---")
        
        # Create fresh model for each episode (like in train_model_episodic)
        params = {'config_path': 'layout.json'}
        model = Warehouse(parameters=params)
        model.setup()
        model.auto_cycle_reset = False
        
        # Limit to 2 robots
        model.robots = model.robots[:2]
        
        model.setup_episode_based_training()
        # Set training mode flags
        model.training_mode = True
        model.box_respawn_enabled = False
        
        print(f"  Training mode: {model.training_mode}")
        print(f"  Box respawn: {model.box_respawn_enabled}")
        print(f"  Robots: {len(model.robots)}")
        
        episode_deliveries = 0
        
        for step in range(250):  # Max steps per episode
            model.step()
            
            step_deliveries = getattr(model, '_delivered_this_step', 0)
            if step_deliveries > 0:
                episode_deliveries += step_deliveries
                print(f"  Step {step}: +{step_deliveries} deliveries (total: {episode_deliveries})")
            
            # Check termination
            if model.check_training_episode_complete():
                print(f"  Episode complete at step {step}")
                break
        
        all_deliveries.append(episode_deliveries)
        print(f"  Final deliveries: {episode_deliveries}")
        print(f"  Success: {model.check_episode_success()}")
    
    print(f"\n=== Summary ===")
    print(f"Deliveries per episode: {all_deliveries}")
    print(f"Average deliveries: {np.mean(all_deliveries):.2f}")
    print(f"Max deliveries: {max(all_deliveries)}")
    print(f"Min deliveries: {min(all_deliveries)}")

if __name__ == "__main__":
    test_multiple_episodes()