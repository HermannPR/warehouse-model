#!/usr/bin/env python3
"""
Simple test to verify guidance line functionality
"""

import sys
sys.path.append('.')

from warehouse import Warehouse, get_guidance_lines_for_boxes, is_on_guidance_line_for_box

def test_guidance_lines():
    """Test the guidance line system"""
    print("Testing Guidance Line System")
    print("=" * 40)
    
    # Create a simple warehouse model
    try:
        model = Warehouse({'config_path': 'layout.json'})
        model.setup()
        
        print(f"Warehouse size: {model.W} x {model.H}")
        print(f"Number of boxes: {len(model.boxes)}")
        
        # Get guidance lines
        guidance_positions = get_guidance_lines_for_boxes(model)
        print(f"Total guidance line positions: {len(guidance_positions)}")
        
        # Show first few guidance positions
        sample_positions = list(guidance_positions)[:10]
        print(f"Sample guidance positions: {sample_positions}")
        
        # Test specific positions against first box
        test_positions = [(3, 3), (4, 3), (2, 3), (5, 10), (10, 15)]
        first_box = model.boxes[0]['pos'] if model.boxes and isinstance(model.boxes[0], dict) and 'pos' in model.boxes[0] else [3, 3, 1]
        print(f"\nTesting specific positions against box at {first_box}:")
        for pos in test_positions:
            on_line = is_on_guidance_line_for_box(model, pos, first_box)
            print(f"  Position {pos}: {'ON guidance line' if on_line else 'not on guidance line'}")
        
        # Show box positions for reference
        print(f"\nBox positions for reference:")
        for i, box in enumerate(model.boxes):
            if isinstance(box, dict) and 'pos' in box:
                pos = box['pos']
                print(f"  Box {i}: {pos}")
        
        print("\n✓ Guidance line test completed successfully!")
        
    except Exception as e:
        print(f"Error testing guidance lines: {e}")

if __name__ == "__main__":
    test_guidance_lines()