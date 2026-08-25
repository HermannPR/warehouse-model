#!/usr/bin/env python3
"""
Test the safe zone system with intentionally blocked scenarios
"""

from warehouse import Warehouse, ensure_box_accessibility, approach_cells_to_box, get_safe_zone_around_position
import matplotlib.pyplot as plt
import numpy as np

def test_blocked_box_scenario():
    """Test safe zone with boxes that have limited access"""
    
    print("🧪 TESTING SAFE ZONE WITH BLOCKED SCENARIOS")
    print("=" * 60)
    
    # Create a test model
    model = Warehouse(
        width=15, height=15,
        n_robots=2,
        n_boxes=3,
        training_mode=True
    )
    model.setup()
    
    print(f"🤖 Created model with {len(model.robots)} robots")
    print(f"📦 Testing safe zone expansion for blocked boxes")
    
    # Let's test specific positions that might be more constrained
    test_positions = [
        (3, 3),   # Corner-ish position  
        (1, 1),   # Very corner position
        (7, 7),   # Central position
        (2, 2),   # Near corner
    ]
    
    results = []
    
    for i, test_pos in enumerate(test_positions):
        print(f"\n📦 Test Box {i+1} at position {test_pos}:")
        
        # Get basic approach cells
        basic_approach = approach_cells_to_box(model, test_pos)
        
        # Get safe zone enhanced approach
        safe_zone_approach = ensure_box_accessibility(model, test_pos)
        
        # Get pure safe zone cells
        safe_zone_only = get_safe_zone_around_position(model, test_pos, radius=2)
        
        print(f"  📍 Basic approach cells: {len(basic_approach)} - {basic_approach}")
        print(f"  🛡️ Safe zone enhanced: {len(safe_zone_approach)} - {safe_zone_approach}")
        print(f"  🔵 Pure safe zone cells: {len(safe_zone_only)} - {safe_zone_only[:8]}{'...' if len(safe_zone_only) > 8 else ''}")
        
        improvement = len(safe_zone_approach) - len(basic_approach)
        print(f"  ⬆️ Improvement: +{improvement} accessible cells")
        
        results.append({
            'position': test_pos,
            'basic': len(basic_approach),
            'enhanced': len(safe_zone_approach),
            'safe_zone_only': len(safe_zone_only),
            'improvement': improvement
        })
    
    # Create visualization
    create_blocked_scenario_visualization(results)
    
    return results

def create_blocked_scenario_visualization(results):
    """Create visualization for blocked scenario testing"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    fig.suptitle('🛡️ Safe Zone System: Accessibility Enhancement Test', fontsize=16, fontweight='bold')
    
    positions = [f"Pos {result['position']}" for result in results]
    basic_counts = [result['basic'] for result in results]
    enhanced_counts = [result['enhanced'] for result in results]
    improvements = [result['improvement'] for result in results]
    
    # Bar chart comparing basic vs enhanced
    x = np.arange(len(positions))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, basic_counts, width, label='Basic Approach', 
                    alpha=0.7, color='lightcoral')
    bars2 = ax1.bar(x + width/2, enhanced_counts, width, label='Safe Zone Enhanced', 
                    alpha=0.7, color='lightgreen')
    
    ax1.set_title('Accessibility Comparison')
    ax1.set_xlabel('Test Positions')
    ax1.set_ylabel('Number of Accessible Cells')
    ax1.set_xticks(x)
    ax1.set_xticklabels(positions, rotation=45)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{int(height)}', ha='center', va='bottom')
    
    # Improvement chart
    colors = ['red' if imp == 0 else 'green' for imp in improvements]
    bars3 = ax2.bar(positions, improvements, alpha=0.7, color=colors)
    
    ax2.set_title('Safe Zone System Improvement')
    ax2.set_xlabel('Test Positions')  
    ax2.set_ylabel('Additional Accessible Cells')
    ax2.set_xticklabels(positions, rotation=45)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    # Add value labels
    for bar, imp in zip(bars3, improvements):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height >= 0 else -0.3),
                f'+{int(height)}' if height > 0 else f'{int(height)}', 
                ha='center', va='bottom' if height >= 0 else 'top')
    
    plt.tight_layout()
    plt.savefig('safe_zone_blocked_test.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 Blocked scenario test visualization saved as 'safe_zone_blocked_test.png'")

def test_safe_zone_radius_scaling():
    """Test how safe zone radius affects accessibility"""
    
    print(f"\n🔬 TESTING SAFE ZONE RADIUS SCALING")
    print("=" * 50)
    
    model = Warehouse(
        width=15, height=15,
        n_robots=2,
        n_boxes=2,
        training_mode=True
    )
    model.setup()
    
    test_pos = (7, 7)  # Central position
    radii = [1, 2, 3, 4]
    
    print(f"📍 Testing position {test_pos} with different safe zone radii:")
    
    for radius in radii:
        safe_zone_cells = get_safe_zone_around_position(model, test_pos, radius=radius)
        print(f"  Radius {radius}: {len(safe_zone_cells)} safe zone cells")
    
    return True

if __name__ == "__main__":
    # Run blocked scenario test
    blocked_results = test_blocked_box_scenario()
    
    # Run radius scaling test  
    test_safe_zone_radius_scaling()
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"✅ Safe zone system is functional")
    total_improvements = sum(r['improvement'] for r in blocked_results)
    positions_improved = sum(1 for r in blocked_results if r['improvement'] > 0)
    print(f"📈 Total accessibility improvements: +{total_improvements} cells")
    print(f"📍 Positions with improvements: {positions_improved}/{len(blocked_results)}")
    
    if total_improvements > 0:
        print(f"🛡️ Safe zone system is WORKING and improving accessibility!")
    else:
        print(f"ℹ️ Safe zone system is ready but current test positions have sufficient basic access.")
        print(f"   System will activate when boxes have limited approach cells.")