"""
Improved stuck robot prevention system.
This focuses on preventing robots from getting stuck in the first place
rather than just recovering from stuck situations.
"""

def apply_improved_stuck_prevention():
    """
    Apply improved stuck prevention to warehouse.py.
    This version focuses on preventing stuck situations rather than just recovering.
    """
    
    # Read the current warehouse.py file
    with open('warehouse.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add smarter action selection with lookahead
    smart_action_selection = '''
    def evaluate_action_quality(self, action, box_location=None):
        """Evaluate how good an action is by looking ahead"""
        if action not in ["UP", "DOWN", "LEFT", "RIGHT"]:
            return 0.5  # Neutral score for non-movement actions
            
        next_pos = next_pos_from_action(self.model, self.position, action)
        
        # If action doesn't move us, it's poor quality
        if next_pos == self.position:
            return 0.1
            
        score = 0.5  # Base score
        
        # Bonus for moving toward goal
        if self.target and len(self.target) >= 2:
            current_dist = abs(self.position[0] - self.target[0]) + abs(self.position[1] - self.target[1])
            new_dist = abs(next_pos[0] - self.target[0]) + abs(next_pos[1] - self.target[1])
            if new_dist < current_dist:
                score += 0.3  # Good move toward target
            elif new_dist > current_dist:
                score -= 0.2  # Move away from target
        
        # Penalty for recent positions (avoid cycling)
        if hasattr(self, 'position_history') and next_pos in self.position_history[-3:]:
            score -= 0.4
            
        # Bonus for guidance lines when appropriate
        if (self.mission == "DELIVERY" and not self.carrying and box_location is not None):
            if is_on_guidance_line_for_box(self.model, next_pos, box_location):
                score += 0.2
                
        # Penalty for corners and dead ends
        adjacent_free = sum(1 for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)] 
                           if self.model.cell_is_free((next_pos[0] + dx, next_pos[1] + dy)))
        if adjacent_free <= 1:
            score -= 0.3  # Dead end penalty
        elif adjacent_free == 2:
            score -= 0.1  # Corner penalty
            
        return max(0.0, min(1.0, score))  # Clamp to [0,1]
'''
    
    # Add the method after the existing get_anti_oscillation_actions method
    if 'return alternative_actions' in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'return alternative_actions' in line:
                # Find the end of this method and insert the new method
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() == '' or (lines[j].strip() and not lines[j].startswith('    ')):
                        lines.insert(j, smart_action_selection)
                        break
                break
        content = '\n'.join(lines)
    
    # 2. Improve the main planning logic to use action quality evaluation
    improved_planning = '''
        # Check for comprehensive stuck conditions first
        stuck_indicators = 0
        if hasattr(self, 'detect_comprehensive_stuck'):
            if self.detect_comprehensive_stuck("WAIT"):
                stuck_indicators = 2
        
        if stuck_indicators >= 2:
            print(f"Robot {getattr(self, 'id', '?')} applying emergency recovery")
            
            # Get all movement actions and evaluate their quality
            movement_actions = [a for a in feasible if a in ["UP", "DOWN", "LEFT", "RIGHT"]]
            
            if movement_actions and hasattr(self, 'evaluate_action_quality'):
                action_scores = [(a, self.evaluate_action_quality(a, box_location)) for a in movement_actions]
                action_scores.sort(key=lambda x: x[1], reverse=True)  # Best first
                
                # Choose best quality action that we haven't tried recently
                recent_actions = getattr(self, 'movement_history', [])[-2:]
                for action, score in action_scores:
                    if action not in recent_actions:
                        self.proposal = action
                        self.stuck_timer = 0
                        return
                
                # If all actions tried recently, pick the best one anyway
                if action_scores:
                    self.proposal = action_scores[0][0]
                    self.stuck_timer = 0
                    return
            
            # Fallback to mission reset if no good movement options
            if self.stuck_timer >= 5:
                self.mission = None
                self.target = None
                print(f"Robot {getattr(self, 'id', '?')} mission reset - completely stuck")
'''
    
    # Replace the existing stuck check in the plan method
    old_stuck_check = '''        # Check for comprehensive stuck conditions
        if hasattr(self, 'detect_comprehensive_stuck') and self.detect_comprehensive_stuck(self.proposal if hasattr(self, 'proposal') else "WAIT"):
            print(f"Robot {getattr(self, 'id', '?')} is stuck, applying recovery")
            
            # Emergency recovery actions
            recovery_actions = []
            
            # Try completely different directions from recent history
            recent_actions = getattr(self, 'movement_history', [])
            for action in ["UP", "DOWN", "LEFT", "RIGHT"]:
                if action in feasible and action not in recent_actions[-2:]:
                    recovery_actions.append(action)
            
            # If no different directions, try perpendicular to last movement
            if not recovery_actions and recent_actions:
                last_action = recent_actions[-1]
                if last_action in ["UP", "DOWN"]:
                    recovery_actions = [a for a in ["LEFT", "RIGHT"] if a in feasible]
                elif last_action in ["LEFT", "RIGHT"]:
                    recovery_actions = [a for a in ["UP", "DOWN"] if a in feasible]
            
            # Force mission reset if stuck too long
            if self.stuck_timer >= 5:
                self.mission = None
                self.target = None
                self.mission_start_step = getattr(self.model, 'step_count', 0)
                print(f"Robot {getattr(self, 'id', '?')} mission reset due to being stuck")
            
            # Choose recovery action
            if recovery_actions:
                self.proposal = random.choice(recovery_actions)
                self.stuck_timer = 0  # Reset stuck timer
                return  # Skip normal planning'''
    
    if old_stuck_check in content:
        content = content.replace(old_stuck_check, improved_planning)
    
    # 3. Improve the exploration section to use action quality evaluation
    improved_exploration = '''            else:  # EXPLORE (ε)
                # Enhanced exploration with action quality evaluation
                goals = goal_cells(self.model, self, box_location)
                if goals:
                    gx, gy, d0 = closest_goal_and_dist(self.position, goals)
                    
                    # Get all movement actions and evaluate their quality
                    movement_actions = [a for a in feasible if a in DIRS]
                    
                    if movement_actions and hasattr(self, 'evaluate_action_quality'):
                        # Score actions based on quality and goal progress
                        action_scores = []
                        for act in movement_actions:
                            quality_score = self.evaluate_action_quality(act, box_location)
                            
                            # Bonus for moving toward goal
                            nx, ny = next_pos_from_action(self.model, self.position, act)
                            d1 = abs(gx - nx) + abs(gy - ny)
                            progress_bonus = 0.2 if d1 < d0 else 0
                            
                            # Check guidance lines
                            guidance_bonus = 0
                            if (self.mission == "DELIVERY" and not self.carrying and 
                                box_location is not None and 
                                is_on_guidance_line_for_box(self.model, (nx, ny), box_location)):
                                guidance_bonus = 0.3
                            
                            total_score = quality_score + progress_bonus + guidance_bonus
                            action_scores.append((act, total_score))
                        
                        # Sort by score and add some randomness
                        action_scores.sort(key=lambda x: x[1], reverse=True)
                        
                        # Choose from top 3 actions with weighted randomness
                        top_actions = action_scores[:min(3, len(action_scores))]
                        if top_actions:
                            # Weighted selection favoring better actions
                            weights = [score for _, score in top_actions]
                            if sum(weights) > 0:
                                chosen_idx = np.random.choice(len(top_actions), 
                                                            p=[w/sum(weights) for w in weights])
                                self.proposal = top_actions[chosen_idx][0]
                            else:
                                self.proposal = random.choice([act for act, _ in top_actions])
                        else:
                            non_wait = [a for a in feasible if a != "WAIT"]
                            self.proposal = random.choice(non_wait) if non_wait else "WAIT"
                    else:
                        # Fallback to original exploration logic
                        better = []
                        for act in movement_actions:
                            if act in DIRS:
                                nx, ny = next_pos_from_action(self.model, self.position, act)
                                d1 = abs(gx - nx) + abs(gy - ny)
                                if d1 < d0:
                                    better.append(act)
                        
                        if better:
                            self.proposal = random.choice(better)
                        else:
                            non_wait = [a for a in feasible if a != "WAIT"]
                            self.proposal = random.choice(non_wait) if non_wait else "WAIT"
                else:
                    non_wait = [a for a in feasible if a != "WAIT"]
                    self.proposal = random.choice(non_wait) if non_wait else "WAIT"'''
    
    # Find and replace the exploration section
    if 'else:  # EXPLORE (ε)' in content:
        lines = content.split('\n')
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            if 'else:  # EXPLORE (ε)' in line:
                start_idx = i
            elif start_idx is not None and line.strip() and not line.startswith('                '):
                # Found the end of the exploration section
                end_idx = i
                break
        
        if start_idx is not None and end_idx is not None:
            # Replace the exploration section
            lines[start_idx:end_idx] = improved_exploration.strip().split('\n')
            content = '\n'.join(lines)
    
    # 4. Improve mission assignment to avoid assigning unreachable targets
    improved_mission_assignment = '''
    def is_target_reachable(self, robot_pos, target_pos):
        """Simple check if target is reachable (not blocked by obstacles)"""
        if not target_pos or len(target_pos) < 2:
            return False
            
        # Simple distance check
        distance = abs(robot_pos[0] - target_pos[0]) + abs(robot_pos[1] - target_pos[1])
        if distance > 15:  # Too far, likely unreachable
            return False
            
        # Check if target position is free
        if not self.cell_is_free((target_pos[0], target_pos[1])):
            return False
            
        return True
'''
    
    # Add the reachability check method
    if 'def cell_is_free(self, pos):' in content:
        content = content.replace('def cell_is_free(self, pos):', 
                                improved_mission_assignment + '\n    def cell_is_free(self, pos):')
    
    # Write the improved file
    with open('warehouse.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Applied improved stuck prevention to warehouse.py")
    print("Improvements applied:")
    print("  - Smart action quality evaluation with lookahead")
    print("  - Improved exploration using action scoring")
    print("  - Enhanced stuck detection with better recovery")
    print("  - Target reachability checking")
    print("  - Reduced intervention frequency through prevention")

if __name__ == "__main__":
    apply_improved_stuck_prevention()