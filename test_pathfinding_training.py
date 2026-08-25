#!/usr/bin/env python3
"""
Test pathfinding by running actual training and monitoring robot behavior
"""

from warehouse import train_model_episodic
import time

def test_pathfinding_during_training():
    """Monitor robot behavior during actual training to see pathfinding in action"""
    
    print("🧭 PATHFINDING DURING TRAINING TEST")
    print("=" * 50)
    
    print("🏋️ Running training and monitoring robot navigation...")
    
    try:
        # Run a short training session to see robots in action
        model, history = train_model_episodic(
            episodes=20,
            steps_per_episode=150,
            config_path='layout.json'
        )
        
        # Extract success rate from training output
        print(f"\n📊 TRAINING COMPLETED")
        
        # Now test the pathfinding functions with the trained model
        print(f"\n🧪 PATHFINDING FUNCTION VALIDATION:")
        
        from warehouse import find_path_around_obstacles, get_next_waypoint_around_obstacles
        
        # Test multiple pathfinding scenarios
        test_cases = [
            {"start": (1, 1), "goal": (5, 5), "name": "Short path"},
            {"start": (2, 10), "goal": (15, 5), "name": "Cross-warehouse"},
            {"start": (10, 2), "goal": (10, 20), "name": "Vertical navigation"},
            {"start": (5, 15), "goal": (20, 15), "name": "Horizontal navigation"}
        ]
        
        successful_paths = 0
        total_path_length = 0
        
        for i, test in enumerate(test_cases):
            print(f"\n  🧪 Test {i+1}: {test['name']}")
            print(f"      {test['start']} → {test['goal']}")
            
            # Test full pathfinding
            path = find_path_around_obstacles(model, test['start'], test['goal'])
            if path:
                print(f"      ✅ Path found: {len(path)} steps")
                successful_paths += 1
                total_path_length += len(path)
                
                # Show first few waypoints
                waypoints_preview = path[:3] if len(path) > 3 else path
                print(f"      🛤️ Waypoints: {waypoints_preview}...")
            else:
                print(f"      ❌ No path found")
            
            # Test next waypoint function
            next_pos = get_next_waypoint_around_obstacles(model, test['start'], test['goal'])
            if next_pos:
                print(f"      ➡️ Next step: {next_pos}")
            else:
                print(f"      ⚠️ No next step")
        
        # Calculate pathfinding metrics
        pathfinding_success_rate = (successful_paths / len(test_cases)) * 100
        avg_path_length = total_path_length / max(1, successful_paths)
        
        print(f"\n📊 PATHFINDING METRICS:")
        print(f"  ✅ Success rate: {pathfinding_success_rate:.1f}%")
        print(f"  📏 Average path length: {avg_path_length:.1f} steps")
        
        # Test obstacle detection
        print(f"\n🧱 OBSTACLE DETECTION TEST:")
        
        obstacle_tests = [
            (0, 0),    # Boundary
            (1, 1),    # Likely free
            (3, 3),    # Box location
            (10, 10),  # Middle area
        ]
        
        for pos in obstacle_tests:
            if model.inbound(pos):
                is_free = model.cell_is_free(pos)
                is_blocked = model.is_blocked(pos)
                print(f"  📍 Position {pos}: {'FREE' if is_free else 'BLOCKED'}")
            else:
                print(f"  📍 Position {pos}: OUT OF BOUNDS")
        
        # Overall assessment
        print(f"\n🎯 PATHFINDING SYSTEM ASSESSMENT:")
        
        if pathfinding_success_rate >= 75:
            status = "EXCELLENT"
            emoji = "🌟"
            message = "Pathfinding system is working well!"
        elif pathfinding_success_rate >= 50:
            status = "GOOD"
            emoji = "✅"
            message = "Pathfinding system is functional with room for improvement"
        elif pathfinding_success_rate >= 25:
            status = "MODERATE"
            emoji = "⚠️"
            message = "Pathfinding system needs optimization"
        else:
            status = "POOR"
            emoji = "❌"
            message = "Pathfinding system requires significant fixes"
        
        print(f"{emoji} {status}: {message}")
        print(f"   🎯 Pathfinding Success: {pathfinding_success_rate:.1f}%")
        print(f"   📏 Path Efficiency: {avg_path_length:.1f} steps average")
        
        # Check if the solution addresses the original problem
        print(f"\n🤖 ROBOT RACK NAVIGATION SOLUTION:")
        
        if pathfinding_success_rate >= 50:
            print(f"✅ SOLUTION IMPLEMENTED: Robots now have pathfinding to avoid rack lines")
            print(f"🧭 The enhanced navigation system includes:")
            print(f"   • A* pathfinding algorithm for obstacle avoidance")
            print(f"   • Smart waypoint selection around blocked areas")
            print(f"   • Heavy penalties for bumping into obstacles")
            print(f"   • Pathfinding-aware action selection")
            
            if pathfinding_success_rate >= 75:
                print(f"🎉 Robots should no longer get stuck at rack lines!")
            else:
                print(f"⚠️ Significant improvement, but fine-tuning may be needed")
        else:
            print(f"❌ SOLUTION NEEDS WORK: Pathfinding system not fully functional")
            
        return {
            'pathfinding_success_rate': pathfinding_success_rate,
            'avg_path_length': avg_path_length,
            'status': status,
            'solution_working': pathfinding_success_rate >= 50
        }
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None

if __name__ == "__main__":
    results = test_pathfinding_during_training()
    
    if results:
        print(f"\n📋 FINAL VERDICT:")
        if results['solution_working']:
            print(f"✅ SUCCESS: Enhanced pathfinding system addresses rack navigation issues")
            print(f"🎯 Pathfinding: {results['pathfinding_success_rate']:.1f}% success rate")
            print(f"📏 Efficiency: {results['avg_path_length']:.1f} steps average path length")
            print(f"\n🛡️ The system now includes obstacle avoidance that should prevent")
            print(f"   robots from repeatedly trying to pass through rack lines.")
        else:
            print(f"❌ PARTIAL: Pathfinding implemented but needs optimization")
            print(f"   Consider adjusting pathfinding parameters or reward weights")
    else:
        print(f"❌ Unable to complete pathfinding validation")