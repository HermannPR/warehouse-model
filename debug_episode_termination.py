#!/usr/bin/env python3
"""
Debug why episodes are ending immediately with 0 steps
"""

from warehouse import Warehouse

def debug_episode_termination():
    """Debug what's causing episodes to end immediately"""
    
    print("🔍 DEBUGGING EPISODE TERMINATION")
    print("=" * 50)
    
    # Create a simple model
    model = Warehouse(
        width=25, height=25, 
        n_robots=2, 
        n_boxes=10, 
        episode_limit=100,
        training_mode=True
    )
    
    print(f"🎯 Training mode: {getattr(model, 'training_mode', 'not set')}")
    print(f"🏃 Running state: {model.running}")
    
    # Setup model
    model.setup()
    print(f"🏃 After setup - Running state: {model.running}")
    print(f"📦 Number of boxes: {len([a for a in model.agents if hasattr(a, 'box_location')])}")
    print(f"🤖 Number of robots: {len(model.robots)}")
    
    # Check initial state
    print(f"📍 Robot positions: {[robot.position for robot in model.robots]}")
    print(f"🎯 Robot missions: {[getattr(robot, 'mission', 'no mission') for robot in model.robots]}")
    print(f"📊 Episode delivery count: {getattr(model, 'episode_delivery_count', 'not set')}")
    
    # Try to run a few steps and see what happens
    for step in range(5):
        if not model.running:
            print(f"❌ Model stopped running at step {step}")
            print(f"🔍 Checking why...")
            
            # Check episode completion conditions
            if hasattr(model, 'check_training_episode_complete'):
                complete = model.check_training_episode_complete()
                print(f"📋 Training episode complete: {complete}")
            
            if hasattr(model, 'episode_delivery_count'):
                print(f"📦 Deliveries: {model.episode_delivery_count}")
                print(f"🎯 Target deliveries: {len(model.robots)}")
            
            break
        
        print(f"\n--- Step {step + 1} ---")
        print(f"🏃 Before step - Running: {model.running}")
        
        try:
            model.step()
            print(f"✅ Step completed successfully")
            print(f"🏃 After step - Running: {model.running}")
            print(f"📦 Deliveries this step: {getattr(model, '_delivered_this_step', 'not tracked')}")
            print(f"📊 Total episode deliveries: {getattr(model, 'episode_delivery_count', 'not tracked')}")
            
        except Exception as e:
            print(f"❌ Error during step: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"\n📊 Final state:")
    print(f"🏃 Running: {model.running}")
    print(f"📦 Episode deliveries: {getattr(model, 'episode_delivery_count', 'not tracked')}")
    print(f"📍 Robot positions: {[robot.position for robot in model.robots]}")

if __name__ == "__main__":
    debug_episode_termination()