#!/usr/bin/env python3
"""
Direct test of robot navigation behavior around obstacles
"""

from warehouse import Warehouse
import matplotlib.pyplot as plt
import numpy as np

def test_robot_obstacle_navigation():
    """Test robots navigating around actual obstacles in the warehouse"""
    
    print("🤖 DIRECT ROBOT OBSTACLE NAVIGATION TEST")
    print("=" * 60)
    
    # Create a warehouse model
    model = Warehouse(
        width=25, height=25,
        n_robots=2,
        n_boxes=3,
        training_mode=True
    )
    model.setup()
    
    print(f"🏭 Created warehouse: {model.W}x{model.H}")
    print(f"🤖 Robots: {len(model.robots)}")
    print(f"📦 Boxes: {len(getattr(model, 'boxes', []))}")
    
    # Test robot navigation behavior
    print(f"\n🧭 TESTING ROBOT NAVIGATION:")
    
    navigation_results = []
    
    # Run multiple short episodes to test navigation
    for episode in range(5):
        print(f"\n  Episode {episode + 1}:")
        
        # Reset episode
        model.setup_episode_based_training()
        
        # Track robot positions and movements
        movement_data = {
            'successful_moves': 0,
            'blocked_attempts': 0, 
            'path_changes': 0,
            'unique_positions': set()
        }
        
        # Run episode for limited steps
        for step in range(50):
            if not model.running:
                break
            
            # Track positions before step
            positions_before = {robot.id: robot.position for robot in model.robots}
            
            try:
                model.step()
                
                # Analyze robot movements
                for robot in model.robots:
                    if robot.id in positions_before:
                        prev_pos = positions_before[robot.id]
                        curr_pos = robot.position
                        
                        # Track unique positions visited
                        movement_data['unique_positions'].add(curr_pos)
                        
                        if curr_pos != prev_pos:
                            movement_data['successful_moves'] += 1
                            
                            # Check if robot changed direction (indicating path planning)
                            if hasattr(robot, 'last_direction'):
                                new_direction = (curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1])
                                if new_direction != robot.last_direction:
                                    movement_data['path_changes'] += 1
                                robot.last_direction = new_direction
                            else:
                                robot.last_direction = (curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1])
                        else:
                            # Robot tried to move but stayed in place (likely blocked)
                            if hasattr(robot, 'proposal') and robot.proposal in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                                movement_data['blocked_attempts'] += 1
                                
            except Exception as e:
                print(f"    ⚠️ Step {step} error: {e}")
                break
        
        # Calculate episode metrics
        total_attempts = movement_data['successful_moves'] + movement_data['blocked_attempts']
        success_rate = (movement_data['successful_moves'] / max(1, total_attempts)) * 100
        exploration_score = len(movement_data['unique_positions'])
        
        print(f"    ✅ Successful moves: {movement_data['successful_moves']}")
        print(f"    ❌ Blocked attempts: {movement_data['blocked_attempts']}")
        print(f"    🔄 Path changes: {movement_data['path_changes']}")
        print(f"    🗺️ Unique positions: {exploration_score}")
        print(f"    📊 Success rate: {success_rate:.1f}%")
        
        navigation_results.append({
            'episode': episode + 1,
            'success_rate': success_rate,
            'blocked_attempts': movement_data['blocked_attempts'],
            'path_changes': movement_data['path_changes'],
            'exploration': exploration_score
        })
    
    # Analyze overall results
    print(f"\n📊 NAVIGATION ANALYSIS:")
    
    avg_success_rate = np.mean([r['success_rate'] for r in navigation_results])
    total_blocked = sum([r['blocked_attempts'] for r in navigation_results])
    total_path_changes = sum([r['path_changes'] for r in navigation_results])
    avg_exploration = np.mean([r['exploration'] for r in navigation_results])
    
    print(f"  📈 Average success rate: {avg_success_rate:.1f}%")
    print(f"  🚫 Total blocked attempts: {total_blocked}")
    print(f"  🔄 Total path changes: {total_path_changes}")
    print(f"  🗺️ Average exploration: {avg_exploration:.1f} positions")
    
    # Test specific pathfinding scenarios
    print(f"\n🧪 PATHFINDING FUNCTION TESTS:")
    
    from warehouse import find_path_around_obstacles, get_next_waypoint_around_obstacles
    
    # Test pathfinding around warehouse obstacles
    robot_pos = model.robots[0].position if model.robots else (5, 5)
    
    # Find a box position as target
    boxes = getattr(model, 'boxes', [])
    if boxes and isinstance(boxes[0], dict) and 'pos' in boxes[0]:
        target_pos = boxes[0]['pos'][:2]
        
        print(f"  📍 Robot at: {robot_pos}")
        print(f"  🎯 Target at: {target_pos}")
        
        # Test pathfinding
        path = find_path_around_obstacles(model, robot_pos, target_pos)
        if path:
            print(f"  ✅ Path found: {len(path)} steps")
            print(f"  🛤️ Path: {path[:5]}{'...' if len(path) > 5 else ''}")
        else:
            print(f"  ❌ No path found")
        
        # Test next waypoint
        next_waypoint = get_next_waypoint_around_obstacles(model, robot_pos, target_pos)
        if next_waypoint:
            print(f"  ➡️ Next waypoint: {next_waypoint}")
        else:
            print(f"  ⚠️ No next waypoint")
    
    # Overall assessment
    print(f"\n🎯 OBSTACLE NAVIGATION ASSESSMENT:")
    
    if avg_success_rate >= 85 and total_blocked <= 10:
        status = "EXCELLENT"
        color = "✅"
    elif avg_success_rate >= 70 and total_blocked <= 20:
        status = "GOOD"  
        color = "✅"
    elif avg_success_rate >= 50:
        status = "MODERATE"
        color = "⚠️"
    else:
        status = "POOR"
        color = "❌"
    
    print(f"{color} {status} obstacle navigation!")
    print(f"   Success Rate: {avg_success_rate:.1f}%")
    print(f"   Blocked Attempts: {total_blocked}")
    print(f"   Path Adaptation: {total_path_changes} changes")
    
    if total_blocked <= 5:
        print(f"🎉 Robots are successfully avoiding rack lines and obstacles!")
    elif total_blocked <= 15:
        print(f"✅ Robots mostly navigate around obstacles with some minor issues")
    else:
        print(f"⚠️ Robots still having trouble navigating around obstacles")
    
    return {
        'success_rate': avg_success_rate,
        'blocked_attempts': total_blocked,
        'path_changes': total_path_changes,
        'status': status
    }

if __name__ == "__main__":
    results = test_robot_obstacle_navigation()
    
    print(f"\n📋 SUMMARY:")
    print(f"Navigation Status: {results['status']}")
    print(f"Success Rate: {results['success_rate']:.1f}%")
    
    if results['blocked_attempts'] <= 10 and results['success_rate'] >= 70:
        print(f"✅ SOLUTION WORKING: Robots can navigate around rack lines!")
    else:
        print(f"⚠️ NEEDS IMPROVEMENT: Further pathfinding optimization required")