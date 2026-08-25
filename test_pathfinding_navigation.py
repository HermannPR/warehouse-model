#!/usr/bin/env python3
"""
Test the enhanced pathfinding system to see if robots can navigate around obstacles
"""

from warehouse import train_model_episodic
import matplotlib.pyplot as plt

def test_pathfinding_navigation():
    """Test robots with the new pathfinding system"""
    
    print("🧭 TESTING ENHANCED PATHFINDING NAVIGATION")
    print("=" * 60)
    
    print("🚀 Running training with pathfinding-enhanced robots...")
    
    try:
        # Run training with the enhanced system
        model, history = train_model_episodic(
            episodes=30,
            steps_per_episode=250,
            config_path='layout.json',
            save_every=15
        )
        
        print(f"\n📊 PATHFINDING NAVIGATION TEST RESULTS:")
        
        # Check training performance
        if history and len(history) > 0:
            print(f"✅ Training completed successfully!")
            
            # Get final performance metrics
            final_deliveries = getattr(model, 'episode_delivery_count', 0)
            
            # Test pathfinding functions directly
            print(f"\n🧭 TESTING PATHFINDING FUNCTIONS:")
            
            # Create test scenarios
            test_scenarios = [
                {"start": (2, 2), "goal": (10, 8), "description": "Cross-warehouse navigation"},
                {"start": (5, 5), "goal": (15, 15), "description": "Diagonal navigation"},
                {"start": (1, 10), "goal": (20, 5), "description": "Around obstacles"}
            ]
            
            for i, scenario in enumerate(test_scenarios):
                print(f"\n  📍 Scenario {i+1}: {scenario['description']}")
                print(f"     Start: {scenario['start']} → Goal: {scenario['goal']}")
                
                from warehouse import find_path_around_obstacles, get_next_waypoint_around_obstacles
                
                # Test full pathfinding
                path = find_path_around_obstacles(model, scenario['start'], scenario['goal'])
                if path:
                    print(f"     ✅ Path found: {len(path)} steps")
                    print(f"     🛤️ First 3 waypoints: {path[:3]}")
                else:
                    print(f"     ❌ No path found")
                
                # Test next waypoint
                next_pos = get_next_waypoint_around_obstacles(model, scenario['start'], scenario['goal'])
                if next_pos:
                    print(f"     ➡️ Next step: {next_pos}")
                else:
                    print(f"     ⚠️ No next step available")
            
            # Test robot navigation behavior
            print(f"\n🤖 ROBOT NAVIGATION BEHAVIOR TEST:")
            
            # Reset for testing
            model.setup_episode_based_training()
            
            # Track robot movement over several steps
            initial_positions = {robot.id: robot.position for robot in model.robots}
            
            movement_success = 0
            stuck_incidents = 0
            
            for step in range(20):
                if not model.running:
                    break
                
                positions_before = {robot.id: robot.position for robot in model.robots}
                
                try:
                    model.step()
                    
                    # Check robot movement
                    for robot in model.robots:
                        if robot.id in positions_before:
                            if robot.position != positions_before[robot.id]:
                                movement_success += 1
                            else:
                                # Check if robot tried to move but got stuck
                                if hasattr(robot, 'consecutive_bumps') and robot.consecutive_bumps > 0:
                                    stuck_incidents += 1
                
                except Exception as e:
                    print(f"     ⚠️ Step {step} error: {e}")
                    break
            
            print(f"     ✅ Successful movements: {movement_success}")
            print(f"     🔄 Stuck incidents: {stuck_incidents}")
            
            if stuck_incidents == 0:
                print(f"     🎉 EXCELLENT: No robots got stuck at obstacles!")
            elif stuck_incidents < movement_success // 4:
                print(f"     ✅ GOOD: Low stuck rate, pathfinding is helping")
            else:
                print(f"     ⚠️ MODERATE: Some stuck incidents, may need tuning")
            
            # Overall assessment
            print(f"\n🎯 OVERALL PATHFINDING ASSESSMENT:")
            
            navigation_score = max(0, 100 - (stuck_incidents * 10))
            
            if navigation_score >= 90:
                print(f"✅ EXCELLENT pathfinding! Score: {navigation_score}/100")
                print(f"🧭 Robots successfully navigate around rack lines")
            elif navigation_score >= 70:
                print(f"✅ GOOD pathfinding! Score: {navigation_score}/100") 
                print(f"🧭 Robots mostly avoid getting stuck at obstacles")
            elif navigation_score >= 50:
                print(f"⚠️ MODERATE pathfinding. Score: {navigation_score}/100")
                print(f"🧭 Some improvement, but may need further tuning")
            else:
                print(f"❌ POOR pathfinding. Score: {navigation_score}/100")
                print(f"🧭 Robots still having trouble with obstacle navigation")
            
            return {
                'navigation_score': navigation_score,
                'movement_success': movement_success,
                'stuck_incidents': stuck_incidents,
                'pathfinding_working': stuck_incidents < movement_success // 3
            }
        
        else:
            print("❌ No training history available")
            return None
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None

if __name__ == "__main__":
    results = test_pathfinding_navigation()
    
    if results:
        print(f"\n📋 FINAL SUMMARY:")
        if results['pathfinding_working']:
            print(f"✅ Pathfinding system is working! Robots can navigate around obstacles.")
            print(f"📈 Navigation score: {results['navigation_score']}/100")
        else:
            print(f"❌ Pathfinding needs more work. Check obstacle detection and path planning.")
    else:
        print(f"❌ Unable to complete pathfinding test")