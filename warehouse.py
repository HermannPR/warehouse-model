from collections import deque
# Poner indicadores de progreso en el modelo y actualizar desde agent
# Poner visualización
# Cargar pesos preentrenados

import numpy as np
import random
import agentpy as ap
import json
import os

# Centralized constants import (keeps backwards compat variable names)
from config_constants import (
    JSON_INITIALIZATION, PRETRAIN_ENABLED, VISUALIZATION_ENABLED,
    CYCLE_DELIVERIES_TARGET, ACTIONS, MOVE_TO_HEADING, ACTION_TO_UNITY,
    ALPHA, GAMMA, EPSILON_START, EPSILON_END, DECAY_STEPS, EPSILON_TAU,
    FEAT_PER_ACT, N_FEATURES, R_STEP, R_SHAPING_K, R_PICKUP, R_DROP, R_RECHARGE,
    R_BUMP, R_CONFLICT, LOW_BATT_THR, R_LOW_BATT, R_PROXIMITY_BONUS, R_ADJACENT_BONUS, R_INEFFICIENCY_PENALTY
)

## (legacy constant block folded into config_constants.py)

# =========================== Helpers ================================
def is_adjacent(pos1:tuple, pos2:tuple):
    x1, y1 = pos1
    x2, y2 = pos2
    return (abs(x1-x2) + abs(y1-y2) == 1)

def neighbors4(x, y):
    """Vecindario 4-direcciones, sin filtrar bordes/bloqueo."""
    return [(x-1,y), (x+1,y), (x, y-1), (x, y+1)]

DIRS = {
    "LEFT":  (-1, 0),
    "RIGHT": ( 1, 0),
    "UP":    ( 0,-1),
    "DOWN":  ( 0, 1),
}

def next_pos_from_action(model, pos, action):
    x, y = pos
    if action in DIRS:
        dx, dy = DIRS[action]
        cand = (x + dx, y + dy)
        return cand if model.cell_is_free(cand) else (x, y)
    return (x, y)

def approach_cells_to_box(model, box_loc, robot=None):
    """
    Celdas válidas para hacer PICKUP: adyacentes libres a la celda de la caja.
    box_loc es la celda REAL de la caja (en el rack).
    Returns basic adjacent cells - enhanced version available through ensure_box_accessibility.
    """
    if box_loc is None or not isinstance(box_loc, (list, tuple)) or len(box_loc) < 2:
        return []
    
    # Check if robot can access this box level using new level system
    if robot is not None and len(box_loc) >= 3:
        box_level = int(box_loc[2]) if box_loc[2] is not None else 1
        robot_access_levels = getattr(robot, 'access_levels', [1, 2])  # Default to levels 1,2
        if box_level not in robot_access_levels:
            return []  # Robot can't access this box level
    
    # Return basic adjacent cells that are free
    bx, by = int(box_loc[0]), int(box_loc[1])
    adjacent_cells = [(bx+dx, by+dy) for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]]
    return [cell for cell in adjacent_cells if model.cell_is_free(cell)]



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


def find_path_around_obstacles(model, start_pos, goal_pos, max_search_distance=50):
    """
    Optimized A* pathfinding that guarantees the shortest possible path.
    Uses advanced heuristics and optimizations for minimal step count.
    Returns a list of waypoint positions to follow, or empty list if no path found.
    """
    from heapq import heappush, heappop
    
    if not isinstance(start_pos, (list, tuple)) or not isinstance(goal_pos, (list, tuple)):
        return []
    
    start = (int(start_pos[0]), int(start_pos[1]))
    goal = (int(goal_pos[0]), int(goal_pos[1]))
    
    # If start and goal are the same, no path needed
    if start == goal:
        return []
    
    # If goal is not free, find the closest accessible cell
    if not model.cell_is_free(goal):
        best_goal = None
        min_distance = float('inf')
        
        # Search in expanding circles for the closest free cell
        for radius in range(1, 6):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) == radius or abs(dy) == radius:  # Perimeter cells
                        candidate = (goal[0] + dx, goal[1] + dy)
                        if (model.inbound(candidate) and model.cell_is_free(candidate)):
                            distance = abs(dx) + abs(dy)  # Manhattan distance
                            if distance < min_distance:
                                min_distance = distance
                                best_goal = candidate
        
        if best_goal:
            goal = best_goal
        else:
            return []  # No accessible goal found
    
    # Enhanced heuristic with tie-breaking for optimal paths
    def heuristic(pos):
        dx = abs(pos[0] - goal[0])
        dy = abs(pos[1] - goal[1])
        # Manhattan distance with small tie-breaker to prefer straight lines
        return dx + dy + 0.001 * (dx * dx + dy * dy)
    
    # Optimized A* search with better data structures
    open_set = [(heuristic(start), 0, start)]  # (f_score, g_score, position)
    came_from = {}  # Track optimal path
    g_score = {start: 0}  # Best known cost to reach each position
    f_score = {start: heuristic(start)}  # Estimated total cost
    
    while open_set:
        _, current_g, current = heappop(open_set)
        
        # Found goal - reconstruct optimal path
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]  # Reverse to get start->goal order
        
        # Skip if we've found a better path to this position
        if current_g > g_score.get(current, float('inf')):
            continue
        
        # Prevent excessive search (but allow longer searches for optimization)
        if current_g > max_search_distance:
            continue
        
        # Explore neighbors in priority order (straight directions first for efficiency)
        neighbors = [
            (0, -1),   # UP - often shortest in warehouse layouts
            (0, 1),    # DOWN
            (-1, 0),   # LEFT
            (1, 0),    # RIGHT
        ]
        
        for dx, dy in neighbors:
            neighbor = (current[0] + dx, current[1] + dy)
            
            # Skip if not free or out of bounds
            if not model.inbound(neighbor) or not model.cell_is_free(neighbor):
                continue
            
            # Calculate cost (uniform cost of 1 for each step)
            tentative_g = current_g + 1
            
            # If this path to neighbor is better than previous ones
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor)
                heappush(open_set, (f_score[neighbor], tentative_g, neighbor))
    
    # No path found
    return []


def find_optimal_path_with_smoothing(model, start_pos, goal_pos):
    """
    Find the shortest path and then apply path smoothing for even better optimization.
    This removes unnecessary waypoints and creates smoother, more direct routes.
    """
    # First find the basic optimal path
    path = find_path_around_obstacles(model, start_pos, goal_pos)
    
    if not path or len(path) <= 2:
        return path
    
    # Apply path smoothing - remove redundant waypoints
    smoothed_path = [path[0]]  # Always keep first waypoint
    
    for i in range(1, len(path) - 1):
        current = path[i]
        prev = smoothed_path[-1]
        next_point = path[i + 1]
        
        # Check if we can skip current waypoint by going directly from prev to next
        if can_move_directly(model, prev, next_point):
            continue  # Skip this waypoint
        else:
            smoothed_path.append(current)  # Keep this waypoint
    
    smoothed_path.append(path[-1])  # Always keep last waypoint
    
    return smoothed_path


def can_move_directly(model, start, end):
    """
    Check if we can move directly between two adjacent points (distance = 1).
    For robot movement, we only allow single-step moves.
    """
    x0, y0 = start
    x1, y1 = end
    
    # Calculate Manhattan distance
    distance = abs(x1 - x0) + abs(y1 - y0)
    
    # Only allow adjacent moves (distance = 1)
    if distance != 1:
        return False
    
    # Check if the destination is free
    return model.inbound(end) and model.cell_is_free(end)


def find_robot_optimized_path(model, start_pos, goal_pos):
    """
    Enhanced A* pathfinding optimized for robot movement with multiple optimization strategies.
    Uses better heuristics and path selection for minimum steps.
    """
    from heapq import heappush, heappop
    
    if not isinstance(start_pos, (list, tuple)) or not isinstance(goal_pos, (list, tuple)):
        return []
    
    start = (int(start_pos[0]), int(start_pos[1]))
    goal = (int(goal_pos[0]), int(goal_pos[1]))
    
    if start == goal:
        return []
    
    # Enhanced heuristic that favors straight paths and penalizes turns
    def enhanced_heuristic(pos, came_from_dict):
        dx = abs(pos[0] - goal[0])
        dy = abs(pos[1] - goal[1])
        base_distance = dx + dy
        
        # Add small penalty for direction changes to encourage straight paths
        direction_penalty = 0
        if pos in came_from_dict:
            parent = came_from_dict[pos]
            if parent in came_from_dict:
                grandparent = came_from_dict[parent]
                # Check if we're changing direction
                parent_dir = (parent[0] - grandparent[0], parent[1] - grandparent[1])
                current_dir = (pos[0] - parent[0], pos[1] - parent[1])
                if parent_dir != current_dir:
                    direction_penalty = 0.1  # Small penalty for turns
        
        return base_distance + direction_penalty
    
    # A* search with enhanced heuristics
    open_set = [(enhanced_heuristic(start, {}), 0, start)]
    came_from = {}
    g_score = {start: 0}
    
    # Priority order for neighbors (prefer straight movement directions)
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]  # UP, DOWN, LEFT, RIGHT
    
    while open_set:
        _, current_g, current = heappop(open_set)
        
        if current == goal:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]
        
        if current_g > g_score.get(current, float('inf')):
            continue
        
        for dx, dy in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            
            if not model.inbound(neighbor) or not model.cell_is_free(neighbor):
                continue
            
            tentative_g = current_g + 1
            
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + enhanced_heuristic(neighbor, came_from)
                heappush(open_set, (f_score, tentative_g, neighbor))
    
    return []


def find_straight_line_optimized_path(model, start_pos, goal_pos):
    """
    Tries to find paths that prefer straight lines and minimize turns.
    This often results in shorter, more efficient paths.
    """
    from heapq import heappush, heappop
    
    start = (int(start_pos[0]), int(start_pos[1]))
    goal = (int(goal_pos[0]), int(goal_pos[1]))
    
    if start == goal:
        return []
    
    def straight_line_heuristic(pos, parent_pos):
        # Manhattan distance
        base_dist = abs(pos[0] - goal[0]) + abs(pos[1] - goal[1])
        
        # Bonus for moves that align with the goal direction
        goal_dx = goal[0] - start[0]
        goal_dy = goal[1] - start[1]
        
        if parent_pos:
            move_dx = pos[0] - parent_pos[0]
            move_dy = pos[1] - parent_pos[1]
            
            # Reward moves in the right direction
            if (goal_dx > 0 and move_dx > 0) or (goal_dx < 0 and move_dx < 0):
                base_dist -= 0.1
            if (goal_dy > 0 and move_dy > 0) or (goal_dy < 0 and move_dy < 0):
                base_dist -= 0.1
        
        return base_dist
    
    open_set = [(straight_line_heuristic(start, None), 0, start, None)]
    visited = set()
    came_from = {}
    
    while open_set:
        _, g_score, current, parent = heappop(open_set)
        
        if current in visited:
            continue
        visited.add(current)
        
        if current == goal:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]
        
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            neighbor = (current[0] + dx, current[1] + dy)
            
            if (neighbor in visited or 
                not model.inbound(neighbor) or 
                not model.cell_is_free(neighbor)):
                continue
            
            new_g = g_score + 1
            new_f = new_g + straight_line_heuristic(neighbor, current)
            came_from[neighbor] = current
            
            heappush(open_set, (new_f, new_g, neighbor, current))
    
    return []


def find_shortest_path_with_diagonals(model, start_pos, goal_pos, allow_diagonals=False):
    """
    Ultra-optimized pathfinding that can use diagonal movement for even shorter paths.
    Only enables diagonals if the warehouse layout supports it safely.
    """
    from heapq import heappush, heappop
    import math
    
    if not isinstance(start_pos, (list, tuple)) or not isinstance(goal_pos, (list, tuple)):
        return []
    
    start = (int(start_pos[0]), int(start_pos[1]))
    goal = (int(goal_pos[0]), int(goal_pos[1]))
    
    if start == goal:
        return []
    
    # Enhanced heuristic for diagonal movement
    def heuristic(pos):
        dx = abs(pos[0] - goal[0])
        dy = abs(pos[1] - goal[1])
        if allow_diagonals:
            # Octile distance (accounts for diagonal movement)
            return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)
        else:
            # Manhattan distance
            return dx + dy
    
    # Movement directions - 4-way or 8-way
    if allow_diagonals:
        directions = [
            (0, -1, 1.0),    # UP
            (0, 1, 1.0),     # DOWN  
            (-1, 0, 1.0),    # LEFT
            (1, 0, 1.0),     # RIGHT
            (-1, -1, 1.414), # UP-LEFT (diagonal)
            (1, -1, 1.414),  # UP-RIGHT (diagonal)
            (-1, 1, 1.414),  # DOWN-LEFT (diagonal)
            (1, 1, 1.414),   # DOWN-RIGHT (diagonal)
        ]
    else:
        directions = [
            (0, -1, 1.0),    # UP
            (0, 1, 1.0),     # DOWN
            (-1, 0, 1.0),    # LEFT
            (1, 0, 1.0),     # RIGHT
        ]
    
    open_set = [(heuristic(start), 0, start)]
    came_from = {}
    g_score = {start: 0}
    
    while open_set:
        _, current_g, current = heappop(open_set)
        
        if current == goal:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1]
        
        if current_g > g_score.get(current, float('inf')):
            continue
        
        for dx, dy, cost in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            
            if not model.inbound(neighbor) or not model.cell_is_free(neighbor):
                continue
            
            # For diagonal moves, check that both adjacent cells are also free
            if allow_diagonals and cost > 1.0:
                if (not model.cell_is_free((current[0] + dx, current[1])) or 
                    not model.cell_is_free((current[0], current[1] + dy))):
                    continue  # Diagonal blocked by adjacent obstacles
            
            tentative_g = current_g + cost
            
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor)
                heappush(open_set, (f_score, tentative_g, neighbor))
    
    return []


def get_optimal_path(model, start_pos, goal_pos, optimization_level='maximum'):
    """
    Intelligent pathfinding that selects the best algorithm based on the situation.
    
    optimization_level options:
    - 'basic': Standard A* pathfinding
    - 'enhanced': A* with path smoothing
    - 'maximum': All optimizations including diagonal movement when safe
    """
    if optimization_level == 'basic':
        return find_path_around_obstacles(model, start_pos, goal_pos)
    
    elif optimization_level == 'enhanced':
        # Use robot-specific optimization (single-step moves only)
        return find_robot_optimized_path(model, start_pos, goal_pos)
    
    elif optimization_level == 'maximum':
        # Try multiple approaches and pick the shortest
        paths = []
        
        # Method 1: Standard optimized A*
        path1 = find_path_around_obstacles(model, start_pos, goal_pos)
        if path1:
            paths.append(('standard', path1))
        
        # Method 2: Robot-optimized path with enhanced heuristics
        path2 = find_robot_optimized_path(model, start_pos, goal_pos)
        if path2:
            paths.append(('robot_optimized', path2))
        
        # Method 3: Straight-line optimized path
        path3 = find_straight_line_optimized_path(model, start_pos, goal_pos)
        if path3:
            paths.append(('straight_line', path3))
        
        # Method 4: Check if diagonal movement is safe and beneficial
        if is_diagonal_safe_area(model, start_pos, goal_pos):
            path4 = find_shortest_path_with_diagonals(model, start_pos, goal_pos, allow_diagonals=True)
            if path4:
                # Convert diagonal path to single-step moves
                single_step_path = convert_diagonal_to_single_steps(model, path4, start_pos)
                if single_step_path:
                    paths.append(('diagonal_converted', single_step_path))
        
        # Return the shortest path found
        if paths:
            shortest = min(paths, key=lambda x: len(x[1]))
            return shortest[1]
    
    return []


def convert_diagonal_to_single_steps(model, diagonal_path, start_pos):
    """
    Convert a path with diagonal moves into single-step robot moves.
    Fills in intermediate steps for any diagonal movements.
    """
    if not diagonal_path:
        return []
    
    single_step_path = []
    current_pos = start_pos
    
    for target_pos in diagonal_path:
        # Create path from current position to target
        while current_pos != target_pos:
            dx = target_pos[0] - current_pos[0]
            dy = target_pos[1] - current_pos[1]
            
            # Move one step closer
            next_x = current_pos[0] + (1 if dx > 0 else -1 if dx < 0 else 0)
            next_y = current_pos[1] + (1 if dy > 0 else -1 if dy < 0 else 0)
            
            next_pos = (next_x, next_y)
            
            # Check if move is valid
            if not model.inbound(next_pos) or not model.cell_is_free(next_pos):
                return []  # Invalid path
            
            single_step_path.append(next_pos)
            current_pos = next_pos
    
    return single_step_path


def is_diagonal_safe_area(model, start_pos, goal_pos):
    """
    Check if the area between start and goal is safe for diagonal movement.
    Avoids diagonal movement in tight spaces where it might cause issues.
    """
    # Calculate the bounding box of the path area
    x1, y1 = start_pos
    x2, y2 = goal_pos
    
    min_x, max_x = min(x1, x2), max(x1, x2)
    min_y, max_y = min(y1, y2), max(y1, y2)
    
    # Check for dense obstacle areas where diagonal movement might be risky
    total_cells = (max_x - min_x + 1) * (max_y - min_y + 1)
    blocked_cells = 0
    
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            if not model.inbound((x, y)) or not model.cell_is_free((x, y)):
                blocked_cells += 1
    
    # If more than 30% of the area is blocked, avoid diagonals
    if total_cells > 0 and (blocked_cells / total_cells) > 0.3:
        return False
    
    return True


def get_next_waypoint_around_obstacles(model, robot_pos, goal_pos, optimization_level='maximum'):
    """
    Get the next optimal waypoint from robot position towards goal.
    Uses the most optimized pathfinding available for minimum steps.
    """
    path = get_optimal_path(model, robot_pos, goal_pos, optimization_level)
    
    if path and len(path) > 0:
        return path[0]  # Return first waypoint in the optimal path
    
    # Fallback: try to move in the general direction but avoid obstacles
    rx, ry = int(robot_pos[0]), int(robot_pos[1])
    gx, gy = int(goal_pos[0]), int(goal_pos[1])
    
    # Calculate preferred directions
    preferred_moves = []
    
    if gx > rx:  # Goal is to the right
        preferred_moves.append((rx + 1, ry))
    elif gx < rx:  # Goal is to the left
        preferred_moves.append((rx - 1, ry))
        
    if gy > ry:  # Goal is below
        preferred_moves.append((rx, ry + 1))
    elif gy < ry:  # Goal is above
        preferred_moves.append((rx, ry - 1))
    
    # Try preferred moves
    for move in preferred_moves:
        if model.inbound(move) and model.cell_is_free(move):
            return move
    
    # If no preferred move available, try any free adjacent cell
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        candidate = (rx + dx, ry + dy)
        if model.inbound(candidate) and model.cell_is_free(candidate):
            return candidate
    
    return None


def get_guidance_lines_for_box(model, box_location):
    """
    Generate vertical guidance lines on left and right sides of a specific box.
    Lines extend the full height of the grid to encourage movement towards the box.
    Returns a set of (x, y) positions that are on guidance lines for this box.
    """
    guidance_positions = set()
    
    if not isinstance(box_location, (list, tuple)) or len(box_location) < 2:
        return guidance_positions
    
    try:
        bx = int(box_location[0])
        
        # Add full-height vertical lines on left and right sides of the target box
        for y in range(model.H):  # Full grid height
            # Left side guidance line (entire column)
            left_pos = (bx - 1, y)
            if model.cell_is_free(left_pos):
                guidance_positions.add(left_pos)
            
            # Right side guidance line (entire column)
            right_pos = (bx + 1, y)
            if model.cell_is_free(right_pos):
                guidance_positions.add(right_pos)
                
    except (ValueError, TypeError):
        pass
    
    return guidance_positions

def get_guidance_lines_for_boxes(model):
    """
    Generate vertical guidance lines on left and right sides of all boxes.
    Returns a set of (x, y) positions that are on guidance lines.
    This is used for visualization purposes.
    """
    guidance_positions = set()
    
    if not hasattr(model, 'boxes') or not model.boxes:
        return guidance_positions
    
    for box in model.boxes:
        try:
            if isinstance(box, dict) and 'pos' in box:
                pos = box['pos']
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    bx = int(pos[0])
                    
                    # Add full-height vertical lines on left and right sides of box
                    for y in range(model.H):  # Full grid height
                        # Left side guidance line
                        left_pos = (bx - 1, y)
                        if model.cell_is_free(left_pos):
                            guidance_positions.add(left_pos)
                        
                        # Right side guidance line  
                        right_pos = (bx + 1, y)
                        if model.cell_is_free(right_pos):
                            guidance_positions.add(right_pos)
        except (ValueError, TypeError, KeyError):
            continue
    
    return guidance_positions

def is_on_guidance_line_for_box(model, position, box_location):
    """
    Check if a position is on a vertical guidance line next to a specific target box.
    Returns True if position is on a guidance line for the target box, False otherwise.
    """
    if not isinstance(position, (tuple, list)) or len(position) < 2:
        return False
    
    if not isinstance(box_location, (list, tuple)) or len(box_location) < 2:
        return False
    
    try:
        x, y = int(position[0]), int(position[1])
        bx = int(box_location[0])
        
        # Check if position is on vertical line to left or right of the target box
        # Lines extend full height, so we only check x-coordinates
        if (x == bx - 1 or x == bx + 1):
            return model.cell_is_free((x, y))
            
    except (ValueError, TypeError):
        pass
    
    return False

def goal_cells(model, robot, box_location):
    """
    Objetivo según misión:
    - DELIVERY, sin caja: aproximación a la caja (celdas libres adyacentes a box_location)
    - DELIVERY, con caja: celda DROP exacta (robot.target)
    - RECHARGE: celda del cargador (robot.target)
    - RESTING: celda de descanso (robot.target) para que se desplace hacia allí
    """
    if robot.mission == "DELIVERY":
        if not robot.carrying:
            # box_location puede ser (x,y,h)
            if isinstance(box_location, (list, tuple)) and len(box_location) >= 2:
                return approach_cells_to_box(model, (box_location[0], box_location[1]), robot)
            return approach_cells_to_box(model, box_location, robot)
        if robot.target is not None:
            tgt = robot.target
            if isinstance(tgt, (list, tuple)) and len(tgt) >= 2:
                return [tuple(tgt[:2])]
            elif isinstance(tgt, (list, tuple)):
                return [tgt]
            else:
                return []
    elif robot.mission == "RECHARGE":
        if robot.target is not None:
            tgt = robot.target
            if isinstance(tgt, (list, tuple)) and len(tgt) >= 2:
                return [tuple(tgt[:2])]
            elif isinstance(tgt, (list, tuple)):
                return [tgt]
            else:
                return []
    elif robot.mission == "RESTING":
        if robot.target is not None:
            tgt = robot.target
            if isinstance(tgt, (list, tuple)) and len(tgt) >= 2:
                return [tuple(tgt[:2])]
            elif isinstance(tgt, (list, tuple)):
                return [tgt]
            else:
                return []
    return []

def closest_goal_and_dist(from_pos, goals):
    """Devuelve (gx, gy, dist) a la meta Manhattan más cercana. Si no hay metas: (from_pos, 0)."""
    if not goals:
        x, y = from_pos
        return x, y, 0
    x, y = from_pos
    best = None
    best_d = None
    for gx, gy in goals:
        d = abs(x - gx) + abs(y - gy)
        if best_d is None or d < best_d:
            best = (gx, gy)
            best_d = d
    return best[0], best[1], best_d

def manhattan(pos:tuple, target:tuple):
    x, y = pos
    xt = target[0]
    yt = target[1]
    return abs(xt-x) + abs(yt-y)

# ========================= Q-LEARNING ===============================
## (reward & feature constants imported)

def q_function(model, robot, action, box_location=None):
    """
    Q(s,a) = w^T φ(s,a)
    - model.global_weights: vector de pesos global de tamaño N_FEATURES
    - φ: vector por-bloques de tamaño N_FEATURES (FEAT_PER_ACT * len(ACTIONS))
    """
    if not hasattr(model, "global_weights") or len(model.global_weights) != N_FEATURES:
        model.global_weights = np.zeros(N_FEATURES, dtype=np.float32)

    f_sa = phi(model, robot, action, box_location)  # (N_FEATURES,)

    return float(np.dot(model.global_weights, f_sa))

def reward_fun(model, robot, action, prev_pos, next_pos, box_location=None, forced_wait_by_conflict=False):
    r = R_STEP

    goals = goal_cells(model, robot, box_location)
    if goals:
        _, _, d_prev = closest_goal_and_dist(prev_pos, goals)
        _, _, d_next = closest_goal_and_dist(next_pos, goals)
        
        # Enhanced distance shaping with stronger incentive
        distance_improvement = d_prev - d_next
        r += R_SHAPING_K * distance_improvement
        
        # Proximity bonuses - encourage getting very close to targets
        if d_next <= 3:  # Within 3 cells of goal
            r += R_PROXIMITY_BONUS
        if d_next <= 1:  # Adjacent to goal
            r += R_ADJACENT_BONUS
            
        # Inefficiency penalty - discourage moving away from target
        if distance_improvement < 0:  # Moving away from target
            r -= R_INEFFICIENCY_PENALTY

    # OJO: ahora revisamos estado POST-ACCIÓN (porque ya actualizaste en act())
    if action == "PICKUP" and robot.carrying:  # acaba de recoger
        if tuple(prev_pos) in approach_cells_to_box(model, box_location, robot):
            r += R_PICKUP

    if action == "DISCHARGE" and (not robot.carrying):  # acaba de descargar
        if robot.target is not None:
            tgt = robot.target
            tgt_xy = tuple(tgt[:2]) if isinstance(tgt, (list, tuple)) and len(tgt) >= 2 else tuple(tgt)
            if tuple(prev_pos) == tgt_xy:
                r += R_DROP

    if action == "RECHARGE" and tuple(prev_pos) in getattr(model, "recharge_points", []):
        r += R_RECHARGE

    # Small bonus for reaching resting points to avoid lingering
    if robot.mission == "RESTING" and robot.target is not None:
        tgt = robot.target
        tgt_xy = tuple(tgt[:2]) if isinstance(tgt, (list, tuple)) and len(tgt) >= 2 else tuple(tgt)
        if tuple(next_pos) == tgt_xy:
            r += 0.5  # Small completion bonus for reaching rest point

    if action in {"UP","DOWN","LEFT","RIGHT"} and tuple(next_pos) == tuple(prev_pos):
        r += R_BUMP

    if forced_wait_by_conflict:
        r += R_CONFLICT
    elif action == "WAIT":
        # Extra penalty for waiting when not forced by conflict
        r -= 0.05  # Encourage active exploration over waiting

    batt = float(getattr(robot, "battery", 100)) / 100.0
    if batt < LOW_BATT_THR and action != "RECHARGE":
        r += R_LOW_BATT

    # Enhanced navigation with pathfinding around obstacles
    if action in {"UP", "DOWN", "LEFT", "RIGHT"}:
        # Strong penalty for bumping into obstacles (trying to move through racks)
        if tuple(next_pos) == tuple(prev_pos):
            # Robot tried to move but didn't (hit obstacle)
            r -= 1.0  # Heavy penalty for bumping into racks/obstacles
            
            # Additional penalty if this is a repeated bump
            if hasattr(robot, 'consecutive_bumps'):
                robot.consecutive_bumps += 1
                r -= 0.5 * robot.consecutive_bumps  # Escalating penalty
            else:
                robot.consecutive_bumps = 1
        else:
            # Robot successfully moved - reset bump counter
            if hasattr(robot, 'consecutive_bumps'):
                robot.consecutive_bumps = 0
        
        # Pathfinding-aware navigation bonus
        if tuple(next_pos) != tuple(prev_pos) and goals:
            goal_pos = goals[0] if goals else None
            if goal_pos is not None:
                # Check if robot is following a good path around obstacles
                optimal_next = get_next_waypoint_around_obstacles(model, prev_pos, goal_pos)
                if optimal_next is not None and tuple(next_pos) == tuple(optimal_next):
                    r += 0.8  # Bonus for following optimal pathfinding route
                
                # Penalty for taking detours when direct path is available
                direct_next_x = prev_pos[0] + (1 if goal_pos[0] > prev_pos[0] else -1 if goal_pos[0] < prev_pos[0] else 0)
                direct_next_y = prev_pos[1] + (1 if goal_pos[1] > prev_pos[1] else -1 if goal_pos[1] < prev_pos[1] else 0)
                direct_next = (direct_next_x, direct_next_y)
                
                if (model.inbound(direct_next) and model.cell_is_free(direct_next) and 
                    tuple(next_pos) != direct_next and tuple(next_pos) != tuple(prev_pos)):
                    # Robot chose a non-direct path when direct was available
                    r -= 0.2  # Small penalty for unnecessary detours
        
        # Smart guidance line usage (only when appropriate)
        if robot.mission == "DELIVERY" and not robot.carrying and box_location is not None:
            # Encourage guidance lines, but only when they lead toward the target
            if is_on_guidance_line_for_box(model, next_pos, box_location):
                # Check if this guidance line actually helps reach the box
                if isinstance(box_location, (list, tuple)) and len(box_location) >= 2:
                    box_x, box_y = box_location[0], box_location[1]
                    robot_x, robot_y = next_pos[0], next_pos[1]
                    
                    # Only reward guidance line if it's helping reach the box
                    if (abs(robot_x - box_x) <= 1):  # Adjacent to target box column
                        r += 0.4  # Moderate bonus for appropriate guidance line use
        
        # Penalty for entering narrow aisles without proper navigation
        if model.is_narrow_aisle(next_pos):
            # Check if robot has a plan to navigate this aisle
            if goals:
                path_through_aisle = find_path_around_obstacles(model, next_pos, goals[0], max_search_distance=25)
                if not path_through_aisle:
                    r -= 0.5  # Penalty for entering dead-end aisles
        
        # Anti-oscillation penalty (enhanced)
        if hasattr(robot, 'stuck_counter') and robot.stuck_counter >= 2:
            r -= 0.3 * min(robot.stuck_counter, 5)  # Escalating penalty for being stuck

    return float(r)

def phi(model, robot, action, box_location=None):
    """
    φ por bloques de acción (12 features, con dx/dy y extras opcionales).
    Solo se llena el bloque de la acción actual; los demás van en cero.

    Bloque de 12:
      [0] bias_act        = 1.0
      [1] dist_next_norm  = dist(next -> goal) / max_dist
      [2] dx_norm         = (gx - x_next) / max_dx
      [3] dy_norm         = (gy - y_next) / max_dy
      [4] carrying        = 0/1
      [5] is_wait         = 1 si WAIT
      [6] is_pick         = 1 si PICKUP
      [7] is_drop         = 1 si DISCHARGE
      [8] is_recharge     = 1 si RECHARGE
      [9] battery_norm    = battery / 100
      [10] col_w_norm     = peso de columna normalizado [0..1] (si aplica)
      [11] acc_flag       = 1 si caja accesible (adyacencia libre), 0 en otro caso
    """
    # normalizadores
    W = max(1, getattr(model, "W", 0))
    H = max(1, getattr(model, "H", 0))
    max_dx = max(1, W - 1)
    max_dy = max(1, H - 1)
    max_dist = max_dx + max_dy

    # pos tentativa tras aplicar acción
    x, y = robot.position
    x_next, y_next = next_pos_from_action(model, (x, y), action)

    # metas
    goals = goal_cells(model, robot, box_location)
    gx, gy, dist_next = closest_goal_and_dist((x_next, y_next), goals)

    dist_next_norm = dist_next / max_dist
    dx_norm = (gx - x_next) / max_dx
    dy_norm = (gy - y_next) / max_dy

    # indicadores
    carrying     = 1.0 if robot.carrying else 0.0
    is_wait      = 1.0 if action == "WAIT" else 0.0
    is_pick      = 1.0 if action == "PICKUP" else 0.0
    is_drop      = 1.0 if action == "DISCHARGE" else 0.0
    is_recharge  = 1.0 if action == "RECHARGE" else 0.0
    battery_norm = float(getattr(robot, "battery", 100)) / 100.0

    # extras: col_w_norm y accesibilidad
    col_w_norm = 0.0
    acc_flag = 0.0
    try:
        if box_location is not None:
            bx = box_location[0] if isinstance(box_location, (list, tuple)) and len(box_location) >= 2 else None
            by = box_location[1] if isinstance(box_location, (list, tuple)) and len(box_location) >= 2 else None
            if bx is not None and by is not None:
                if hasattr(model, 'get_col_weight'):
                    cw = float(model.get_col_weight((bx, by)))
                    maxw = getattr(model, 'col_weight_max', 1.0) or 1.0
                    col_w_norm = max(0.0, min(1.0, cw / maxw))
                if hasattr(model, 'box_is_accessible'):
                    acc_flag = 1.0 if model.box_is_accessible((bx, by, 0)) else 0.0
    except Exception:
        pass

    # vector por bloques
    f = np.zeros(FEAT_PER_ACT * len(ACTIONS), dtype=np.float32)
    try:
        aidx = ACTIONS.index(action)
    except ValueError:
        aidx = ACTIONS.index("UP")

    off = FEAT_PER_ACT * aidx
    f[off + 0] = 1.0
    f[off + 1] = dist_next_norm
    f[off + 2] = dx_norm
    f[off + 3] = dy_norm
    f[off + 4] = carrying
    f[off + 5] = is_wait
    f[off + 6] = is_pick
    f[off + 7] = is_drop
    f[off + 8] = is_recharge
    f[off + 9] = battery_norm
    f[off + 10] = col_w_norm
    f[off + 11] = acc_flag

    return f

#  ========================= AGENTE ================================
DEFAULT_CONF = {
    "carrying": 0,
    "battery": 100,
    "target": None,
    "r_type": "A",
    "mission": None,
    "position": (0,0)
}

class Robot(ap.Agent):
    def setup(self, robot_conf=DEFAULT_CONF):
        if JSON_INITIALIZATION:
            pass

        self.carrying = bool(robot_conf.get("carrying", 0))
        self.battery = robot_conf.get("battery", 100)
        self.target = robot_conf.get("target", None)
        self.r_type = robot_conf.get("r_type", "A")
        pos = robot_conf.get("position", (0, 0))
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            self.position = (pos[0], pos[1])
        else:
            self.position = (0, 0)
        self.mission = robot_conf.get("mission", None)
        self.proposal = None

        self.box_location = None
        self.last_phi = None
        # Unity integration: default heading (0=UP) and last action string
        self.last_heading = 0
        self.last_action_str = "idle"
        
        # Anti-oscillation system
        self.movement_history = []  # Track last 4 movements
        self.stuck_counter = 0      # Count consecutive similar movements
        self.position_tracker = []  # Track recent positions
        self.action_success_counter = 0  # Track successful actions
        
        # Adaptive Behavior System
        self.behavior_mode = "NORMAL"  # Current behavior mode
        self.failure_history = {
            'movement_blocks': 0,
            'pickup_failures': 0, 
            'delivery_failures': 0,
            'pathfinding_failures': 0,
            'collision_count': 0
        }
        self.behavior_adaptations = {
            'patience_level': 1.0,      # How long to wait (1.0 = normal)
            'risk_tolerance': 1.0,      # How risky moves to attempt  
            'cooperation_level': 1.0,   # How much to help others
            'exploration_bias': 1.0,    # Preference for new vs known paths
            'task_flexibility': 1.0     # Willingness to switch tasks
        }
        self.successful_strategies = []  # Track what works for this robot
        self.behavior_change_cooldown = 0  # Prevent rapid behavior changes

    def json_setup(self, info):
        self.carrying = bool(info.get("carrying", 0))
        self.battery = info.get("battery", 100)
        self.target = info.get("target", None)
        self.r_type = info.get("r_type", "A")
        pos = info.get("position", info.get("pos", (0, 0)))
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            self.position = (pos[0], pos[1])
        else:
            self.position = (0, 0)
        self.mission = info.get("mission", None)
        # Mantener id existente si no viene en el JSON
        if "id" in info:
            self.id = info["id"]
        self.proposal = None

        self.box_location = None
        self.last_phi = None
        # Unity integration: default heading (0=UP) and last action string
        self.last_heading = 0
        self.last_action_str = "idle"
        
        # Anti-oscillation system
        self.movement_history = []  # Track last 4 movements
        self.stuck_counter = 0      # Count consecutive similar movements
        self.position_tracker = []  # Track recent positions
        self.action_success_counter = 0  # Track successful actions

    def set_robot_id(self, rid):
        self.id = int(rid)
    
    def detect_oscillation(self, proposed_action):
        """Detect if robot is oscillating between positions"""
        if proposed_action not in ["UP", "DOWN", "LEFT", "RIGHT"]:
            return False
            
        # Keep track of last 4 movements
        self.movement_history.append(proposed_action)
        if len(self.movement_history) > 4:
            self.movement_history.pop(0)
            
        # Check for oscillation patterns (e.g., UP-DOWN-UP-DOWN)
        if len(self.movement_history) >= 4:
            # Check for vertical oscillation
            if (self.movement_history == ["UP", "DOWN", "UP", "DOWN"] or 
                self.movement_history == ["DOWN", "UP", "DOWN", "UP"]):
                self.stuck_counter += 1
                return True
                
            # Check for horizontal oscillation
            if (self.movement_history == ["LEFT", "RIGHT", "LEFT", "RIGHT"] or 
                self.movement_history == ["RIGHT", "LEFT", "RIGHT", "LEFT"]):
                self.stuck_counter += 1
                return True
                
        # Reset counter if no oscillation
        self.stuck_counter = 0
        return False
    
    def get_pathfinding_action(self, feasible_actions, goal_pos):
        """Get the best action using pathfinding to avoid obstacles"""
        if not goal_pos or not feasible_actions:
            return None
        
        # Get optimal next position using pathfinding
        optimal_next = get_next_waypoint_around_obstacles(self.model, self.position, goal_pos)
        if optimal_next is None:
            return None
        
        # Find action that leads to optimal position
        for action in feasible_actions:
            if action in DIRS:
                next_pos = next_pos_from_action(self.model, self.position, action)
                if tuple(next_pos) == tuple(optimal_next):
                    return action
        
        return None

    def get_guidance_line_navigation_action(self, feasible_actions, box_location):
        """Get the best action to move towards guidance lines for target box"""
        if not box_location or self.mission != "DELIVERY" or self.carrying:
            return None
            
        box_x = int(box_location[0]) if len(box_location) > 0 else 0
        current_x, current_y = self.position
        
        # Check if we're already on a guidance line
        if is_on_guidance_line_for_box(self.model, self.position, box_location):
            # We're on a guidance line, now move towards the box
            if current_x < box_x - 1:  # We're too far left, move right to left guidance line
                return "RIGHT" if "RIGHT" in feasible_actions else None
            elif current_x > box_x + 1:  # We're too far right, move left to right guidance line  
                return "LEFT" if "LEFT" in feasible_actions else None
            elif current_x == box_x - 1 or current_x == box_x + 1:
                # We're on the correct guidance line, move vertically towards box
                box_y = int(box_location[1]) if len(box_location) > 1 else 0
                if current_y < box_y:
                    return "DOWN" if "DOWN" in feasible_actions else None
                elif current_y > box_y:
                    return "UP" if "UP" in feasible_actions else None
        else:
            # We're not on a guidance line, move towards the nearest one
            left_guidance_x = box_x - 1
            right_guidance_x = box_x + 1
            
            # Choose the closest guidance line
            dist_to_left = abs(current_x - left_guidance_x)
            dist_to_right = abs(current_x - right_guidance_x)
            
            if dist_to_left <= dist_to_right:
                # Move towards left guidance line
                if current_x < left_guidance_x:
                    return "RIGHT" if "RIGHT" in feasible_actions else None
                elif current_x > left_guidance_x:
                    return "LEFT" if "LEFT" in feasible_actions else None
            else:
                # Move towards right guidance line
                if current_x < right_guidance_x:
                    return "RIGHT" if "RIGHT" in feasible_actions else None
                elif current_x > right_guidance_x:
                    return "LEFT" if "LEFT" in feasible_actions else None
        
        return None

    def get_anti_oscillation_actions(self, feasible_actions, box_location=None):
        """Get alternative actions to break oscillation"""
        alternative_actions = []
        
        # If we have a target box, prefer guidance line movements
        if box_location is not None and self.mission == "DELIVERY" and not self.carrying:
            guidance_action = self.get_guidance_line_navigation_action(feasible_actions, box_location)
            if guidance_action:
                alternative_actions.append(guidance_action)
                
            # Also add direct guidance line movements
            for action in ["LEFT", "RIGHT", "UP", "DOWN"]:
                if action in feasible_actions:
                    next_pos = next_pos_from_action(self.model, self.position, action)
                    if is_on_guidance_line_for_box(self.model, next_pos, box_location):
                        alternative_actions.append(action)
        
        # If no guidance line actions available, try perpendicular movements
        if not alternative_actions:
            recent_moves = self.movement_history[-2:] if len(self.movement_history) >= 2 else []
            if recent_moves:
                last_move = recent_moves[-1]
                # If last move was vertical, try horizontal
                if last_move in ["UP", "DOWN"]:
                    for action in ["LEFT", "RIGHT"]:
                        if action in feasible_actions:
                            alternative_actions.append(action)
                # If last move was horizontal, try vertical
                elif last_move in ["LEFT", "RIGHT"]:
                    for action in ["UP", "DOWN"]:
                        if action in feasible_actions:
                            alternative_actions.append(action)
        
        # Last resort: try WAIT
        if not alternative_actions and "WAIT" in feasible_actions:
            alternative_actions.append("WAIT")
            
        return alternative_actions

    def valid_actions(self, x:int, y:int, carrying:bool, target:tuple, mission:str, box_location:tuple):
        valid = []
        # Prefer movement options first
        for act, (dx, dy) in DIRS.items():
            cand = (x + dx, y + dy)
            if self.model.cell_is_free(cand):
                valid.append(act)

        if mission == "DELIVERY":
            if carrying and target is not None:
                tgt_xy = tuple(target[:2]) if isinstance(target, (list, tuple)) and len(target) >= 2 else tuple(target)
                # Use safe zone for drop accessibility
                drop_access_cells = ensure_drop_zone_accessibility(self.model, target)
                if (x, y) == tgt_xy or (x, y) in drop_access_cells:
                    valid.append("DISCHARGE")
            elif (not carrying):
                if isinstance(box_location, (list, tuple)) and len(box_location) >= 2:
                    bx, by = box_location[0], box_location[1]
                    if (x, y) in approach_cells_to_box(self.model, (bx, by), self):
                        valid.append("PICKUP")
                elif box_location is not None:
                    if (x, y) in approach_cells_to_box(self.model, box_location, self):
                        valid.append("PICKUP")

        # Recharge only at actual charger cells. In RESTING, permit only if low battery.
        if (mission == "RECHARGE" and self.battery < 100) or (mission == "RESTING" and self.battery < 10):
            if (not carrying) and target is not None:
                tgt_xy = tuple(target[:2]) if isinstance(target, (list, tuple)) and len(target) >= 2 else tuple(target)
                if (x, y) == tgt_xy and tgt_xy in self.model.recharge_points:
                    valid.append("RECHARGE")

        # WAIT is always feasible; append last so tie-breakers deprioritize it
        valid.append("WAIT")
        return valid

    def plan(self, box_location=None):
        # Enforce preferred drop point target when carrying
        try:
            if self.carrying and hasattr(self, 'drop_pref'):
                dp = getattr(self, 'drop_pref')
                if isinstance(dp, (list, tuple)) and len(dp) >= 2:
                    if (not self.target) or tuple(self.target[:2]) != (dp[0], dp[1]):
                        self.target = (dp[0], dp[1], 0)
                        self.mission = "DELIVERY"
        except Exception:
            pass
        feasible = self.valid_actions(
            *self.position,
            self.carrying,
            self.target,
            self.mission,
            box_location
        )


        # Simple stuck recovery
        if hasattr(self, 'is_really_stuck') and self.is_really_stuck():
            # Force mission reset for really stuck robots
            self.mission = None
            self.target = None
            if hasattr(self, 'position_tracker'):
                self.position_tracker.clear()
            print(f"Robot {getattr(self, 'id', '?')} was stuck, resetting mission")
        
        # Adaptive Behavior System - analyze failures instead of simple reset
        if hasattr(self, 'action_success_counter') and self.action_success_counter >= 8:
            # Record failure type for analysis
            self.record_failure_type()
            
            # Apply behavioral adaptations instead of resetting
            if self.action_success_counter >= 15:
                self.model.analyze_failure_pattern(self)
                
                # Smart mission reassignment based on behavior mode
                if self.behavior_mode == "PATIENT_MOVER":
                    # Find easier movement targets
                    self.find_accessible_mission()
                elif self.behavior_mode == "FLEXIBLE_PICKER":
                    # Switch to delivery if carrying, pickup if not
                    if self.carrying:
                        self.mission = "EMERGENCY_DELIVERY"
                        self.target = self.model.find_nearest_available_drop(self.position)
                    else:
                        self.mission = "PICKUP_PRIORITY" 
                        self.target = self.model.find_easiest_pickup(self.position)
                elif self.behavior_mode == "EXPLORER":
                    # Keep current mission but explore new paths
                    self.target = self.model.find_alternative_target(self.position, self.mission)
                else:
                    # Default: smart reassignment instead of None
                    if self.carrying:
                        self.mission = "DELIVERY"
                        self.target = self.model.find_nearest_available_drop(self.position)
                    else:
                        self.mission = "PICKUP"
                        self.target = self.model.find_nearest_available_pickup(self.position)
                
                self.action_success_counter = 0
                print(f"🧠 Robot {getattr(self, 'id', '?')} adapted behavior: {self.behavior_mode}")


        # Diagnostics: check opportunities
        had_pick = ("PICKUP" in feasible)
        had_drop = ("DISCHARGE" in feasible)
        if had_pick:
            try:
                self.model.stats["pickup_opportunities"] += 1
            except Exception:
                pass
        if had_drop:
            try:
                self.model.stats["drop_opportunities"] += 1
            except Exception:
                pass

        # Prioritize critical actions deterministically
        if had_drop:
            self.proposal = "DISCHARGE"
        elif had_pick:
            self.proposal = "PICKUP"
        elif ("RECHARGE" in feasible) and (self.battery < 10):
            self.proposal = "RECHARGE"
        else:
            # ε-greedy among remaining feasible actions
            if random.random() > self.model.global_epsilon:  # EXPLOIT (1-ε)
                qvals = {act: q_function(self.model, self, act, box_location) for act in feasible}
                best_action = max(
                    feasible,
                    key=lambda act: (qvals[act], 0 if act != "WAIT" else -1)
                )
                
                # Check for oscillation before committing to action
                if self.detect_oscillation(best_action) and self.stuck_counter >= 2:
                    # Try pathfinding solution first for stuck robots
                    goals = goal_cells(self.model, self, box_location)
                    if goals:
                        gx, gy, _ = closest_goal_and_dist(self.position, goals)
                        pathfinding_action = self.get_pathfinding_action(feasible, (gx, gy))
                        
                        if pathfinding_action and pathfinding_action != best_action:
                            self.proposal = pathfinding_action
                            self.stuck_counter = 0  # Reset counter
                        else:
                            # Fall back to anti-oscillation actions
                            alternative_actions = self.get_anti_oscillation_actions(feasible, box_location)
                            if alternative_actions:
                                self.proposal = random.choice(alternative_actions)
                                self.stuck_counter = 0  # Reset counter
                            else:
                                self.proposal = best_action
                    else:
                        # No goals - use anti-oscillation actions
                        alternative_actions = self.get_anti_oscillation_actions(feasible, box_location)
                        if alternative_actions:
                            self.proposal = random.choice(alternative_actions)
                            self.stuck_counter = 0  # Reset counter
                        else:
                            self.proposal = best_action
                else:
                    self.proposal = best_action
                    
            else:  # EXPLORE (ε)
                # Smart pathfinding-aware exploration
                goals = goal_cells(self.model, self, box_location)
                if goals:
                    gx, gy, d0 = closest_goal_and_dist(self.position, goals)
                    goal_pos = (gx, gy)
                    
                    # 1. Try pathfinding action first (highest priority)
                    pathfinding_action = self.get_pathfinding_action(feasible, goal_pos)
                    
                    # 2. Collect guidance line actions as backup
                    guidance_actions = []
                    better = []
                    
                    for act in feasible:
                        if act in DIRS:
                            nx, ny = next_pos_from_action(self.model, self.position, act)
                            d1 = abs(gx - nx) + abs(gy - ny)
                            
                            # Check if this move would put us on guidance lines to target box
                            if (self.mission == "DELIVERY" and not self.carrying and 
                                box_location is not None and 
                                is_on_guidance_line_for_box(self.model, (nx, ny), box_location)):
                                guidance_actions.append(act)
                            
                            if d1 < d0:
                                better.append(act)
                    
                    # 3. Smart guidance line navigation as tertiary option
                    smart_guidance_action = None
                    if (self.mission == "DELIVERY" and not self.carrying and box_location is not None):
                        smart_guidance_action = self.get_guidance_line_navigation_action(feasible, box_location)
                    
                    # Priority order: pathfinding > smart guidance > guidance lines > better moves
                    if pathfinding_action and random.random() < 0.9:
                        chosen_action = pathfinding_action
                    elif smart_guidance_action and random.random() < 0.8:
                        chosen_action = smart_guidance_action
                    elif guidance_actions and random.random() < 0.6:
                        chosen_action = random.choice(guidance_actions)
                    elif better:
                        chosen_action = random.choice(better)
                    else:
                        non_wait = [a for a in feasible if a != "WAIT"]
                        chosen_action = random.choice(non_wait) if non_wait else "WAIT"
                    
                    # Anti-oscillation check during exploration
                    if self.detect_oscillation(chosen_action) and self.stuck_counter >= 2:
                        alternative_actions = self.get_anti_oscillation_actions(feasible, box_location)
                        if alternative_actions:
                            self.proposal = random.choice(alternative_actions)
                            self.stuck_counter = 0
                        else:
                            self.proposal = chosen_action
                    else:
                        self.proposal = chosen_action
                else:
                    non_wait = [a for a in feasible if a != "WAIT"]
                    self.proposal = random.choice(non_wait) if non_wait else "WAIT"

        # Apply adaptive behavior modifications to the selected action
        if hasattr(self, 'behavior_adaptations') and self.proposal:
            modified_action = self.model.apply_behavioral_modifications(self, self.proposal)
            if modified_action is not None:
                self.proposal = modified_action
            # Record last action for failure analysis
            self.last_action = self.proposal

        # Diagnostics: missed critical actions (only if not chosen)
        if had_pick and self.proposal != "PICKUP":
            try:
                self.model.stats["pickup_missed"] += 1
            except Exception:
                pass
        if had_drop and self.proposal != "DISCHARGE":
            try:
                self.model.stats["drop_missed"] += 1
            except Exception:
                pass

        # Guardar el último phi para actualizar después de resolver conflictos
        self.box_location = box_location
        self.last_phi = phi(self.model, self, self.proposal, box_location)

    def act(self):
        self.last_phi = phi(self.model, self, self.proposal, self.box_location)
        prev_pos = self.position
        a = self.proposal

        # Movimiento tentativo
        next_pos = next_pos_from_action(self.model, prev_pos, a)

        # Bump statistic: attempted move but stayed in place
        if a in DIRS and tuple(next_pos) == tuple(prev_pos):
            try:
                self.model.stats["bumps"] += 1
                self.model._bumps_this_step += 1
            except Exception:
                pass

        # Unity-facing action/heading tracking and per-tick action event
        try:
            unity_action = ACTION_TO_UNITY.get(a, "idle")
            # Update robot memory
            self.last_action_str = unity_action
            if a in MOVE_TO_HEADING:
                self.last_heading = int(MOVE_TO_HEADING[a])
            # Collect per-tick actions on the model (cleared each step)
            if hasattr(self.model, 'action_events') and isinstance(self.model.action_events, list):
                self.model.action_events.append({"robot_id": int(getattr(self, 'id', -1)), "action": unity_action})
        except Exception:
            pass

        # Coste/recarga de batería (post-acción)
        if a == "RECHARGE":
            self.battery = min(self.battery + 5, 100)
            # If fully charged, leave charger to a RESTING point
            if self.battery >= 100:
                self.mission = "RESTING"
                rp = self.model.closest_pick(self.position, self.model.resting_points, self.model.resting_point_free)
                self.target = (rp[0], rp[1], 0) if rp is not None else None
        elif a == "WAIT":
            self.battery = max(self.battery - 0.05, 0)
        else:
            self.battery = max(self.battery - 0.10, 0)
        
        # Track position for balanced stuck detection
        self.position_tracker.append(self.position)
        
        # Track successful actions
        if a in ["PICKUP", "DISCHARGE"]:
            self.action_success_counter = 0  # Reset - we did something useful
            # Record successful strategy for adaptive behavior
            if hasattr(self, 'behavior_mode') and self.behavior_mode != "NORMAL":
                strategy_context = f"{a}_success_with_{self.behavior_mode}"
                self.model.record_successful_strategy(self, strategy_context)
        elif a in DIRS and tuple(next_pos) != tuple(prev_pos):
            self.action_success_counter = 0  # Reset - we moved successfully
            # Record successful movement strategy
            if hasattr(self, 'behavior_mode') and self.behavior_mode != "NORMAL":
                strategy_context = f"movement_success_with_{self.behavior_mode}"
                self.model.record_successful_strategy(self, strategy_context)
        else:
            self.action_success_counter += 1  # Increment failure counter


        # Actualizar carrying antes de recompensa para coherencia del reward
        if a == "PICKUP":
            self.carrying = True
            self.model.stats["pickups"] += 1
            # Handle visual pickup for box hiding
            if hasattr(self, 'box_location') and self.box_location:
                self.model.handle_box_pickup(self, self.box_location)
            try:
                self.model._picked_this_step += 1
            except Exception:
                pass
        elif a == "DISCHARGE":
            self.carrying = False
            self.model.stats["deliveries"] += 1
            # Handle visual delivery for box respawn
            if hasattr(self, 'box_location') and self.box_location:
                self.model.handle_box_delivery(self, self.box_location)
            # Episodic delivery tracking
            try:
                if getattr(self.model, 'training_mode', False):
                    # Training mode: only count first delivery per robot, cap at robot count
                    if (not hasattr(self, 'deliveries_this_episode') or 
                        self.deliveries_this_episode == 0):
                        # Only count if we haven't exceeded the robot limit
                        if self.model.episode_delivery_count < len(self.model.robots):
                            self.deliveries_this_episode = 1
                            self.model.episode_delivery_count += 1
                            self.model._delivered_this_step += 1
                            # Terminate when we reach the target deliveries
                            if self.model.episode_delivery_count >= len(self.model.robots):
                                self.model.episode_terminated = True
                else:
                    # Visualization mode: count all deliveries
                    if hasattr(self, 'deliveries_this_episode'):
                        self.deliveries_this_episode += 1
                    else:
                        self.deliveries_this_episode = 1
                    self.model._delivered_this_step += 1
            except Exception:
                pass

        # Q(s,a) desde last_phi evita inconsistencias de estado
        current_q = float(np.dot(self.model.global_weights, self.last_phi)) if self.last_phi is not None else q_function(self.model, self, a, self.box_location)

        # Recompensa: para DISCHARGE, aún no cambiamos mission/target para validar DROP correctamente
        reward = reward_fun(self.model, self, a, prev_pos, next_pos, self.box_location,
                            self.id in self.model.forced_wait_by_conflict)
        self.model.stats["reward_hist"].append(reward)
        try:
            self.model.stats["success_hist"].append(1 if reward > 0 else 0)
        except Exception:
            pass

        # Update action statistics
        if a == "WAIT":
            self.model.stats["waits"] += 1
        elif a == "RECHARGE":
            self.model.stats["recharges"] += 1
        elif a in ["UP", "DOWN", "LEFT", "RIGHT"]:
            self.model.stats["moves"] += 1

        # Ahora sí, completar transición de misión/target tras entregar
        if a == "DISCHARGE":
            # Release the drop point reservation
            self.model.release_drop_point(self.id)
            
            # Clear current mission to make robot available for reassignment
            self.mission = None
            self.target = None
            self.box_location = None
            # Clear from current missions
            if hasattr(self.model, 'current_missions') and self.id in self.model.current_missions:
                del self.model.current_missions[self.id]

        # Aplicar la transición de posición al estado siguiente antes de Q(s',a')
        self.position = next_pos

        # Q(s',a') mejor
        feasible = self.valid_actions(*self.position, self.carrying, self.target, self.mission, self.box_location)
        q_vals = [q_function(self.model, self, act, self.box_location) for act in feasible]
        next_best_q = max(q_vals) if q_vals else 0.0

        td = reward + GAMMA * next_best_q - current_q
        self.model.stats["td_hist"].append(td)
        if self.last_phi is not None:
            self.model.global_weights += ALPHA * td * self.last_phi

# ======================== MODELO =====================================        # Check if we've been in the same few positions for too long
        recent_positions = self.position_tracker[-5:]
        unique_positions = len(set(recent_positions))
        
        # If we've only been in 1-2 positions in last 5 steps, we're stuck
        return unique_positions <= 2
    
    def record_failure_type(self):
        """Record the type of failure for behavioral analysis"""
        if not hasattr(self, 'failure_history'):
            return
            
        # Determine failure type based on context
        if hasattr(self, 'last_action') and self.last_action in ["UP", "DOWN", "LEFT", "RIGHT"]:
            # Movement failure
            if self.model.cell_has_robot_or_obstacle(next_pos_from_action(self.model, self.position, self.last_action)):
                self.failure_history['collision_count'] += 1
            else:
                self.failure_history['movement_blocks'] += 1
        elif self.mission == "DELIVERY" and not self.carrying:
            self.failure_history['pickup_failures'] += 1
        elif self.mission == "DELIVERY" and self.carrying:
            self.failure_history['delivery_failures'] += 1
        elif hasattr(self, 'last_action') and self.last_action == "PICKUP":
            self.failure_history['pickup_failures'] += 1
        else:
            self.failure_history['pathfinding_failures'] += 1
    
    def find_accessible_mission(self):
        """Find an accessible mission for patient movers"""
        # Look for resting points or easy targets
        if not self.carrying:
            self.mission = "RESTING"
            resting_points = getattr(self.model, 'resting_points', [])
            if resting_points:
                self.target = self.model.closest_pick(self.position, resting_points, lambda p: True)
        else:
            self.mission = "DELIVERY"
            # Find closest drop point
            drop_points = getattr(self.model, 'drop_points', [])
            if drop_points:
                self.target = self.model.closest_pick(self.position, drop_points, lambda p: True)

class Warehouse(ap.Model):
    def setup(self):
        # 1. cargar JSON (permite parámetro config_path)
        cfg_path = None
        try:
            # agentpy expone parámetros en self.p
            cfg_path = getattr(self, 'p', {}).get('config_path', 'layout.json')
        except Exception:
            cfg_path = 'layout.json'
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # Validar JSON (best-effort)
        try:
            self._validate_config(cfg)
        except Exception:
            pass

        # 2. diccionario robots
        n_robots = len(cfg.get("robots", []))

        # 3. Process boxes with rack slot mapping
        racks = {r["id"]: r for r in cfg.get("entities", {}).get("racks", [])}
        self.boxes = cfg.get("boxes", [])

        # Convert rack slots to positions
        for b in self.boxes:
            if "pos" not in b and "rack_id" in b and "slot" in b:
                rack = racks.get(b["rack_id"])
                if rack and "rect" in rack:
                    # Calculate position from rack rect and slot
                    rack_rect = rack["rect"]
                    slot = b["slot"]
                    bay = slot.get("bay", 0)
                    level = slot.get("level", 0)
                    
                    # For vertical racks (h > w), bay maps to y-direction
                    # For horizontal racks (w > h), bay maps to x-direction
                    if rack_rect["h"] >= rack_rect["w"]:
                        # Vertical rack
                        x = rack_rect["x"]
                        y = rack_rect["y"] + (bay % rack_rect["h"])
                    else:
                        # Horizontal rack
                        x = rack_rect["x"] + (bay % rack_rect["w"])
                        y = rack_rect["y"]
                    
                    h = level
                    b["pos"] = [x, y, h]

        # Assign box levels based on robot count and new level system:
        # Levels: 1,2 for robots 1&2, levels 3,4 for robots 3&4
        # 1 robot: 1 box level 1
        # 2 robots: 1 box level 1, 1 box level 2  
        # 3 robots: 1 box level 1, 1 box level 2, 1 box level 3
        # 4 robots: 1 box level 1, 1 box level 2, 1 box level 3, 1 box level 4
        
        if n_robots == 1:
            box_levels = [1]  # Only level 1 for robot 1
        elif n_robots == 2:
            box_levels = [1, 2]  # Levels 1,2 for robots 1&2
        elif n_robots == 3:
            box_levels = [1, 2, 3]  # Levels 1,2 for robots 1&2, level 3 for robot 3
        elif n_robots >= 4:
            box_levels = [1, 2, 3, 4]  # All levels
        else:
            box_levels = [1]
        
        total_boxes_needed = len(box_levels)
        
        # Only keep the exact number of boxes needed and assign proper levels
        active_boxes = []
        for i in range(min(total_boxes_needed, len(self.boxes))):
            b = self.boxes[i]
            if isinstance(b, dict) and "pos" in b:
                pos = b["pos"]
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    # Assign level from the progression
                    level = box_levels[i]
                    
                    # Update box position with correct level
                    b_copy = dict(b)  # Make a copy to avoid modifying original
                    if len(pos) >= 3:
                        b_copy["pos"] = [pos[0], pos[1], level]
                    else:
                        b_copy["pos"] = [pos[0], pos[1], level]
                    active_boxes.append(b_copy)
        
        # Replace the boxes list with only the active ones
        self.boxes = active_boxes

        # 4. lista de celdas bloqueadas, puntos de entrega y de recolección
        rows = cfg["tilemap"]["walkable"]
        self.H, self.W = len(rows), len(rows[0])
        legend = cfg["tilemap"]["legend"]
        walkable = [[bool(legend[rows[y][x]]) for x in range(self.W)] for y in range(self.H)]
        self.occupied = {(x,y) for y in range(self.H) for x in range(self.W) if not walkable[y][x]}

        self.drop_points = []
        self.recharge_points = []
        self.spawn_points = []
        self.resting_points = []
        
        # Drop point reservation system to prevent congestion
        self.reserved_drop_points = set()  # Currently reserved drop points
        self.drop_point_assignments = {}   # robot_id -> drop_point mapping

        for cell in cfg.get("tags", []):
            if cell["type"] == "DROP": self.drop_points.append(tuple(cell["pos"]))
            if cell["type"] == "CHARGE": self.recharge_points.append(tuple(cell["pos"]))
            if cell["type"] == "SPAWN": self.spawn_points.append(tuple(cell["pos"]))
            if cell["type"] == "REST": self.resting_points.append(tuple(cell["pos"]))

        # If no explicit REST tags provided, derive resting points away from chargers.
        # Do NOT use SPAWN as resting to avoid clustering on a single spawn cell.
        if not self.resting_points:
            rest_candidates = set()
            for cx, cy in self.recharge_points:
                for nx, ny in neighbors4(cx, cy):
                    if self.cell_is_free((nx, ny)) and (nx, ny) not in self.recharge_points:
                        rest_candidates.add((nx, ny))
            self.resting_points = list(rest_candidates)
        
        # Initialize available spawn points for box respawning (free cells away from service points)
        self._initialize_box_spawn_points()
        
        # Box respawning control - enabled by default for simulation, disabled for training
        self.box_respawn_enabled = getattr(self, 'box_respawn_enabled', True)
        self.training_mode = getattr(self, 'training_mode', False)

        # Pesos de columna opcionales
        self.col_weight = {}
        colw = cfg.get("col_weights")
        if isinstance(colw, list):
            for item in colw:
                try:
                    pos = item.get("pos")
                    w = float(item.get("w", 1.0))
                    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        self.col_weight[(int(pos[0]), int(pos[1]))] = w
                except Exception:
                    continue
        elif isinstance(colw, dict):
            for k, v in colw.items():
                try:
                    if isinstance(k, str) and "," in k:
                        xs, ys = k.split(",", 1)
                        pos = (int(xs), int(ys))
                    elif isinstance(k, (list, tuple)) and len(k) >= 2:
                        pos = (int(k[0]), int(k[1]))
                    else:
                        continue
                    self.col_weight[pos] = float(v)
                except Exception:
                    continue
        self.col_weight_max = max(self.col_weight.values()) if self.col_weight else 1.0

        # 5. Inicializa la lista de agentes con los datos del JSON
        self.robots = ap.AgentList(self, n_robots, Robot)
        for robot, info in zip(self.robots, cfg.get("robots", [])):
            robot.json_setup(info)
            # If robot starts without a mission, send it to nearest resting point so it moves
            if robot.mission is None:
                robot.mission = "RESTING"
                # During setup, 'intended' isn't defined yet; ignore occupancy when picking
                rp = self.closest_pick(robot.position, self.resting_points, lambda p: True)
                robot.target = (rp[0], rp[1], 0) if rp is not None else None

        # Assign robot capabilities and preferred drop points
        try:
            if self.drop_points:
                for rb in self.robots:
                    rb.drop_pref = tuple(self.drop_points[rb.id % len(self.drop_points)])
                    # Robot capabilities: 
                    # - Robots 1&2 (id 0,1): Can access levels 1&2 (low-medium levels)
                    # - Robots 3&4 (id 2,3): Can access levels 3&4 (high levels)
                    if rb.id <= 1:
                        rb.access_levels = [1, 2]  # Robots 1&2 access levels 1&2
                    else:
                        rb.access_levels = [3, 4]  # Robots 3&4 access levels 3&4
                    
                    # Backward compatibility with old system
                    rb.can_access_high = (rb.id >= 2)
        except Exception:
            pass

        # 6. Inicializa indicadores y datos de Q-learning
        self.n_features = N_FEATURES
        self.global_epsilon = EPSILON_START
        # Auto-cycle reset is disabled by default; visualization can enable it
        self.auto_cycle_reset = False
        # Expose cycle target for visualizer HUD
        self.CYCLE_DELIVERIES_TARGET = CYCLE_DELIVERIES_TARGET
        # Counter to cycle drop points when seeding missions so early missions map predictably
        self._mission_seed_counter = 0

        # Silent pretrained weight loading
        if PRETRAIN_ENABLED and os.path.exists("W_linear.npy"):
            try:
                self.global_weights = np.load("W_linear.npy").astype(np.float32)
                if self.global_weights.shape[0] != N_FEATURES:
                    self.global_weights = np.zeros(N_FEATURES, dtype=np.float32)
            except Exception:
                self.global_weights = np.zeros(N_FEATURES, dtype=np.float32)
        else:
            self.global_weights = np.zeros(N_FEATURES, dtype=np.float32)

        # Estado de planificación y misiones
        self.intended = {}  # dict[(x,y)] -> [Robot,...] para resolución de conflictos
        self.current_missions = {}  # ROBOT_ID -> {box_location, target, mission}
        self.pending_missions = []
        self.forced_wait_by_conflict = set()
        
        # Box visibility tracking for visualization
        self.picked_boxes = set()  # Track which boxes are currently picked up
        self.delivered_boxes = set()  # Track which boxes have been delivered (training mode)
        self.available_spawn_points = []  # Potential respawn locations for boxes

        # --- Métricas / logging ---
        self.stats = {
            "step": 0,
            "reward_hist": [],
            "success_hist": [],
            "delivery_hist": [],
            "pickup_hist": [],
            "td_hist": [],
            "deliveries": 0,
            "pickups": 0,
            "conflicts": 0,
            "moves": 0,
            "waits": 0,
            "recharges": 0,
            "bumps": 0,
            "forced_waits": 0,
            # Per-step event histograms for plotting/export
            "bump_hist": [],
            "forced_wait_hist": [],
            # Diagnostics: action opportunities vs choices
            "pickup_opportunities": 0,
            "pickup_missed": 0,
            "drop_opportunities": 0,
            "drop_missed": 0,
            "dist_reduced_sum": 0.0,
            "dist_steps": 0,
            "episodes": 0,
            "episode_rewards": [],
            "avg_reward": 0.0,
            "epsilon": self.global_epsilon
        }
        # Unity actions envelope: per-tick events collected in step()
        self.action_events = []
        # Backward-compat for external scripts that expect _stats
        self._stats = self.stats

        # Sembrar misiones aleatorias para pruebas
        try:
            # Use instance cycle target (allows dynamic adjustment for visualization modes)
            self.seed_random_missions(self.CYCLE_DELIVERIES_TARGET)
        except Exception:
            pass

    def reset_cycle(self):
        """Reset missions and per-cycle counters after reaching delivery target."""
        # Bump a simple cycle counter stored in episodes for visibility
        try:
            self.stats["episodes"] = int(self.stats.get("episodes", 0)) + 1
        except Exception:
            self.stats["episodes"] = 1

        # Clear mission state
        self.current_missions = {}
        self.pending_missions = []
        self.intended = {}
        self.forced_wait_by_conflict = set()

        # Send robots to resting and clear transient flags
        for rb in getattr(self, 'robots', []):
            rb.carrying = False
            rb.mission = "RESTING"
            rp = self.closest_pick(rb.position, self.resting_points, self.resting_point_free)
            rb.target = (rp[0], rp[1], 0) if rp is not None else None
            rb.proposal = None
            rb.box_location = None

        # Reset per-cycle counters and short histories for clarity in the HUD
        for k in ["deliveries", "pickups", "conflicts", "moves", "waits", "recharges"]:
            try:
                self.stats[k] = 0
            except Exception:
                pass
        try:
            self.stats["reward_hist"] = []
            self.stats["success_hist"] = []
            self.stats["delivery_hist"] = []
            self.stats["pickup_hist"] = []
            self.stats["td_hist"] = []
            self.stats["avg_reward"] = 0.0
        except Exception:
            pass

        # Seed a fresh batch of missions (aiming for the new cycle target)
        try:
            self.seed_random_missions(self.CYCLE_DELIVERIES_TARGET)
        except Exception:
            pass

    def set_cycle_target(self, deliveries:int):
        """Dynamically adjust how many deliveries constitute a visualization 'cycle'.
        Updates the instance variable and reseeds missions accordingly.
        """
        try:
            deliveries = int(deliveries)
            if deliveries <= 0:
                return
            self.CYCLE_DELIVERIES_TARGET = deliveries
            # Reseed missions to match new cycle size if current pending is empty
            if not self.pending_missions:
                try:
                    self.seed_random_missions(self.CYCLE_DELIVERIES_TARGET)
                except Exception:
                    pass
        except Exception:
            pass

    def inbound(self, p : tuple):
        x, y = p
        return (0 <= x < self.W and 0 <= y < self.H)

    def is_blocked(self, p : tuple):
        return (p in self.occupied)

    def _initialize_box_spawn_points(self):
        """Initialize potential spawn points for box respawning."""
        self.available_spawn_points = []
        service_points = set(self.drop_points + self.recharge_points + self.spawn_points + self.resting_points)
        
        # Find free cells that are not service points and not too close to them
        for x in range(self.W):
            for y in range(self.H):
                pos = (x, y)
                if self.cell_is_free(pos) and pos not in service_points:
                    # Check if not too close to service points (at least 2 cells away)
                    too_close = False
                    for service_pos in service_points:
                        if manhattan(pos, service_pos) < 2:
                            too_close = True
                            break
                    if not too_close:
                        self.available_spawn_points.append(pos)

    def handle_box_pickup(self, robot, box_location):
        """Handle visual pickup - mark box as picked and schedule respawn."""
        if isinstance(box_location, (list, tuple)) and len(box_location) >= 2:
            box_key = (box_location[0], box_location[1])
            self.picked_boxes.add(box_key)
    
    def handle_box_delivery(self, robot, box_location):
        """Handle delivery - optionally respawn the box at a new location."""
        # Skip delivery if training episode is already terminated
        if getattr(self, 'episode_terminated', False):
            return
            
        if isinstance(box_location, (list, tuple)) and len(box_location) >= 2:
            box_key = (box_location[0], box_location[1])
            if box_key in self.picked_boxes:
                self.picked_boxes.remove(box_key)
                # Only respawn if respawning is enabled (simulation mode)
                if getattr(self, 'box_respawn_enabled', True):
                    self._respawn_box(box_location)
                else:
                    # In training mode, mark box as permanently delivered
                    if not hasattr(self, 'delivered_boxes'):
                        self.delivered_boxes = set()
                    self.delivered_boxes.add(box_key)
    
    def _respawn_box(self, original_box_location):
        """Respawn a box at a new random location with the same level."""
        if not self.available_spawn_points:
            return  # No spawn points available
            
        # Find the original box to get its level
        original_level = 1  # Default level
        box_id = None
        for i, box in enumerate(self.boxes):
            if isinstance(box, dict) and 'pos' in box:
                pos = box['pos']
                if (isinstance(pos, (list, tuple)) and len(pos) >= 2 and 
                    pos[0] == original_box_location[0] and pos[1] == original_box_location[1]):
                    original_level = pos[2] if len(pos) >= 3 else 1
                    box_id = i
                    break
        
        if box_id is not None:
            # Choose a random spawn point
            new_pos = random.choice(self.available_spawn_points)
            # Update box position
            self.boxes[box_id]['pos'] = [new_pos[0], new_pos[1], original_level]

    def is_rack_cell(self, pos):
        """Check if a position is a rack (blocked) cell"""
        return not self.inbound(pos) or self.is_blocked(pos)
    
    def is_narrow_aisle(self, pos):
        """Check if position is in a narrow aisle between racks (should use guidance lines)"""
        if not isinstance(pos, (tuple, list)) or len(pos) < 2:
            return False
            
        x, y = int(pos[0]), int(pos[1])
        
        # Check if we're between two racks horizontally (narrow vertical aisle)
        left_blocked = self.is_rack_cell((x-1, y))
        right_blocked = self.is_rack_cell((x+1, y))
        
        # If both sides are blocked, we're in a narrow aisle
        if left_blocked and right_blocked:
            return True
            
        return False
    
    def is_guidance_line_entry(self, pos, target_box=None):
        """Check if position is a proper guidance line entry point"""
        if target_box is not None:
            return is_on_guidance_line_for_box(self, pos, target_box)
        return False
    
    def cell_is_free(self, p : tuple):
        return (self.inbound(p) and not self.is_blocked(p))
    
    def cell_has_robot_or_obstacle(self, p : tuple):
        """Check if cell has robot or obstacle (opposite of cell_is_free)"""
        return not self.cell_is_free(p)

    def recharge_point_free(self, p:tuple):
        return (p in self.recharge_points) and (p not in self.intended.keys())

    def resting_point_free(self, p:tuple):
        return (p in self.resting_points) and (p not in self.intended.keys())

    def get_available_drop_point(self, robot_id):
        """Get an available drop point for a robot, ensuring no conflicts"""
        if not self.drop_points:
            return None
            
        # Check if robot already has a reserved drop point
        if robot_id in self.drop_point_assignments:
            reserved_point = self.drop_point_assignments[robot_id]
            if reserved_point in self.reserved_drop_points:
                return reserved_point
        
        # Find an unreserved drop point
        for drop_point in self.drop_points:
            if drop_point not in self.reserved_drop_points:
                # Reserve this drop point for the robot
                self.reserved_drop_points.add(drop_point)
                self.drop_point_assignments[robot_id] = drop_point
                return drop_point
        
        # If all are reserved, use round-robin as fallback
        fallback_point = self.drop_points[robot_id % len(self.drop_points)]
        return fallback_point
    
    def release_drop_point(self, robot_id):
        """Release a robot's drop point reservation"""
        if robot_id in self.drop_point_assignments:
            drop_point = self.drop_point_assignments[robot_id]
            self.reserved_drop_points.discard(drop_point)
            del self.drop_point_assignments[robot_id]

    def add_mission_to_queue(self, box_location:tuple, target:tuple, mission:str):
        self.pending_missions.append((box_location, target, mission))

    def closest_pick(self, robot_pos:tuple, cell_list, free_fun):
        best = None
        best_d = None
        for p in cell_list:
            d = manhattan(robot_pos, p)
            if (best_d is None or d < best_d) and free_fun(p):
                best = p
                best_d = d
        return best

    def assign_all_pending_nearest(self):
        """Assign each pending mission to the nearest eligible robot (greedy).
        Elegible: mission None/RESTING, battery >=15 (else reroute to recharge), correct type if level requires.
        No random choice: determinista por orden de lista de misiones.
        """
        if not self.pending_missions:
            return
        remaining = []
        # Precompute a list of free robots we can still allocate this pass
        # We'll update as we assign so each robot gets at most one new mission.
        for bx_loc, tgt, miss in list(self.pending_missions):
            # Skip inaccessible box for now
            try:
                if bx_loc is not None and not self.box_is_accessible(bx_loc):
                    remaining.append((bx_loc, tgt, miss))
                    continue
            except Exception:
                pass
            # Determine capability requirement - check if robot can access box level
            box_level = None
            try:
                if bx_loc is not None and len(bx_loc) > 2:
                    box_level = int(bx_loc[2])
            except Exception:
                box_level = 1  # Default level
                
            candidates = []
            for rb in self.robots:
                if rb.mission not in (None, "RESTING"):
                    continue
                # Skip robots that can't access this box level
                if box_level is not None:
                    robot_access_levels = getattr(rb, 'access_levels', [1, 2])
                    if box_level not in robot_access_levels:
                        continue
                # Battery routing
                if rb.battery < 15:
                    chg = self.closest_pick(rb.position, self.recharge_points, self.recharge_point_free)
                    if chg is not None:
                        rb.mission = "RECHARGE"
                        rb.target = (chg[0], chg[1], 0)
                    else:
                        rb.mission = "RESTING"
                    continue
                candidates.append(rb)
            if not candidates:
                remaining.append((bx_loc, tgt, miss))
                continue
            # Choose nearest by Manhattan distance to the box location (x,y)
            try:
                bx_xy = (bx_loc[0], bx_loc[1]) if isinstance(bx_loc, (list, tuple)) else None
            except Exception:
                bx_xy = None
            if bx_xy is None:
                remaining.append((bx_loc, tgt, miss))
                continue
            best = min(candidates, key=lambda r: manhattan(r.position, bx_xy))
            best.mission = miss
            
            # Assign unique drop point for this robot
            if miss == "DELIVERY":
                unique_drop_point = self.get_available_drop_point(best.id)
                if unique_drop_point is not None:
                    best.target = (unique_drop_point[0], unique_drop_point[1], 0)
                else:
                    best.target = tgt  # Fallback to original target
            else:
                best.target = tgt
                
            best.box_location = bx_loc
            self.current_missions[best.id] = {"box_location": bx_loc, "target": best.target, "mission": miss}
        self.pending_missions = remaining

    # Backward compatibility wrapper (old signature still called elsewhere)
    def assign_mission(self, box_location:tuple, target:tuple, mission:str):
        # If a single mission is passed, append then batch assign; else just batch assign existing queue
        if box_location is not None and target is not None and mission is not None:
            self.pending_missions.append((box_location, target, mission))
        self.assign_all_pending_nearest()

    # ================= Episodic training helpers =================
    def setup_episode_based_training(self):
        """Reset robots to random positions with fresh state for episodic training."""
        # Reset box delivery tracking for training episodes
        if hasattr(self, 'delivered_boxes'):
            self.delivered_boxes.clear()
        if hasattr(self, 'picked_boxes'):
            self.picked_boxes.clear()
        
        # Initialize episode termination flag for training
        self.episode_terminated = False
        
        # Track episode deliveries for training mode
        if not hasattr(self, 'episode_delivery_count'):
            self.episode_delivery_count = 0
        else:
            self.episode_delivery_count = 0
            
        try:
            free_cells = [(x, y) for x in range(self.W) for y in range(self.H) if self.cell_is_free((x, y))]
        except Exception:
            free_cells = []
        if len(free_cells) < len(getattr(self, 'robots', [])):
            # fallback allow duplicates
            available_positions = free_cells + [(x, y) for x in range(self.W) for y in range(self.H) if (x, y) not in self.occupied]
        else:
            available_positions = list(free_cells)
        for robot in self.robots:
            if available_positions:
                spawn_pos = random.choice(available_positions)
                robot.position = spawn_pos
                try:
                    available_positions.remove(spawn_pos)
                except ValueError:
                    pass
            robot.battery = 100
            robot.carrying = False
            robot.mission = "RESTING"
            robot.target = None
            robot.proposal = None
            robot.box_location = None
            robot.deliveries_this_episode = 0

    def check_episode_success(self):
        """Success when all robots have delivered at least once this episode."""
        for rb in self.robots:
            if not hasattr(rb, 'deliveries_this_episode') or rb.deliveries_this_episode == 0:
                return False
        return True

    def check_training_episode_complete(self):
        """Check if training episode should end (max 1 delivery per robot)."""
        if not getattr(self, 'training_mode', False):
            return self.check_episode_success()  # Use regular success criteria for visualization
        
        # In training mode: terminate when ALL robots have delivered at least once
        # This ensures successful episodes while limiting deliveries
        all_delivered = True
        for rb in self.robots:
            deliveries = getattr(rb, 'deliveries_this_episode', 0)
            if deliveries == 0:
                all_delivered = False
                break
        
        return all_delivered

    def _update_epsilon_episodic(self, episode:int, total_episodes:int):
        """Quadratic episode-based epsilon decay."""
        if getattr(self, 'epsilon_override', None) is not None:
            self.global_epsilon = float(self.epsilon_override)
        else:
            progress = episode / max(1, total_episodes)
            self.global_epsilon = float(EPSILON_END + (EPSILON_START - EPSILON_END) * (1 - progress) ** 2)
        self.stats['epsilon'] = self.global_epsilon

    # --- utilidades nuevas ---
    def get_col_weight(self, pos_xy:tuple):
        if not isinstance(pos_xy, (list, tuple)) or len(pos_xy) < 2:
            return 1.0
        return float(self.col_weight.get((pos_xy[0], pos_xy[1]), 1.0))

    def box_is_accessible(self, box_location:tuple):
        try:
            if not isinstance(box_location, (list, tuple)) or len(box_location) < 2:
                return False
            bx, by = box_location[0], box_location[1]
            
            # Check if box is already picked up (visually disappeared)
            box_key = (int(bx), int(by))
            if hasattr(self, 'picked_boxes') and box_key in self.picked_boxes:
                return False  # Box is already picked up, not accessible
            
            # In training mode without respawning, check if box was delivered
            if getattr(self, 'training_mode', False) and not getattr(self, 'box_respawn_enabled', True):
                # Track delivered boxes that shouldn't respawn
                delivered_boxes = getattr(self, 'delivered_boxes', set())
                if box_key in delivered_boxes:
                    return False  # Box was delivered and not respawned
            
            return len(approach_cells_to_box(self, (bx, by), None)) > 0
        except Exception:
            return False

    def seed_random_missions(self, n:int=3):
        # Filter boxes based on available robot capabilities with new level system
        locs = []
        # Get all access levels available from current robots
        available_levels = set()
        for rb in self.robots:
            robot_levels = getattr(rb, 'access_levels', [1, 2])
            available_levels.update(robot_levels)
        
        for b in self.boxes:
            pos = b.get('pos') if isinstance(b, dict) else None
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                if len(pos) >= 3:
                    level = int(pos[2]) if pos[2] is not None else 1
                    # Include box only if we have robots that can access this level
                    if level in available_levels:
                        locs.append(tuple(pos[:3]))
                else:
                    locs.append((pos[0], pos[1], 1))  # Default to level 1
        if not locs:
            if not getattr(self, '_warned_no_locs', False):
                print("[WARN] No box locations available for missions.")
                self._warned_no_locs = True
            return
        if not self.drop_points:
            if not getattr(self, '_warned_no_drops', False):
                print("[WARN] No drop points configured - cannot create delivery missions.")
                self._warned_no_drops = True
            return
        k = min(n, len(locs))
        random.shuffle(locs)
        for i in range(k):
            loc = locs[i]
            # Use available drop point system instead of round-robin
            # For now, we'll assign drop points during robot assignment, not during mission creation
            # This allows for proper reservation management
            dummy_dp = self.drop_points[0] if self.drop_points else (0, 0)
            tgt3 = (dummy_dp[0], dummy_dp[1], 0)
            self.add_mission_to_queue(loc, tgt3, "DELIVERY")
        # Asignar inmediatamente usando política "nearest"
        self.assign_all_pending_nearest()

    def _validate_config(self, cfg:dict):
        # Cajas
        for i, b in enumerate(cfg.get('boxes', [])):
            if not isinstance(b, dict):
                print(f"[WARN] Box idx {i} invalid format")
                continue
            pos = b.get('pos')
            has_slot = ('rack_id' in b) and isinstance(b.get('slot'), dict)
            if pos is None:
                # If slot-based addressing is present, it's valid; we'll map to pos at setup
                if not has_slot:
                    print(f"[WARN] Box idx {i} missing pos (x,y,h)")
            else:
                if not isinstance(pos, (list, tuple)) or len(pos) < 3:
                    print(f"[WARN] Box idx {i} pos invalid (expected [x,y,h])")
        # Tags
        valid = {"DROP", "CHARGE", "SPAWN", "REST"}
        for t in cfg.get('tags', []):
            ty = t.get('type')
            if ty not in valid:
                print(f"[WARN] Unknown tag type: {ty}")
            pos = t.get('pos')
            if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                print(f"[WARN] Tag {ty} invalid pos: {pos}")
        # Pesos de columna
        colw = cfg.get('col_weights')
        if colw is not None and not isinstance(colw, (list, dict)):
            print("[WARN] col_weights must be list or dict")

    def _dest_after(self, rb, act=None):
        """Where this robot will be next step given its current (or provided) proposal."""
        a = rb.proposal if act is None else act
        return next_pos_from_action(self, rb.position, a)

    def get_robot_priority(self, robot):
        """Calculate robot priority for conflict resolution. Higher = more important."""
        priority = 0
        
        # Mission-based priority
        if getattr(robot, 'carrying', False):
            priority += 100  # Delivery has highest priority
        elif getattr(robot, 'mission', None) == 'DELIVERY':
            priority += 50   # Going to pickup is important
        elif getattr(robot, 'mission', None) == 'RECHARGE':
            priority += 30   # Recharging is medium priority
        
        # Battery urgency
        battery = float(getattr(robot, 'battery', 100))
        if battery < 15:
            priority += 75   # Critical battery - emergency priority
        elif battery < 30:
            priority += 25   # Low battery gets some priority
        
        # Slight randomization to break ties fairly
        priority += (robot.id * 0.1)  # Small tie-breaker based on ID
        
        return priority

    def get_alternative_moves(self, robot):
        """Get all valid alternative moves for a robot, sorted by preference."""
        x, y = robot.position
        alternatives = []
        
        # Get all possible directions
        for action, (dx, dy) in DIRS.items():
            new_pos = (x + dx, y + dy)
            if self.cell_is_free(new_pos):
                alternatives.append((action, new_pos))
        
        # Sort alternatives by distance to robot's goal
        if hasattr(robot, 'target') and robot.target:
            goal = robot.target[:2] if len(robot.target) >= 2 else robot.target
            alternatives.sort(key=lambda alt: manhattan(alt[1], goal))
        elif hasattr(robot, 'box_location') and robot.box_location and not getattr(robot, 'carrying', False):
            goal = robot.box_location[:2] if len(robot.box_location) >= 2 else robot.box_location
            alternatives.sort(key=lambda alt: manhattan(alt[1], goal))
        
        return alternatives

    # ================= ADAPTIVE BEHAVIOR SYSTEM =================
    def analyze_failure_pattern(self, robot):
        """Analyze robot's failure history to determine behavioral adaptations needed"""
        if robot.behavior_change_cooldown > 0:
            robot.behavior_change_cooldown -= 1
            return
        
        failures = robot.failure_history
        total_failures = sum(failures.values())
        
        if total_failures < 5:  # Not enough data yet
            return
        
        # Determine dominant failure type
        dominant_failure = max(failures.items(), key=lambda x: x[1])
        failure_type, failure_count = dominant_failure
        
        # Apply behavioral adaptations based on failure pattern
        if failure_type == 'movement_blocks' and failure_count > failures['pathfinding_failures']:
            self.adapt_to_movement_issues(robot)
        elif failure_type == 'pickup_failures':
            self.adapt_to_pickup_issues(robot)
        elif failure_type == 'delivery_failures':
            self.adapt_to_delivery_issues(robot)
        elif failure_type == 'pathfinding_failures':
            self.adapt_to_pathfinding_issues(robot)
        elif failure_type == 'collision_count':
            self.adapt_to_collision_issues(robot)
    
    def adapt_to_movement_issues(self, robot):
        """Adapt behavior for robots having movement problems"""
        robot.behavior_mode = "PATIENT_MOVER"
        robot.behavior_adaptations['patience_level'] = 2.0  # Wait longer
        robot.behavior_adaptations['risk_tolerance'] = 0.5  # Take safer moves
        robot.behavior_adaptations['exploration_bias'] = 0.7  # Prefer known paths
        robot.behavior_change_cooldown = 20
        print(f"🔄 Robot {robot.id}: Adapted to PATIENT_MOVER mode (movement issues)")
    
    def adapt_to_pickup_issues(self, robot):
        """Adapt behavior for robots having pickup problems"""
        robot.behavior_mode = "FLEXIBLE_PICKER"
        robot.behavior_adaptations['task_flexibility'] = 2.0  # More willing to switch tasks
        robot.behavior_adaptations['cooperation_level'] = 1.5  # More cooperative
        robot.behavior_adaptations['risk_tolerance'] = 1.3  # Try riskier pickup attempts
        robot.behavior_change_cooldown = 15
        print(f"🔄 Robot {robot.id}: Adapted to FLEXIBLE_PICKER mode (pickup issues)")
    
    def adapt_to_delivery_issues(self, robot):
        """Adapt behavior for robots having delivery problems"""
        robot.behavior_mode = "PERSISTENT_DELIVERER"
        robot.behavior_adaptations['patience_level'] = 1.8  # More patient
        robot.behavior_adaptations['task_flexibility'] = 0.3  # Stick to delivery
        robot.behavior_adaptations['exploration_bias'] = 1.5  # Try new delivery routes
        robot.behavior_change_cooldown = 25
        print(f"🔄 Robot {robot.id}: Adapted to PERSISTENT_DELIVERER mode (delivery issues)")
    
    def adapt_to_pathfinding_issues(self, robot):
        """Adapt behavior for robots having pathfinding problems"""
        robot.behavior_mode = "EXPLORER"
        robot.behavior_adaptations['exploration_bias'] = 2.0  # Strongly prefer exploration
        robot.behavior_adaptations['risk_tolerance'] = 1.8  # Take risks to find paths
        robot.behavior_adaptations['patience_level'] = 0.8  # Less patient, keep moving
        robot.behavior_change_cooldown = 10
        print(f"🔄 Robot {robot.id}: Adapted to EXPLORER mode (pathfinding issues)")
    
    def adapt_to_collision_issues(self, robot):
        """Adapt behavior for robots having collision problems"""
        robot.behavior_mode = "COOPERATIVE"
        robot.behavior_adaptations['cooperation_level'] = 2.5  # Highly cooperative
        robot.behavior_adaptations['patience_level'] = 2.2  # Very patient
        robot.behavior_adaptations['risk_tolerance'] = 0.3  # Avoid risky moves
        robot.behavior_change_cooldown = 30
        print(f"🔄 Robot {robot.id}: Adapted to COOPERATIVE mode (collision issues)")
    
    def record_successful_strategy(self, robot, strategy_context):
        """Record when robot succeeds with current adaptations"""
        strategy = {
            'behavior_mode': robot.behavior_mode,
            'adaptations': robot.behavior_adaptations.copy(),
            'context': strategy_context,
            'timestamp': getattr(self, 'steps', 0)
        }
        robot.successful_strategies.append(strategy)
        
        # Keep only recent successful strategies
        if len(robot.successful_strategies) > 10:
            robot.successful_strategies.pop(0)
    
    def apply_behavioral_modifications(self, robot, action):
        """Apply behavioral adaptations to action selection"""
        adaptations = robot.behavior_adaptations
        
        # Patience modification: wait longer before switching actions
        if adaptations['patience_level'] > 1.0:
            if robot.action_success_counter < int(15 * adaptations['patience_level']):
                return action  # Don't modify yet, be more patient
        
        # Risk tolerance modification: avoid/prefer risky actions
        if action in ["UP", "DOWN", "LEFT", "RIGHT"]:
            next_pos = next_pos_from_action(self, robot.position, action)
            if self.cell_has_robot_or_obstacle(next_pos):
                if adaptations['risk_tolerance'] < 0.8:
                    return None  # Avoid risky move
                elif adaptations['risk_tolerance'] > 1.5:
                    pass  # Allow risky move
        
        # Task flexibility modification: willingness to switch missions
        if robot.action_success_counter >= 8:
            if adaptations['task_flexibility'] > 1.5:
                # More willing to switch tasks when stuck
                if robot.mission == "DELIVERY" and not robot.carrying:
                    available_boxes = self.get_available_box_locations()
                    if available_boxes:
                        robot.mission = "PICKUP_PRIORITY"
                        print(f"🔄 Robot {robot.id}: Flexible task switch to pickup")
                        return None  # Recalculate action with new mission
        
        return action
    
    def find_nearest_available_drop(self, position):
        """Find nearest available drop point for adaptive behavior"""
        drop_points = getattr(self, 'drop_points', [])
        if not drop_points:
            return None
        return self.closest_pick(position, drop_points, lambda p: True)
    
    def find_easiest_pickup(self, position):
        """Find easiest pickup target for adaptive behavior"""
        box_locations = self.get_available_box_locations()
        if not box_locations:
            return None
        # Find closest box
        return min(box_locations, key=lambda box: manhattan(position, box))
    
    def find_nearest_available_pickup(self, position):
        """Find nearest available pickup for adaptive behavior"""
        return self.find_easiest_pickup(position)
    
    def find_alternative_target(self, position, mission):
        """Find alternative target for exploratory behavior"""
        if mission == "DELIVERY":
            return self.find_nearest_available_drop(position)
        else:
            return self.find_easiest_pickup(position)
    
    def get_available_box_locations(self):
        """Get list of available box locations"""
        box_locations = []
        try:
            # Check spawned boxes
            spawned_boxes = getattr(self, 'spawned_boxes', {})
            for box_id, box_info in spawned_boxes.items():
                if not box_info.get('picked_up', False):
                    pos = box_info.get('position', box_info.get('pos'))
                    if pos:
                        box_locations.append(tuple(pos))
            
            # Fallback: check static box positions if available
            if not box_locations and hasattr(self, 'box_positions'):
                box_locations = list(self.box_positions)
                
        except Exception:
            pass
        return box_locations

    # ================= FIXED STEP PIPELINE (CLEAN REPLACEMENT) =================
    def step(self):
        """Advance one simulation tick (planning -> conflict resolution -> action -> bookkeeping)."""
        self._update_epsilon()
        self._reset_step_counters()
        self._phase_plan()
        self.resolve_conflicts()
        self._phase_act()
        self._post_step_updates()

    def resolve_conflicts(self, max_passes=3):
        """Enhanced multi-pass resolver with priority-based resolution and alternative routing."""
        self.forced_wait_by_conflict = set()
        
        for pass_num in range(max_passes):
            # Build intended destinations map
            intended = {}
            for rb in self.robots:
                dest = self._dest_after(rb)
                intended.setdefault(dest, []).append(rb)
            
            conflicts_found = False
            
            # Resolve many-to-one conflicts with priority and alternatives
            # Create a copy of items to avoid RuntimeError from modification during iteration
            conflicts_to_resolve = [(dest, robots[:]) for dest, robots in intended.items() if len(robots) > 1]
            
            for dest, robots in conflicts_to_resolve:
                conflicts_found = True
                
                # Sort robots by priority (highest first)
                robots_by_priority = sorted(robots, key=self.get_robot_priority, reverse=True)
                winner = robots_by_priority[0]  # Highest priority wins
                
                # Try to find alternatives for lower priority robots
                for loser in robots_by_priority[1:]:
                    found_alternative = False
                    
                    # Try alternative moves (only on first pass to avoid confusion)
                    if pass_num == 0:
                        alternatives = self.get_alternative_moves(loser)
                        for alt_action, alt_dest in alternatives:
                            # Check if this alternative destination is free from other robots
                            # Don't modify intended dict during resolution - just check original conflicts
                            other_robots_at_dest = [r for r in self.robots if r != loser and self._dest_after(r) == alt_dest]
                            if len(other_robots_at_dest) == 0:
                                # Alternative is free, use it
                                loser.proposal = alt_action
                                found_alternative = True
                                break
                    
                    # If no alternative found, force to wait
                    if not found_alternative:
                        loser.proposal = "WAIT"
                        self.forced_wait_by_conflict.add(loser.id)
            
            # Resolve head-on swaps with priority system
            swap_conflicts = []
            for rb1 in self.robots:
                for rb2 in self.robots:
                    if rb1.id >= rb2.id:
                        continue
                    dest1 = self._dest_after(rb1)
                    dest2 = self._dest_after(rb2)
                    if rb1.position == dest2 and rb2.position == dest1:
                        swap_conflicts.append((rb1, rb2))
            
            for rb1, rb2 in swap_conflicts:
                conflicts_found = True
                priority1 = self.get_robot_priority(rb1)
                priority2 = self.get_robot_priority(rb2)
                
                # Lower priority robot waits
                if priority1 < priority2:
                    loser = rb1
                else:
                    loser = rb2
                
                # Try alternative for the loser (first pass only)
                found_alternative = False
                if pass_num == 0:
                    alternatives = self.get_alternative_moves(loser)
                    for alt_action, alt_dest in alternatives[:2]:  # Try top 2 alternatives
                        # Check if alternative is truly free (no other robots going there)
                        if alt_dest not in [self._dest_after(r) for r in self.robots if r != loser]:
                            loser.proposal = alt_action
                            found_alternative = True
                            break
                
                # Force to wait if no alternative
                if not found_alternative:
                    loser.proposal = "WAIT"
                    self.forced_wait_by_conflict.add(loser.id)
            
            if not conflicts_found:
                break
        
        # Update stats
        self.stats["conflicts"] += len(self.forced_wait_by_conflict)
        self._forced_waits_this_step = len(self.forced_wait_by_conflict)

    def _update_epsilon(self):
        self.stats["step"] += 1
        if getattr(self, 'epsilon_override', None) is not None:
            self.global_epsilon = float(self.epsilon_override)
        else:
            try:
                tau = float(EPSILON_TAU)
            except Exception:
                tau = max(1.0, DECAY_STEPS / 4.0)
            self.global_epsilon = float(
                EPSILON_END + (EPSILON_START - EPSILON_END) * np.exp(-self.stats["step"] / tau)
            )
        self.stats["epsilon"] = self.global_epsilon

    def _reset_step_counters(self):
        self.intended = {}
        self.forced_wait_by_conflict = set()
        self.action_events = []
        self._delivered_this_step = 0
        self._picked_this_step = 0
        self._bumps_this_step = 0
        self._forced_waits_this_step = 0

    def _phase_plan(self):
        # Try to assign pending missions to available robots first
        try:
            self.assign_all_pending_nearest()
        except Exception:
            pass
        
        for robot in self.robots:
            if robot.mission is None:
                robot.mission = "RESTING"
                rp = self.closest_pick(robot.position, self.resting_points, self.resting_point_free)
                robot.target = (rp[0], rp[1], 0) if rp is not None else None
            if getattr(robot, 'battery', 100) < 10 and not getattr(robot, 'carrying', False):
                chg = self.closest_pick(robot.position, self.recharge_points, self.recharge_point_free)
                if chg is None and self.recharge_points:
                    chg = min(self.recharge_points, key=lambda p: manhattan(robot.position, p))
                if chg is not None:
                    robot.mission = "RECHARGE"
                    robot.target = (chg[0], chg[1], 0)
            if robot.mission == "RESTING":
                tgt = robot.target
                if tgt is not None:
                    tgt_xy = tuple(tgt[:2]) if isinstance(tgt, (list, tuple)) and len(tgt) >= 2 else tuple(tgt)
                    if tgt_xy in self.recharge_points:
                        rp = self.closest_pick(robot.position, self.resting_points, self.resting_point_free)
                        robot.target = (rp[0], rp[1], 0) if rp is not None else None
            box_loc = self.current_missions.get(robot.id, {}).get("box_location", None)
            robot.plan(box_loc)
            dest = next_pos_from_action(self, robot.position, robot.proposal)
            self.intended.setdefault(dest, []).append(robot)

    def _phase_act(self):
        for robot in self.robots:
            if robot.mission is None:
                continue
            robot.act()

    def _post_step_updates(self):
        try:
            self.assign_mission(None, None, None)
        except Exception:
            pass
        # More aggressive mission seeding - always keep missions available
        try:
            available_robots = sum(1 for r in self.robots if r.mission in (None, "RESTING"))
            pending_count = len(self.pending_missions)
            if pending_count < available_robots and int(self.stats.get("deliveries", 0)) < 999:
                missions_needed = max(2, available_robots - pending_count)
                self.seed_random_missions(n=missions_needed)
        except Exception:
            pass
        if self.stats["reward_hist"]:
            recent = self.stats["reward_hist"][-100:] if len(self.stats["reward_hist"]) >= 100 else self.stats["reward_hist"]
            self.stats["avg_reward"] = sum(recent) / len(recent)
        try:
            self.stats["delivery_hist"].append(1 if self._delivered_this_step > 0 else 0)
            self.stats["pickup_hist"].append(1 if self._picked_this_step > 0 else 0)
            self.stats["bump_hist"].append(int(self._bumps_this_step))
            self.stats["forced_wait_hist"].append(int(self._forced_waits_this_step))
        except Exception:
            pass
        try:
            if bool(getattr(self, 'auto_cycle_reset', False)) and int(self.stats.get("deliveries", 0)) >= int(self.CYCLE_DELIVERIES_TARGET):
                print(f"Cycle complete: {self.stats.get('deliveries',0)} deliveries. Resetting...")
                self.reset_cycle()
        except Exception:
            pass

    def run(self, steps=1000):
        """Run the simulation for a specified number of steps."""
        for _ in range(steps):
            self.step()
        return self
    # ================= END FIXED STEP PIPELINE =================

    def get_state_dict(self):
        """Return current state for visualization"""
        robot_states = []
        for robot in self.robots:
            robot_states.append({
                'id': robot.id,
                'position': robot.position,
                'carrying': robot.carrying,
                'battery': robot.battery,
                'mission': robot.mission,
                'target': robot.target,
                'r_type': robot.r_type
            })
        
        return {
            'step': self.stats["step"],
            'robots': robot_states,
            'stats': self.stats.copy(),
            'epsilon': self.global_epsilon,
            'occupied': list(self.occupied),
            'drop_points': self.drop_points,
            'recharge_points': self.recharge_points,
            'spawn_points': self.spawn_points,
            'W': self.W,
            'H': self.H
        }

    def print_progress(self, episode=None):
        """Print training progress"""
        if episode is not None:
            print(f"Episode {episode}")
        print(f"Step: {self.stats['step']}")
        print(f"Epsilon: {self.global_epsilon:.3f}")
        print(f"Avg Reward: {self.stats['avg_reward']:.3f}")
        print(f"Deliveries: {self.stats['deliveries']}")
        print(f"Pickups: {self.stats['pickups']}")
        print(f"Conflicts: {self.stats['conflicts']}")
        print("-" * 40)

    def save_weights(self, filename="W_linear.npy"):
        """Save current weights silently"""
        try:
            np.save(filename, self.global_weights)
        except Exception as e:
            print(f"Error saving weights: {e}")

    def load_weights(self, filename="W_linear.npy"):
        """Load weights from file silently. Returns True if loaded, False otherwise."""
        try:
            if not os.path.exists(filename):
                return False
            arr = np.load(filename).astype(np.float32)
            if arr.shape[0] != N_FEATURES:
                print(f"Error: weight dimension mismatch in {filename}")
                return False
            self.global_weights = arr
            return True
        except Exception:
            return False

    def end(self):
        # Guardar pesos si no usamos preentrenados
        try:
            if not PRETRAIN_ENABLED and hasattr(self, 'global_weights'):
                self.save_weights("W_linear.npy")
        except Exception:
            pass

    def serialize_for_unity(self):
        """Build the exact envelope the Unity client expects."""
        # robots array
        robots_json = []
        try:
            for rb in getattr(self, "robots", []):
                x, y = rb.position
                robots_json.append({
                    "id": int(getattr(rb, "id", -1)),
                    "x": int(x),
                    "y": int(y),
                    "heading": int(getattr(rb, "last_heading", 0)),
                    "action": str(getattr(rb, "last_action_str", "idle"))
                })
        except Exception:
            robots_json = []

        # boxes array (static from config); 'available' via accessibility check
        boxes_json = []
        try:
            for b in getattr(self, "boxes", []):
                pos = b.get("pos") if isinstance(b, dict) else None
                if isinstance(pos, (list, tuple)) and len(pos) >= 3:
                    bx, by, lvl = int(pos[0]), int(pos[1]), int(pos[2])
                    avail = False
                    try:
                        avail = bool(self.box_is_accessible((bx, by, lvl)))
                    except Exception:
                        avail = False
                    boxes_json.append({
                        "x": bx,
                        "y": by,
                        "level": lvl,
                        "available": avail
                    })
        except Exception:
            boxes_json = []

        # actions array (already lowercase strings)
        try:
            actions_json = list(self.action_events) if isinstance(self.action_events, list) else []
        except Exception:
            actions_json = []

        # episode/tick flags
        ticks = int(self.stats.get("step", 0)) if isinstance(self.stats, dict) else 0
        # Mark done when a delivery cycle target is reached (but before auto reset)
        ep_done = False
        try:
            ep_done = bool(self.stats.get("deliveries", 0) >= int(self.CYCLE_DELIVERIES_TARGET))
        except Exception:
            ep_done = False

        state = {
            "ticks": ticks,
            "episode_done": ep_done,
            "robots": robots_json,
            "boxes": boxes_json,
            "actions": actions_json,
        }

        # Full envelope
        envelope = {
            "initialized": True,
            "running": True,
            "state": state
        }
        return envelope

"""Deprecated step-based train_model removed in favor of episodic training.
For backward compatibility, provide a thin wrapper that calls train_model_episodic
with equivalent arguments. Users should migrate to train_model_episodic directly."""
def train_model(episodes=1000, steps_per_episode=300, config_path='layout.json',
                save_every=100, weights_dir="weights", summary_window=50, n_robots=None):
    return train_model_episodic(episodes=episodes, steps_per_episode=steps_per_episode,
                                config_path=config_path, save_every=save_every,
                                weights_dir=weights_dir, summary_window=summary_window,
                                n_robots=n_robots)

def run_simulation(steps=1000, config_path='layout.json', visualize=False):
    """Run a single simulation with optional visualization."""
    params = {'config_path': config_path}
    model = Warehouse(parameters=params)
    model.setup()

    if visualize and VISUALIZATION_ENABLED:
        try:
            try:
                from visualize import WarehouseVisualizer
            except Exception:
                WarehouseVisualizer = None
            if WarehouseVisualizer is not None:
                viz = WarehouseVisualizer(model, cell_size=30, fps=3)
                viz.run(steps)
            else:
                print("WarehouseVisualizer not available. Running headless.")
                for _ in range(steps):
                    model.step()
        except Exception as e:
            print(f"Visualization error: {e}. Running headless.")
            for _ in range(steps):
                model.step()
    else:
        for _ in range(steps):
            model.step()
    return model

# ================= Episodic / Progressive Training ============================
def train_model_episodic(episodes=1000, steps_per_episode=300, config_path='layout.json',
                         save_every=100, weights_dir="weights", summary_window=50, n_robots=None):
    """Episode-based training with random spawning, success tracking, and episodic epsilon decay."""
    print(f"Episode-based Training: {episodes} episodes × {steps_per_episode} steps")
    print("Success criteria: all robots deliver at least once per episode")
    if n_robots:
        print(f"Training with {n_robots} robots")
    print(f"Config: {config_path} | Weights: {weights_dir}")
    print("-" * 80)

    os.makedirs(weights_dir, exist_ok=True)
    default_weights = os.path.join(weights_dir, "W_linear.npy")
    best_weights = os.path.join(weights_dir, "W_linear_best.npy")

    best_success_rate = 0.0
    total_steps = 0
    episode_success_history = []
    episode_rewards = []
    deliveries_per_episode = []

    recent_success_rate = 0.0

    for episode in range(episodes):
        params = {'config_path': config_path}
        model = Warehouse(parameters=params)
        model.setup()
        model.auto_cycle_reset = False
        if n_robots and n_robots < len(model.robots):
            model.robots = model.robots[:n_robots]
        if episode > 0:
            if not model.load_weights(default_weights):
                model.load_weights(best_weights)

        model.setup_episode_based_training()
        # DISABLE box respawning during training for clean metrics
        model.training_mode = True
        model.box_respawn_enabled = False
        
        # Compute episodic epsilon (quadratic decay over episodes)
        model._update_epsilon_episodic(episode, episodes)
        # Freeze epsilon during intra-episode steps so step-based decay in step() doesn't override it
        # (step() calls _update_epsilon each tick; the override keeps epsilon constant for this episode)
        model.epsilon_override = model.global_epsilon

        episode_reward = 0.0
        episode_deliveries = 0
        for step in range(steps_per_episode):
            model.step()
            if getattr(model, '_delivered_this_step', 0) > 0:
                episode_deliveries += getattr(model, '_delivered_this_step', 0)
            if model.stats['reward_hist']:
                episode_reward += model.stats['reward_hist'][-1]
            total_steps += 1
            
            # Early termination: check if episode was terminated during delivery processing
            if (getattr(model, 'episode_terminated', False) or 
                model.check_training_episode_complete()):
                break

        success = model.check_episode_success()
        episode_success_history.append(1 if success else 0)
        episode_rewards.append(episode_reward)
        deliveries_per_episode.append(episode_deliveries)

        if len(episode_success_history) >= summary_window:
            recent_success_rate = sum(episode_success_history[-summary_window:]) / summary_window
        else:
            recent_success_rate = sum(episode_success_history) / len(episode_success_history)

        if (episode + 1) % summary_window == 0:
            avg_reward = np.mean(episode_rewards[-summary_window:]) if len(episode_rewards) >= summary_window else np.mean(episode_rewards)
            avg_del = np.mean(deliveries_per_episode[-summary_window:]) if len(deliveries_per_episode) >= summary_window else np.mean(deliveries_per_episode)
            progress = (episode + 1) / episodes * 100.0
            print(f"Episodes {episode-summary_window+2:4d}-{episode+1:4d} [{progress:5.1f}%] | "
                  f"Success: {recent_success_rate:5.1%} | Avg Reward: {avg_reward:6.2f} | "
                  f"Deliveries: {avg_del:4.1f} | ε: {model.global_epsilon:.3f}")

        if recent_success_rate > best_success_rate:
            best_success_rate = recent_success_rate
            model.save_weights(best_weights)
        model.save_weights(default_weights)
        if (episode + 1) % save_every == 0:
            model.save_weights(os.path.join(weights_dir, f"W_linear_ep_{episode+1}.npy"))

    print("\nEpisodic training completed!")
    print(f"Best success rate: {best_success_rate:.1%}")
    print(f"Final success rate: {recent_success_rate:.1%}")
    # Persist aggregated episodic statistics onto the final model so export_metrics can access them
    try:
        model.stats['episode_success_history'] = list(episode_success_history)
        model.stats['episode_rewards'] = list(episode_rewards)
        model.stats['deliveries_per_episode'] = list(deliveries_per_episode)
        model.stats['episodes'] = int(episodes)
        model.stats['best_success_rate'] = float(best_success_rate)
        model.stats['final_success_rate'] = float(recent_success_rate)
    except Exception:
        pass
    return model, episode_success_history

def train_single_robot(episodes=300, steps_per_episode=200):
    print("=== Phase 1: Single Robot Navigation ===")
    return train_model_episodic(episodes=episodes, steps_per_episode=steps_per_episode,
                                n_robots=1, weights_dir="weights/phase1")

def train_two_robots(episodes=500, steps_per_episode=250):
    print("=== Phase 2: Two Robot Coordination ===")
    model, history = train_model_episodic(episodes=episodes, steps_per_episode=steps_per_episode,
                                          n_robots=2, weights_dir="weights/phase2")
    try:
        if os.path.exists("weights/phase1/W_linear_best.npy"):
            import shutil
            shutil.copy("weights/phase1/W_linear_best.npy", "weights/phase2/W_linear.npy")
    except Exception:
        pass
    return model, history

def train_full_team(episodes=1000, steps_per_episode=300):
    print("=== Phase 3: Full Team Optimization ===")
    model, history = train_model_episodic(episodes=episodes, steps_per_episode=steps_per_episode,
                                          n_robots=None, weights_dir="weights/phase3")
    try:
        if os.path.exists("weights/phase2/W_linear_best.npy"):
            import shutil
            shutil.copy("weights/phase2/W_linear_best.npy", "weights/phase3/W_linear.npy")
    except Exception:
        pass
    return model, history

def progressive_training_strategy():
    print("=== Progressive Training Strategy ===")
    model1, history1 = train_single_robot(episodes=300)
    success1 = sum(history1[-50:]) / min(50, len(history1)) if history1 else 0.0
    print(f"Phase 1 final success rate: {success1:.1%}")
    model2, history2 = train_two_robots(episodes=500)
    success2 = sum(history2[-50:]) / min(50, len(history2)) if history2 else 0.0
    print(f"Phase 2 final success rate: {success2:.1%}")
    model3, history3 = train_full_team(episodes=700)
    success3 = sum(history3[-50:]) / min(50, len(history3)) if history3 else 0.0
    print(f"Phase 3 final success rate: {success3:.1%}")
    print("\nProgressive training completed!")
    print(f"Single: {success1:.1%} -> Two: {success2:.1%} -> Full: {success3:.1%}")
    return model3, history3

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "train":
            episodes = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            train_model(episodes=episodes)
        elif sys.argv[1] == "run":
            steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            visualize = len(sys.argv) > 3 and sys.argv[3] == "--viz"
            run_simulation(steps=steps, visualize=visualize)
        else:
            print("Usage: python warehouse.py [train|run] [episodes/steps] [--viz]")
    else:
        # Default behavior
        try:
            params = {
                'config_path': 'layout.json',
            }
            model = Warehouse(parameters=params)
            model.run(steps=50)
            model.print_progress()
        except FileNotFoundError:
            print("layout.json not found. Place it next to warehouse.py or pass parameters in your runner.")
        except KeyboardInterrupt:
            print("Interrupted by user.")
        except Exception as e:
            print("Simulation error:", e)