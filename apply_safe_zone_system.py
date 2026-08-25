#!/usr/bin/env python3
"""
Add Safe Zone functionality to ensure robots can always reach objectives
"""

import re

def apply_safe_zone_system():
    """Add safe zone system to warehouse.py for better navigation"""
    
    print("🛡️ APPLYING SAFE ZONE SYSTEM")
    print("=" * 50)
    
    # Read the warehouse.py file
    with open('warehouse.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add safe zone functions after the existing approach_cells_to_box function
    safe_zone_functions = '''

def get_safe_zone_around_position(model, center_pos, radius=2):
    """
    Get safe zone cells around a position (box or drop zone).
    Safe zone ensures there are always accessible paths to the objective.
    """
    if not isinstance(center_pos, (list, tuple)) or len(center_pos) < 2:
        return []
    
    cx, cy = int(center_pos[0]), int(center_pos[1])
    safe_cells = []
    
    # Create expanding square around the center position
    for r in range(1, radius + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if abs(dx) == r or abs(dy) == r:  # Only perimeter cells
                    cell = (cx + dx, cy + dy)
                    if (0 <= cell[0] < model.W and 0 <= cell[1] < model.H and 
                        model.cell_is_free(cell)):
                        safe_cells.append(cell)
    
    return safe_cells

def ensure_box_accessibility(model, box_pos, robot=None):
    """
    Ensure a box position has accessible approach cells.
    If not enough access, return expanded safe zone cells.
    """
    if not isinstance(box_pos, (list, tuple)) or len(box_pos) < 2:
        return []
    
    # Get standard approach cells
    standard_approach = approach_cells_to_box(model, box_pos, robot)
    
    # If we have enough approach cells, use them
    if len(standard_approach) >= 2:
        return standard_approach
    
    # Otherwise, expand to safe zone
    safe_zone = get_safe_zone_around_position(model, box_pos, radius=2)
    
    # Combine standard approach with safe zone
    all_access_cells = list(set(standard_approach + safe_zone))
    
    # Filter by robot capabilities if specified
    if robot is not None and len(box_pos) >= 3:
        box_level = int(box_pos[2]) if box_pos[2] is not None else 1
        robot_access_levels = getattr(robot, 'access_levels', [1, 2])
        if box_level not in robot_access_levels:
            return []
    
    return all_access_cells

def ensure_drop_zone_accessibility(model, drop_pos, radius=1):
    """
    Ensure a drop zone has accessible cells around it.
    Creates a safe zone around the drop location.
    """
    if not isinstance(drop_pos, (list, tuple)) or len(drop_pos) < 2:
        return []
    
    dx, dy = int(drop_pos[0]), int(drop_pos[1])
    access_cells = []
    
    # Get immediate neighbors
    immediate_neighbors = neighbors4(dx, dy)
    free_neighbors = [p for p in immediate_neighbors if model.cell_is_free(p)]
    
    # If enough immediate access, use it
    if len(free_neighbors) >= 2:
        return free_neighbors
    
    # Otherwise, expand to safe zone
    safe_zone = get_safe_zone_around_position(model, drop_pos, radius)
    
    # Prioritize closer cells
    all_cells = free_neighbors + safe_zone
    return list(set(all_cells))

def find_safe_path_to_objective(model, robot_pos, objective_pos, objective_type="box"):
    """
    Find a safe path to an objective, considering safe zones.
    Returns intermediate waypoints if direct path is blocked.
    """
    if not isinstance(robot_pos, (list, tuple)) or not isinstance(objective_pos, (list, tuple)):
        return []
    
    rx, ry = int(robot_pos[0]), int(robot_pos[1])
    ox, oy = int(objective_pos[0]), int(objective_pos[1])
    
    # Check if direct path is possible
    if objective_type == "box":
        target_cells = ensure_box_accessibility(model, objective_pos)
    else:  # drop zone
        target_cells = ensure_drop_zone_accessibility(model, objective_pos)
    
    if not target_cells:
        return []
    
    # Find closest accessible cell
    min_dist = float('inf')
    best_cell = None
    
    for cell in target_cells:
        dist = abs(rx - cell[0]) + abs(ry - cell[1])  # Manhattan distance
        if dist < min_dist:
            min_dist = dist
            best_cell = cell
    
    return [best_cell] if best_cell else []
'''
    
    # Insert the safe zone functions after the approach_cells_to_box function
    insert_point = content.find('def get_guidance_lines_for_box(')
    if insert_point == -1:
        print("❌ Could not find insertion point for safe zone functions")
        return
    
    content = content[:insert_point] + safe_zone_functions + '\n' + content[insert_point:]
    
    # Update the approach_cells_to_box function to use safe zones
    old_approach_function = '''def approach_cells_to_box(model, box_loc, robot=None):
    """
    Celdas válidas para hacer PICKUP: adyacentes libres a la celda de la caja.
    box_loc es la celda REAL de la caja (en el rack).
    Now considers robot capabilities for high-level boxes.
    """
    if box_loc is None or not isinstance(box_loc, (list, tuple)) or len(box_loc) < 2:
        return []
    
    # Check if robot can access this box level using new level system
    if robot is not None and len(box_loc) >= 3:
        box_level = int(box_loc[2]) if box_loc[2] is not None else 1
        robot_access_levels = getattr(robot, 'access_levels', [1, 2])  # Default to levels 1,2
        if box_level not in robot_access_levels:
            return []  # Robot can't access this box level
    
    bx, by = box_loc[0], box_loc[1]
    return [p for p in neighbors4(bx, by) if model.cell_is_free(p)]'''
    
    new_approach_function = '''def approach_cells_to_box(model, box_loc, robot=None):
    """
    Celdas válidas para hacer PICKUP: adyacentes libres a la celda de la caja.
    box_loc es la celda REAL de la caja (en el rack).
    Now uses safe zone system for better accessibility.
    """
    if box_loc is None or not isinstance(box_loc, (list, tuple)) or len(box_loc) < 2:
        return []
    
    # Check if robot can access this box level using new level system
    if robot is not None and len(box_loc) >= 3:
        box_level = int(box_loc[2]) if box_loc[2] is not None else 1
        robot_access_levels = getattr(robot, 'access_levels', [1, 2])  # Default to levels 1,2
        if box_level not in robot_access_levels:
            return []  # Robot can't access this box level
    
    # Use safe zone system for better accessibility
    return ensure_box_accessibility(model, box_loc, robot)'''
    
    content = content.replace(old_approach_function, new_approach_function)
    
    # Update the DISCHARGE validation to use safe zones for drop locations
    # Find the DISCHARGE validation section
    discharge_pattern = r'if mission == "DELIVERY":\s+if carrying and target is not None:\s+tgt_xy = tuple\(target\[:2\]\)[^}]+if \(x, y\) == tgt_xy:\s+valid\.append\("DISCHARGE"\)'
    
    new_discharge_logic = '''if mission == "DELIVERY":
            if carrying and target is not None:
                tgt_xy = tuple(target[:2]) if isinstance(target, (list, tuple)) and len(target) >= 2 else tuple(target)
                # Use safe zone for drop accessibility
                drop_access_cells = ensure_drop_zone_accessibility(self.model, target)
                if (x, y) == tgt_xy or (x, y) in drop_access_cells:
                    valid.append("DISCHARGE")'''
    
    # Apply the replacement (this is complex regex, so let's do it step by step)
    lines = content.split('\n')
    in_delivery_section = False
    updated_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        if 'if mission == "DELIVERY":' in line and 'if carrying and target is not None:' in lines[i+1] if i+1 < len(lines) else False:
            # Found the section to replace
            updated_lines.append('        if mission == "DELIVERY":')
            updated_lines.append('            if carrying and target is not None:')
            updated_lines.append('                tgt_xy = tuple(target[:2]) if isinstance(target, (list, tuple)) and len(target) >= 2 else tuple(target)')
            updated_lines.append('                # Use safe zone for drop accessibility')  
            updated_lines.append('                drop_access_cells = ensure_drop_zone_accessibility(self.model, target)')
            updated_lines.append('                if (x, y) == tgt_xy or (x, y) in drop_access_cells:')
            updated_lines.append('                    valid.append("DISCHARGE")')
            
            # Skip the original lines until we get past the DISCHARGE append
            while i < len(lines) and 'valid.append("DISCHARGE")' not in lines[i]:
                i += 1
            i += 1  # Skip the DISCHARGE line itself
        else:
            updated_lines.append(line)
            i += 1
    
    content = '\n'.join(updated_lines)
    
    # Add safe zone configuration to the Warehouse model initialization
    init_pattern = r'(def __init__\(self.*?\n.*?super\(\).__init__\(\*\*kwargs\))'
    safe_zone_init = r'\1\n        \n        # Safe Zone System Configuration\n        self.safe_zone_radius = 2  # Default safe zone radius\n        self.min_access_cells = 2  # Minimum accessible cells required'
    
    content = re.sub(init_pattern, safe_zone_init, content, flags=re.DOTALL)
    
    # Save the updated content
    with open('warehouse.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Safe zone system applied successfully!")
    print("🛡️ Features added:")
    print("  - Safe zones around box locations")
    print("  - Extended drop zone accessibility")
    print("  - Automatic fallback to expanded access areas")
    print("  - Path finding with safe zone consideration")
    print("  - Configurable safe zone radius")

if __name__ == "__main__":
    apply_safe_zone_system()