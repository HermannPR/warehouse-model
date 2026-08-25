#!/usr/bin/env python3
"""
Performance comparison test for guidance line improvements
"""

import sys
sys.path.append('.')

from warehouse import Warehouse, get_guidance_lines_for_box, is_on_guidance_line_for_box

def test_mission_specific_guidance():
    """Test the mission-specific guidance line system"""
    print("Mission-Specific Guidance Line Test")
    print("=" * 50)
    
    try:
        model = Warehouse({'config_path': 'layout.json'})
        model.setup()
        
        print(f"Warehouse size: {model.W} x {model.H}")
        print(f"Number of boxes: {len(model.boxes)}")
        
        # Test guidance lines for each box
        for i, box in enumerate(model.boxes):
            if isinstance(box, dict) and 'pos' in box:
                pos = box['pos']
                print(f"\nBox {i} at position {pos}:")
                
                # Get guidance lines for this specific box
                guidance_positions = get_guidance_lines_for_box(model, pos)
                print(f"  Guidance line positions: {len(guidance_positions)}")
                
                # Show sample positions (left and right columns)
                bx = pos[0]
                left_column = [(bx-1, y) for y in range(min(10, model.H)) if (bx-1, y) in guidance_positions]
                right_column = [(bx+1, y) for y in range(min(10, model.H)) if (bx+1, y) in guidance_positions]
                
                print(f"  Left column (x={bx-1}): {left_column[:5]}{'...' if len(left_column) > 5 else ''}")
                print(f"  Right column (x={bx+1}): {right_column[:5]}{'...' if len(right_column) > 5 else ''}")
                
                # Test specific positions for this box
                test_positions = [
                    (bx-1, pos[1]),    # Left of box, same Y
                    (bx+1, pos[1]),    # Right of box, same Y  
                    (bx-1, 0),         # Left column, top
                    (bx+1, model.H-1), # Right column, bottom
                    (bx, pos[1])       # Box position itself
                ]
                
                for test_pos in test_positions:
                    if 0 <= test_pos[0] < model.W and 0 <= test_pos[1] < model.H:
                        on_line = is_on_guidance_line_for_box(model, test_pos, pos)
                        print(f"    Position {test_pos}: {'✓' if on_line else '✗'}")
        
        print(f"\n✓ Mission-specific guidance line test completed!")
        print(f"Key improvements:")
        print(f"  • Full-height guidance lines (0 to {model.H-1})")
        print(f"  • Mission-specific targeting (only for current box)")
        print(f"  • Enhanced rewards for approaching target box")
        
    except Exception as e:
        print(f"Error testing guidance lines: {e}")

if __name__ == "__main__":
    test_mission_specific_guidance()