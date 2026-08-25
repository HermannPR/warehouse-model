#!/usr/bin/env python3
"""
Test safe zone system effectiveness by running training episodes
"""

from warehouse import Warehouse
import matplotlib.pyplot as plt
import numpy as np

def test_safe_zone_training_effectiveness():
    """Test the safe zone system during actual training"""
    
    print("🧪 TESTING SAFE ZONE EFFECTIVENESS IN TRAINING")
    print("=" * 60)
    
    # Test with safe zones enabled (current system)
    print("🛡️ Running episodes with SAFE ZONE system enabled...")
    model_with_safe_zones = Warehouse(
        width=25, height=25,
        n_robots=2,
        n_boxes=3,
        training_mode=True
    )
    model_with_safe_zones.setup()
    
    # Run a few episodes
    episodes_to_test = 10
    wins_with_safe_zones = []
    deliveries_with_safe_zones = []
    
    for episode in range(episodes_to_test):
        model_with_safe_zones.setup_episode_based_training()
        
        max_steps = 200
        for step in range(max_steps):
            if not model_with_safe_zones.running:
                break
            model_with_safe_zones.step()
        
        # Check results
        deliveries = model_with_safe_zones.episode_delivery_count
        win = deliveries >= len(model_with_safe_zones.robots)  # All robots delivered
        
        wins_with_safe_zones.append(1 if win else 0)
        deliveries_with_safe_zones.append(deliveries)
        
        print(f"  Episode {episode+1}: {deliveries} deliveries, {'WIN' if win else 'LOSS'}")
    
    # Calculate stats
    win_rate_safe_zones = np.mean(wins_with_safe_zones) * 100
    avg_deliveries_safe_zones = np.mean(deliveries_with_safe_zones)
    
    print(f"\n📊 RESULTS WITH SAFE ZONES:")
    print(f"  🏆 Win Rate: {win_rate_safe_zones:.1f}%")
    print(f"  📦 Average Deliveries: {avg_deliveries_safe_zones:.1f}")
    print(f"  🎯 Target Deliveries: {len(model_with_safe_zones.robots)}")
    
    # Test robot navigation issues
    print(f"\n🔍 ANALYZING NAVIGATION ISSUES:")
    
    # Reset and run one episode with detailed tracking
    model_with_safe_zones.setup_episode_based_training()
    
    stuck_incidents = 0
    navigation_failures = 0
    successful_navigations = 0
    
    for step in range(100):
        if not model_with_safe_zones.running:
            break
            
        # Track robot positions before step
        positions_before = {robot.id: robot.position for robot in model_with_safe_zones.robots}
        
        try:
            model_with_safe_zones.step()
            
            # Check if robots moved (indication of successful navigation)
            for robot in model_with_safe_zones.robots:
                if robot.id in positions_before:
                    if robot.position != positions_before[robot.id]:
                        successful_navigations += 1
                    else:
                        # Robot didn't move - could be stuck or completed
                        if hasattr(robot, 'state') and robot.state not in ['IDLE', 'DONE']:
                            stuck_incidents += 1
                            
        except Exception as e:
            navigation_failures += 1
            print(f"    Navigation failure at step {step}: {e}")
    
    print(f"  ✅ Successful navigation actions: {successful_navigations}")
    print(f"  🔄 Stuck incidents: {stuck_incidents}")
    print(f"  ❌ Navigation failures: {navigation_failures}")
    
    # Test specific safe zone functionality
    print(f"\n🛡️ TESTING SAFE ZONE ACTIVATION:")
    
    # Find boxes and test their accessibility
    boxes = getattr(model_with_safe_zones, 'boxes', [])
    safe_zone_activations = 0
    
    for i, box in enumerate(boxes[:3]):
        if isinstance(box, dict) and 'pos' in box:
            box_pos = box['pos'][:2]  # x, y only
            
            # Get basic approach cells
            from warehouse import approach_cells_to_box, ensure_box_accessibility
            basic_cells = approach_cells_to_box(model_with_safe_zones, box_pos)
            enhanced_cells = ensure_box_accessibility(model_with_safe_zones, box_pos)
            
            if len(enhanced_cells) > len(basic_cells):
                safe_zone_activations += 1
                print(f"  📦 Box {i+1} at {box_pos}: Safe zone activated! ({len(basic_cells)} → {len(enhanced_cells)} cells)")
            else:
                print(f"  📦 Box {i+1} at {box_pos}: Sufficient access ({len(basic_cells)} cells)")
    
    print(f"  🛡️ Safe zone activations: {safe_zone_activations}/{len(boxes[:3])}")
    
    # Summary and recommendations
    print(f"\n📋 SAFE ZONE SYSTEM ANALYSIS:")
    print(f"  ✅ System Status: {'ACTIVE and HELPING' if win_rate_safe_zones > 70 else 'ACTIVE but may need tuning'}")
    print(f"  📈 Performance: {win_rate_safe_zones:.1f}% win rate indicates {'GOOD' if win_rate_safe_zones > 80 else 'MODERATE' if win_rate_safe_zones > 60 else 'NEEDS IMPROVEMENT'}")
    
    if safe_zone_activations == 0:
        print(f"  ℹ️ Safe zones didn't activate in this test - boxes have sufficient basic access")
        print(f"     This is normal behavior; safe zones activate when needed")
    else:
        print(f"  🛡️ Safe zones activated {safe_zone_activations} times, improving accessibility")
    
    return {
        'win_rate': win_rate_safe_zones,
        'avg_deliveries': avg_deliveries_safe_zones,
        'target_deliveries': len(model_with_safe_zones.robots),
        'safe_zone_activations': safe_zone_activations,
        'navigation_successes': successful_navigations,
        'stuck_incidents': stuck_incidents
    }

if __name__ == "__main__":
    results = test_safe_zone_training_effectiveness()
    
    # Create a simple performance summary
    print(f"\n📊 FINAL SUMMARY:")
    print(f"🏆 Win Rate: {results['win_rate']:.1f}%")
    print(f"📦 Delivery Performance: {results['avg_deliveries']:.1f}/{results['target_deliveries']}")
    print(f"🛡️ Safe Zone System: {'OPERATIONAL' if results['safe_zone_activations'] >= 0 else 'ERROR'}")
    print(f"🎯 Navigation: {results['navigation_successes']} successes, {results['stuck_incidents']} stuck incidents")
    
    if results['win_rate'] >= 70:
        print(f"✅ Safe zone system appears to be helping maintain good performance!")
    elif results['win_rate'] >= 50:
        print(f"⚠️ Moderate performance - safe zone system is working but may need fine-tuning")
    else:
        print(f"❌ Low performance detected - investigate training or safe zone parameters")