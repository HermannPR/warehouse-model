"""
Enhanced solution for robots that get stuck and don't finish their tasks.
This system addresses multiple types of stuck behavior:
1. Oscillation between positions
2. Robots stuck in corners or dead ends
3. Robots with unreachable targets
4. Robots circling around obstacles
5. Mission starvation (robots without missions)
"""

import numpy as np
import random
from collections import deque

class StuckRobotSolution:
    def __init__(self):
        self.name = "Enhanced Stuck Robot Detection & Recovery System"
        
    def enhance_robot_class(self, robot_class):
        """Add enhanced stuck detection and recovery to Robot class"""
        
        # Enhanced tracking attributes
        def enhanced_setup(self, robot_conf={}):
            # Call original setup
            self.original_setup(robot_conf)
            
            # Enhanced stuck detection
            self.position_history = deque(maxlen=10)  # Track last 10 positions
            self.action_history = deque(maxlen=8)     # Track last 8 actions
            self.stuck_timer = 0                      # Steps since making progress
            self.last_progress_step = 0               # Last step where we made progress
            self.target_unreachable_count = 0         # Times target was unreachable
            self.mission_stuck_timer = 0              # Time without completing missions
            self.emergency_mode = False               # Emergency unstuck mode
            self.last_successful_delivery = 0         # Step of last successful delivery
            
            # Pathfinding assistance
            self.tried_positions = set()              # Positions we've tried recently
            self.avoid_positions = set()              # Positions to temporarily avoid
            self.preferred_directions = []            # Directions that led to progress
            
        # Store original setup method
        if not hasattr(robot_class, 'original_setup'):
            robot_class.original_setup = robot_class.setup
        robot_class.setup = enhanced_setup
        
        # Enhanced stuck detection
        def detect_comprehensive_stuck(self, proposed_action):
            """Comprehensive stuck detection beyond simple oscillation"""
            current_pos = self.position
            current_step = getattr(self.model, 'step_count', 0)
            
            # Track position history
            self.position_history.append(current_pos)
            self.action_history.append(proposed_action)
            
            stuck_reasons = []
            
            # 1. Oscillation detection (existing)
            if self.detect_oscillation(proposed_action):
                stuck_reasons.append("oscillation")
            
            # 2. Position cycling detection
            if len(self.position_history) >= 6:
                recent_positions = list(self.position_history)[-6:]
                if len(set(recent_positions)) <= 2:
                    stuck_reasons.append("position_cycling")
            
            # 3. No progress detection
            if len(self.position_history) >= 5:
                if current_pos == self.position_history[-5]:
                    self.stuck_timer += 1
                else:
                    self.stuck_timer = 0
                    self.last_progress_step = current_step
            
            if self.stuck_timer >= 3:
                stuck_reasons.append("no_progress")
            
            # 4. Unreachable target detection
            if self.target and hasattr(self.model, 'is_path_blocked'):
                if self.model.is_path_blocked(current_pos, self.target[:2]):
                    self.target_unreachable_count += 1
                    if self.target_unreachable_count >= 3:
                        stuck_reasons.append("unreachable_target")
            
            # 5. Mission completion stagnation
            current_deliveries = getattr(self, 'deliveries_this_episode', 0)
            if current_step - self.last_successful_delivery > 50 and current_deliveries == 0:
                stuck_reasons.append("mission_stagnation")
            
            # 6. Wall following detection (moving along walls without progress)
            if len(self.action_history) >= 4:
                recent_actions = list(self.action_history)[-4:]
                wall_following_patterns = [
                    ["UP", "RIGHT", "DOWN", "LEFT"],
                    ["LEFT", "UP", "RIGHT", "DOWN"],
                    ["DOWN", "LEFT", "UP", "RIGHT"],
                    ["RIGHT", "DOWN", "LEFT", "UP"]
                ]
                for pattern in wall_following_patterns:
                    if recent_actions == pattern:
                        stuck_reasons.append("wall_following")
                        break
            
            return stuck_reasons
        
        robot_class.detect_comprehensive_stuck = detect_comprehensive_stuck
        
        # Enhanced recovery actions
        def get_unstuck_actions(self, feasible_actions, box_location=None, stuck_reasons=[]):
            """Get actions to recover from various stuck situations"""
            recovery_actions = []
            current_pos = self.position
            
            # Recovery strategy based on stuck reasons
            if "oscillation" in stuck_reasons:
                # Use existing anti-oscillation logic
                recovery_actions.extend(self.get_anti_oscillation_actions(feasible_actions, box_location))
            
            if "position_cycling" in stuck_reasons or "no_progress" in stuck_reasons:
                # Try completely different directions
                tried_recently = set(self.action_history) if len(self.action_history) > 0 else set()
                for action in ["UP", "DOWN", "LEFT", "RIGHT"]:
                    if action in feasible_actions and action not in tried_recently:
                        recovery_actions.append(action)
            
            if "unreachable_target" in stuck_reasons:
                # Find alternative target or take random exploration action
                if self.mission == "DELIVERY" and box_location:
                    # Try to find alternative approach cells
                    from warehouse import approach_cells_to_box
                    alt_approaches = approach_cells_to_box(self.model, box_location, self)
                    if alt_approaches:
                        # Pick closest alternative approach
                        distances = [(abs(current_pos[0] - ap[0]) + abs(current_pos[1] - ap[1]), ap) 
                                   for ap in alt_approaches]
                        closest_alt = min(distances, key=lambda x: x[0])[1]
                        
                        # Move towards alternative approach
                        dx = closest_alt[0] - current_pos[0]
                        dy = closest_alt[1] - current_pos[1]
                        
                        if dx > 0 and "RIGHT" in feasible_actions:
                            recovery_actions.append("RIGHT")
                        elif dx < 0 and "LEFT" in feasible_actions:
                            recovery_actions.append("LEFT")
                        elif dy > 0 and "DOWN" in feasible_actions:
                            recovery_actions.append("DOWN")
                        elif dy < 0 and "UP" in feasible_actions:
                            recovery_actions.append("UP")
                
                # Mark current target as problematic and request new mission
                self.target_unreachable_count = 0
                self.mission = None  # Force mission reassignment
            
            if "mission_stagnation" in stuck_reasons:
                # Request immediate mission reassignment
                self.mission = None
                self.target = None
                # Force exploration towards box areas
                if hasattr(self.model, 'boxes') and self.model.boxes:
                    nearest_box = min(self.model.boxes, 
                                    key=lambda b: abs(b['pos'][0] - current_pos[0]) + abs(b['pos'][1] - current_pos[1]))
                    box_pos = nearest_box['pos']
                    dx = box_pos[0] - current_pos[0]
                    dy = box_pos[1] - current_pos[1]
                    
                    if abs(dx) > abs(dy):
                        recovery_actions.append("RIGHT" if dx > 0 else "LEFT")
                    else:
                        recovery_actions.append("DOWN" if dy > 0 else "UP")
            
            if "wall_following" in stuck_reasons:
                # Break wall following with perpendicular movement
                last_action = self.action_history[-1] if self.action_history else None
                if last_action in ["UP", "DOWN"]:
                    for action in ["LEFT", "RIGHT"]:
                        if action in feasible_actions:
                            recovery_actions.append(action)
                elif last_action in ["LEFT", "RIGHT"]:
                    for action in ["UP", "DOWN"]:
                        if action in feasible_actions:
                            recovery_actions.append(action)
            
            # Emergency random walk if no specific recovery found
            if not recovery_actions:
                movement_actions = [a for a in feasible_actions if a in ["UP", "DOWN", "LEFT", "RIGHT"]]
                if movement_actions:
                    recovery_actions = movement_actions
            
            # Add WAIT as last resort
            if not recovery_actions and "WAIT" in feasible_actions:
                recovery_actions.append("WAIT")
            
            return recovery_actions
        
        robot_class.get_unstuck_actions = get_unstuck_actions
        
        # Enhanced mission timeout detection
        def check_mission_timeout(self):
            """Check if robot has been stuck on current mission too long"""
            current_step = getattr(self.model, 'step_count', 0)
            
            # Mission-specific timeouts
            timeout_limits = {
                "DELIVERY": 30,  # 30 steps to complete delivery
                "PICKUP": 25,   # 25 steps to complete pickup  
                "RECHARGE": 20, # 20 steps to reach charger
                "RESTING": 15   # 15 steps to reach rest point
            }
            
            if self.mission in timeout_limits:
                if not hasattr(self, 'mission_start_step'):
                    self.mission_start_step = current_step
                
                time_on_mission = current_step - self.mission_start_step
                if time_on_mission > timeout_limits[self.mission]:
                    return True
            
            return False
        
        robot_class.check_mission_timeout = check_mission_timeout
        
        # Enhanced plan method
        def enhanced_plan(self, box_location=None):
            """Enhanced planning with stuck detection and recovery"""
            
            # Check for comprehensive stuck conditions
            current_pos = self.position
            
            # Get initial feasible actions
            feasible = self.valid_actions(
                *current_pos,
                self.carrying,
                self.target,
                self.mission,
                box_location
            )
            
            # Mission timeout check
            if self.check_mission_timeout():
                print(f"Robot {getattr(self, 'id', '?')} mission timeout detected, resetting mission")
                self.mission = None
                self.target = None
                self.mission_start_step = getattr(self.model, 'step_count', 0)
            
            # Handle critical actions first (unchanged)
            had_pick = ("PICKUP" in feasible)
            had_drop = ("DISCHARGE" in feasible)
            
            if had_drop:
                self.proposal = "DISCHARGE"
                self.last_successful_delivery = getattr(self.model, 'step_count', 0)
                return
            elif had_pick:
                self.proposal = "PICKUP"
                return
            elif ("RECHARGE" in feasible) and (self.battery < 10):
                self.proposal = "RECHARGE"
                return
            
            # Check for stuck conditions before normal planning
            stuck_reasons = self.detect_comprehensive_stuck("WAIT")  # Use WAIT as placeholder
            
            if stuck_reasons:
                print(f"Robot {getattr(self, 'id', '?')} detected stuck: {stuck_reasons}")
                recovery_actions = self.get_unstuck_actions(feasible, box_location, stuck_reasons)
                if recovery_actions:
                    self.proposal = random.choice(recovery_actions)
                    self.emergency_mode = True
                    return
            else:
                self.emergency_mode = False
            
            # Normal ε-greedy planning (existing logic)
            if random.random() > self.model.global_epsilon:  # EXPLOIT
                qvals = {act: self.model.q_function(self.model, self, act, box_location) for act in feasible}
                best_action = max(
                    feasible,
                    key=lambda act: (qvals[act], 0 if act != "WAIT" else -1)
                )
                self.proposal = best_action
            else:  # EXPLORE
                # Enhanced exploration with stuck avoidance
                goals = self.model.goal_cells(self.model, self, box_location) if hasattr(self.model, 'goal_cells') else []
                if goals:
                    # Existing goal-directed exploration logic
                    from warehouse import closest_goal_and_dist, goal_cells, is_on_guidance_line_for_box, DIRS, next_pos_from_action
                    gx, gy, d0 = closest_goal_and_dist(current_pos, goals)
                    
                    better = []
                    for act in feasible:
                        if act in DIRS:
                            nx, ny = next_pos_from_action(self.model, current_pos, act)
                            d1 = abs(gx - nx) + abs(gy - ny)
                            
                            # Avoid recently tried positions
                            if (nx, ny) not in self.tried_positions:
                                if d1 < d0:
                                    better.append(act)
                    
                    if better:
                        chosen_action = random.choice(better)
                        # Remember this position
                        next_pos = next_pos_from_action(self.model, current_pos, chosen_action)
                        self.tried_positions.add(next_pos)
                        # Clear tried positions periodically
                        if len(self.tried_positions) > 5:
                            self.tried_positions.clear()
                        self.proposal = chosen_action
                    else:
                        non_wait = [a for a in feasible if a != "WAIT"]
                        self.proposal = random.choice(non_wait) if non_wait else "WAIT"
                else:
                    non_wait = [a for a in feasible if a != "WAIT"]
                    self.proposal = random.choice(non_wait) if non_wait else "WAIT"
        
        # Replace original plan method
        if not hasattr(robot_class, 'original_plan'):
            robot_class.original_plan = robot_class.plan
        robot_class.enhanced_plan = enhanced_plan
        
        return robot_class

def enhance_warehouse_model(warehouse_class):
    """Add pathfinding and mission management enhancements to Warehouse model"""
    
    def is_path_blocked(self, start_pos, end_pos):
        """Simple pathfinding check to detect unreachable targets"""
        if not hasattr(self, 'occupied') or not self.occupied:
            return False
            
        # Simple line-of-sight check
        x1, y1 = start_pos
        x2, y2 = end_pos
        
        # Check if direct path is blocked
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        
        # If too far apart, consider potentially blocked
        if dx + dy > 10:
            return True
            
        # Check intermediate positions for obstacles
        steps = max(dx, dy)
        if steps == 0:
            return False
            
        for i in range(1, steps):
            x = x1 + (x2 - x1) * i // steps
            y = y1 + (y2 - y1) * i // steps
            if (x, y) in self.occupied:
                return True
                
        return False
    
    warehouse_class.is_path_blocked = is_path_blocked
    
    def enhanced_mission_assignment(self):
        """Enhanced mission assignment that prevents robots from getting stuck"""
        
        # Count robots without missions or stuck robots
        available_robots = []
        stuck_robots = []
        
        for robot in self.robots:
            if hasattr(robot, 'emergency_mode') and robot.emergency_mode:
                stuck_robots.append(robot)
            elif robot.mission in [None, "RESTING"]:
                available_robots.append(robot)
        
        # Prioritize reassigning missions to stuck robots
        for robot in stuck_robots:
            robot.mission = None
            robot.target = None
            available_robots.append(robot)
        
        # Assign missions to available robots
        if available_robots and hasattr(self, 'pending_missions') and self.pending_missions:
            try:
                self.assign_all_pending_nearest()
            except:
                pass
        
        # Create more missions if needed
        if len(available_robots) > len(getattr(self, 'pending_missions', [])):
            try:
                self.seed_random_missions(n=len(available_robots))
            except:
                pass
    
    # Enhance the existing step method
    if not hasattr(warehouse_class, 'original_phase_plan'):
        warehouse_class.original_phase_plan = warehouse_class._phase_plan
    
    def enhanced_phase_plan(self):
        # Run enhanced mission assignment
        self.enhanced_mission_assignment()
        
        # Run original phase plan logic
        self.original_phase_plan()
    
    warehouse_class._phase_plan = enhanced_phase_plan
    warehouse_class.enhanced_mission_assignment = enhanced_mission_assignment
    
    return warehouse_class

def apply_stuck_robot_solution(warehouse_model):
    """Apply the complete stuck robot solution to a warehouse model instance"""
    
    # Create solution instance
    solution = StuckRobotSolution()
    
    # Enhance the Robot class
    robot_class = type(warehouse_model.robots[0]) if warehouse_model.robots else None
    if robot_class:
        solution.enhance_robot_class(robot_class)
        
        # Apply enhanced planning to existing robots
        for robot in warehouse_model.robots:
            robot.enhanced_setup = robot_class.enhanced_setup.__get__(robot, robot_class)
            robot.detect_comprehensive_stuck = robot_class.detect_comprehensive_stuck.__get__(robot, robot_class)
            robot.get_unstuck_actions = robot_class.get_unstuck_actions.__get__(robot, robot_class)
            robot.check_mission_timeout = robot_class.check_mission_timeout.__get__(robot, robot_class)
            robot.enhanced_plan = robot_class.enhanced_plan.__get__(robot, robot_class)
            
            # Initialize enhanced attributes
            robot.position_history = deque(maxlen=10)
            robot.action_history = deque(maxlen=8)
            robot.stuck_timer = 0
            robot.last_progress_step = 0
            robot.target_unreachable_count = 0
            robot.mission_stuck_timer = 0
            robot.emergency_mode = False
            robot.last_successful_delivery = 0
            robot.tried_positions = set()
            robot.avoid_positions = set()
            robot.preferred_directions = []
            
            # Replace plan method
            robot.plan = robot.enhanced_plan
    
    # Enhance the warehouse model
    warehouse_class = type(warehouse_model)
    enhance_warehouse_model(warehouse_class)
    
    print("✅ Enhanced stuck robot solution applied successfully!")
    print("Features added:")
    print("  - Comprehensive stuck detection (oscillation, cycling, stagnation)")
    print("  - Smart recovery actions for different stuck types")
    print("  - Mission timeout detection and reassignment")
    print("  - Enhanced pathfinding assistance")
    print("  - Emergency unstuck mode")
    
    return warehouse_model

if __name__ == "__main__":
    print("Stuck Robot Solution Module")
    print("=" * 50)
    print("This module provides comprehensive solutions for robots that get stuck.")
    print("Import and use apply_stuck_robot_solution(model) to enhance your warehouse model.")