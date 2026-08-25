#!/usr/bin/env python3
"""
Test the safe zone system to ensure robots can reach objectives
"""

from warehouse import Warehouse
import matplotlib.pyplot as plt
import numpy as np

def test_safe_zone_system():
    """Test the safe zone functionality"""
    
    print("🧪 TESTING SAFE ZONE SYSTEM")
    print("=" * 50)
    
    # Create a test model
    model = Warehouse(
        width=25, height=25,
        n_robots=2,
        n_boxes=5,
        training_mode=True
    )
    model.setup()
    
    print(f"🤖 Created model with {len(model.robots)} robots")
    print(f"📦 Box locations and their safe zones:")
    
    # Test box accessibility
    box_accessibility_data = []
    
    # Use the boxes from the model
    boxes = getattr(model, 'boxes', [])
    print(f"🔍 Found {len(boxes)} boxes in the model")
    if boxes:
        print(f"🔍 First box structure: {boxes[0]}")
    
    for i, box in enumerate(boxes[:5]):  # Test first 5 boxes
        # Each box should have position data (x, y, level) or similar
        if isinstance(box, dict):
            # Box structure: {'pos': [x, y, level], ...}
            pos_data = box.get('pos', [])
            if len(pos_data) >= 2:
                box_pos = (pos_data[0], pos_data[1])
            else:
                continue
        elif isinstance(box, (list, tuple)) and len(box) >= 2:
            box_pos = (box[0], box[1])
        else:
            continue
            
        if box_pos[0] is None or box_pos[1] is None:
            continue
            
        print(f"\n📦 Box {i+1} at position {box_pos}:")
        
        # Test standard approach cells (adjacent cells only)
        standard_cells = [p for p in [(box_pos[0]+dx, box_pos[1]+dy) for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]] 
                         if model.cell_is_free(p)]
        
        # Test safe zone approach cells (now built into approach_cells_to_box)
        from warehouse import approach_cells_to_box
        safe_zone_cells = approach_cells_to_box(model, box_pos)
        
        print(f"  📍 Standard approach cells: {len(standard_cells)} - {standard_cells}")
        print(f"  🛡️ Safe zone approach cells: {len(safe_zone_cells)} - {safe_zone_cells}")
        
        box_accessibility_data.append({
            'position': box_pos,
            'standard_access': len(standard_cells),
            'safe_zone_access': len(safe_zone_cells),
            'improvement': len(safe_zone_cells) - len(standard_cells)
        })
    
    # Test drop zone accessibility
    print(f"\n🎯 Drop zone accessibility test:")
    
    # Test some potential drop locations
    test_drop_locations = []
    for robot in model.robots:
        if hasattr(robot, 'target') and robot.target is not None:
            test_drop_locations.append(robot.target)
        elif hasattr(robot, 'drop_location') and robot.drop_location is not None:
            test_drop_locations.append(robot.drop_location)
    
    # If no targets, create some test locations
    if not test_drop_locations:
        test_drop_locations = [(5, 5), (10, 10), (15, 15), (20, 5)]
    
    drop_accessibility_data = []
    
    for i, drop_pos in enumerate(test_drop_locations[:3]):
        print(f"\n🎯 Drop zone {i+1} at position {drop_pos}:")
        
        # Test standard neighbors
        standard_drop_cells = [p for p in [(drop_pos[0]+dx, drop_pos[1]+dy) for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]] 
                              if model.cell_is_free(p)]
        
        # Test safe zone drop accessibility
        from warehouse import ensure_drop_zone_accessibility
        try:
            safe_drop_cells = ensure_drop_zone_accessibility(model, drop_pos)
            
            print(f"  📍 Standard drop access: {len(standard_drop_cells)} cells")
            print(f"  🛡️ Safe zone drop access: {len(safe_drop_cells)} cells")
            
            drop_accessibility_data.append({
                'position': drop_pos,
                'standard_access': len(standard_drop_cells),
                'safe_zone_access': len(safe_drop_cells),
                'improvement': len(safe_drop_cells) - len(standard_drop_cells)
            })
        except Exception as e:
            print(f"  ❌ Error testing drop zone: {e}")
    
    # Create visualization of results
    create_safe_zone_visualization(box_accessibility_data, drop_accessibility_data)
    
    # Run a quick simulation to test navigation
    print(f"\n🏃 Testing navigation with safe zones...")
    test_navigation_with_safe_zones(model)
    
    return box_accessibility_data, drop_accessibility_data

def create_safe_zone_visualization(box_data, drop_data):
    """Create visualization showing safe zone improvements"""
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle('🛡️ Safe Zone System: Accessibility Improvements', fontsize=16, fontweight='bold')
    
    # Box accessibility chart
    if box_data:
        box_positions = [f"Box {i+1}" for i in range(len(box_data))]
        standard_access = [d['standard_access'] for d in box_data]
        safe_zone_access = [d['safe_zone_access'] for d in box_data]
        
        x = np.arange(len(box_positions))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, standard_access, width, label='Standard Access', alpha=0.7, color='lightcoral')
        bars2 = ax1.bar(x + width/2, safe_zone_access, width, label='Safe Zone Access', alpha=0.7, color='lightgreen')
        
        ax1.set_title('Box Accessibility Comparison')
        ax1.set_xlabel('Box Locations')
        ax1.set_ylabel('Number of Accessible Cells')
        ax1.set_xticks(x)
        ax1.set_xticklabels(box_positions)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{int(height)}', ha='center', va='bottom')
    else:
        ax1.text(0.5, 0.5, 'No box data available', ha='center', va='center', transform=ax1.transAxes)
        ax1.set_title('Box Accessibility (No Data)')
    
    # Drop zone accessibility chart
    if drop_data:
        drop_positions = [f"Drop {i+1}" for i in range(len(drop_data))]
        standard_drop = [d['standard_access'] for d in drop_data]
        safe_zone_drop = [d['safe_zone_access'] for d in drop_data]
        
        x = np.arange(len(drop_positions))
        width = 0.35  # Define width here too
        
        bars1 = ax2.bar(x - width/2, standard_drop, width, label='Standard Access', alpha=0.7, color='lightcoral')
        bars2 = ax2.bar(x + width/2, safe_zone_drop, width, label='Safe Zone Access', alpha=0.7, color='lightgreen')
        
        ax2.set_title('Drop Zone Accessibility Comparison')
        ax2.set_xlabel('Drop Locations')
        ax2.set_ylabel('Number of Accessible Cells')
        ax2.set_xticks(x)
        ax2.set_xticklabels(drop_positions)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{int(height)}', ha='center', va='bottom')
    else:
        ax2.text(0.5, 0.5, 'No drop zone data available', ha='center', va='center', transform=ax2.transAxes)
        ax2.set_title('Drop Zone Accessibility (No Data)')
    
    plt.tight_layout()
    plt.savefig('safe_zone_test_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 Safe zone test visualization saved as 'safe_zone_test_results.png'")

def test_navigation_with_safe_zones(model):
    """Test robot navigation with safe zones enabled"""
    
    # Run a few steps to see if robots can navigate better
    stuck_count = 0
    successful_actions = 0
    
    for step in range(20):
        if not model.running:
            break
            
        # Count robots that seem stuck (not moving)
        robot_positions_before = [robot.position for robot in model.robots]
        
        try:
            model.step()
            successful_actions += 1
            
            # Check if robots moved
            robot_positions_after = [robot.position for robot in model.robots]
            movements = sum(1 for before, after in zip(robot_positions_before, robot_positions_after) 
                          if before != after)
            
            if movements == 0:
                stuck_count += 1
            
        except Exception as e:
            print(f"❌ Error during navigation test step {step}: {e}")
            break
    
    print(f"📊 Navigation test results:")
    print(f"  ✅ Successful steps: {successful_actions}/20")
    print(f"  🔄 Steps with robot movement: {20 - stuck_count}/20")
    print(f"  🛡️ Safe zone system {'HELPING' if stuck_count < 10 else 'NEEDS TUNING'}")

if __name__ == "__main__":
    test_safe_zone_system()