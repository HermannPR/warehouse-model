#!/usr/bin/env python3
"""
Test script to validate the warehouse setup with your JSON configuration
"""

import json
from warehouse import Warehouse

def test_configuration():
    """Test that the configuration loads correctly"""
    print("Testing warehouse configuration...")
    
    try:
        # Create model instance
        params = {'config_path': 'layout.json'}
        model = Warehouse(parameters=params)
        # Ensure model is initialized before accessing properties
        model.setup()
        
        print(f"✓ Configuration loaded successfully")
        print(f"  Grid size: {model.W}x{model.H}")
        print(f"  Robots: {len(model.robots)}")
        print(f"  Boxes: {len(model.boxes)}")
        print(f"  Drop points: {len(model.drop_points)}")
        print(f"  Charge points: {len(model.recharge_points)}")
        print(f"  Blocked cells: {len(model.occupied)}")
        
        # Test robot positions
        print("\nRobot status:")
        for robot in model.robots:
            print(f"  Robot {robot.id}: pos={robot.position}, type={robot.r_type}, battery={robot.battery}%")
        
        # Test box positions
        print("\nBox positions:")
        for box in model.boxes:
            pos = box.get('pos', 'Unknown')
            print(f"  {box['id']}: {pos} (rack: {box['rack_id']}, slot: bay={box['slot']['bay']}, level={box['slot']['level']})")
        
        # Test points
        print(f"\nPoints:")
        print(f"  Drop points: {model.drop_points}")
        print(f"  Charge points: {model.recharge_points}")
        print(f"  Spawn points: {model.spawn_points}")
        
        # Test a few simulation steps
        print("\nRunning 5 test steps...")
        for i in range(5):
            model.step()
            print(f"  Step {i+1}: {len([r for r in model.robots if r.mission])} robots active")
        
        print(f"\nFinal stats: deliveries={model.stats['deliveries']}, pickups={model.stats['pickups']}")
        print("✓ Configuration test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def validate_json_structure():
    """Validate the JSON structure"""
    print("\nValidating JSON structure...")
    
    try:
        with open('layout.json', 'r') as f:
            cfg = json.load(f)
        
        # Check required fields
        required_fields = ['tilemap', 'tags', 'entities', 'boxes', 'robots']
        for field in required_fields:
            if field not in cfg:
                print(f"✗ Missing required field: {field}")
                return False
            else:
                print(f"✓ Found {field}")
        
        # Check tilemap
        tilemap = cfg['tilemap']
        walkable = tilemap['walkable']
        legend = tilemap['legend']
        
        print(f"  Tilemap: {len(walkable)}x{len(walkable[0])} grid")
        print(f"  Legend: {legend}")
        
        # Check robots
        robots = cfg['robots']
        print(f"  Robots: {len(robots)} defined")
        for robot in robots:
            pos = robot['position']
            if not (0 <= pos[0] < len(walkable[0]) and 0 <= pos[1] < len(walkable)):
                print(f"✗ Robot {robot['id']} position {pos} out of bounds")
                return False
        
        # Check tags
        tags = cfg['tags']
        print(f"  Tags: {len(tags)} defined")
        tag_types = {}
        for tag in tags:
            tag_type = tag['type']
            tag_types[tag_type] = tag_types.get(tag_type, 0) + 1
        print(f"    {tag_types}")
        
        # Check boxes and racks
        racks = cfg['entities']['racks']
        boxes = cfg['boxes']
        print(f"  Racks: {len(racks)} defined")
        print(f"  Boxes: {len(boxes)} defined")
        
        print("✓ JSON structure validation passed!")
        return True
        
    except Exception as e:
        print(f"✗ JSON validation failed: {e}")
        return False

def main():
    print("=" * 50)
    print("WAREHOUSE CONFIGURATION TEST")
    print("=" * 50)
    
    # Validate JSON first
    if not validate_json_structure():
        return False
    
    # Test configuration loading
    if not test_configuration():
        return False
    
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED!")
    print("=" * 50)
    print("\nYou can now run:")
    print("  python train.py train --episodes 100")
    print("  python train.py visualize --steps 500")
    
    return True

if __name__ == "__main__":
    main()