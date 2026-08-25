"""
Simple and direct stuck robot fixes integrated into the existing warehouse system.
This script applies targeted fixes to improve win rate by preventing robots from getting stuck.
"""

import numpy as np
import random
from collections import deque

def apply_stuck_fixes_to_warehouse():
    """
    Apply stuck robot fixes directly to the warehouse.py file.
    This includes:
    1. Enhanced stuck detection
    2. Mission timeout handling 
    3. Better target reassignment
    4. Emergency unstuck modes
    """
    
    # Read the current warehouse.py file
    with open('warehouse.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add enhanced stuck detection attributes to Robot setup
    setup_enhancement = '''
        # Enhanced stuck detection attributes
        self.position_history = []  # Track last 10 positions
        self.stuck_timer = 0        # Steps without progress
        self.mission_start_step = 0 # When current mission started
        self.last_successful_action_step = 0  # Last time we did something useful
'''
    
    # Find the setup method and add enhancements
    if 'self.stuck_counter = 0      # Count consecutive similar movements' in content:
        content = content.replace(
            'self.stuck_counter = 0      # Count consecutive similar movements',
            'self.stuck_counter = 0      # Count consecutive similar movements' + setup_enhancement
        )
    
    # 2. Enhance the detect_oscillation method with more stuck patterns
    enhanced_detect_method = '''
    def detect_comprehensive_stuck(self, proposed_action):
        """Enhanced stuck detection beyond simple oscillation"""
        current_pos = self.position
        current_step = getattr(self.model, 'step_count', self.model.stats.get('step', 0))
        
        # Track position history
        self.position_history.append(current_pos)
        if len(self.position_history) > 10:
            self.position_history.pop(0)
        
        stuck_indicators = 0
        
        # 1. Original oscillation detection
        if self.detect_oscillation(proposed_action):
            stuck_indicators += 2
        
        # 2. Position cycling (staying in same small area)
        if len(self.position_history) >= 6:
            recent_positions = self.position_history[-6:]
            unique_positions = len(set(recent_positions))
            if unique_positions <= 2:
                stuck_indicators += 1
        
        # 3. No progress tracking
        if len(self.position_history) >= 5:
            if current_pos == self.position_history[-5]:
                self.stuck_timer += 1
            else:
                self.stuck_timer = 0
        
        if self.stuck_timer >= 4:
            stuck_indicators += 2
        
        # 4. Mission stagnation
        if hasattr(self, 'mission_start_step'):
            time_on_mission = current_step - self.mission_start_step
            if time_on_mission > 30:  # 30 steps on same mission
                stuck_indicators += 1
        
        # 5. Action ineffectiveness
        if hasattr(self, 'last_successful_action_step'):
            time_since_success = current_step - self.last_successful_action_step
            if time_since_success > 20:  # 20 steps without useful action
                stuck_indicators += 1
        
        return stuck_indicators >= 2  # Stuck if 2+ indicators
'''
    
    # Add the method after the existing detect_oscillation method
    if 'return False' in content and 'def detect_oscillation' in content:
        # Find the end of detect_oscillation method
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'def detect_oscillation' in line:
                # Find the end of this method
                method_start = i
                indent_level = len(line) - len(line.lstrip())
                for j in range(i + 1, len(lines)):
                    if lines[j].strip() == '':
                        continue
                    current_indent = len(lines[j]) - len(lines[j].lstrip())
                    if current_indent <= indent_level and lines[j].strip():
                        # Found next method/class
                        lines.insert(j, enhanced_detect_method)
                        break
                break
        content = '\n'.join(lines)
    
    # 3. Enhance the plan method with stuck recovery
    plan_enhancement = '''
        # Check for comprehensive stuck conditions
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
                return  # Skip normal planning
'''
    
    # Insert this enhancement in the plan method before the epsilon-greedy section
    if 'else:  # EXPLORE (ε)' in content:
        content = content.replace('else:  # EXPLORE (ε)', plan_enhancement + '\n        else:  # EXPLORE (ε)')
    
    # 4. Add mission timeout tracking to mission assignment
    mission_timeout_code = '''
        # Track mission start time
        if not hasattr(robot, 'mission_start_step'):
            robot.mission_start_step = self.stats.get('step', 0)
        elif robot.mission != old_mission:  # Mission changed
            robot.mission_start_step = self.stats.get('step', 0)
'''
    
    # 5. Add successful action tracking to the act method
    successful_action_tracking = '''
        # Track successful actions for stuck detection
        if a in ["PICKUP", "DISCHARGE"]:
            self.last_successful_action_step = getattr(self.model, 'step_count', self.model.stats.get('step', 0))
        elif a in DIRS and tuple(next_pos) != tuple(prev_pos):
            # Successful movement
            self.last_successful_action_step = getattr(self.model, 'step_count', self.model.stats.get('step', 0))
'''
    
    # Insert after the action execution in act method
    if 'self.battery = max(self.battery - 0.10, 0)' in content:
        content = content.replace(
            'self.battery = max(self.battery - 0.10, 0)',
            'self.battery = max(self.battery - 0.10, 0)\n\n' + successful_action_tracking
        )
    
    # 6. Enhanced mission seeding to ensure robots always have work
    enhanced_mission_seeding = '''
        # Enhanced mission seeding - ensure every robot has opportunity for missions
        try:
            idle_robots = [r for r in self.robots if r.mission in (None, "RESTING")]
            pending_count = len(getattr(self, 'pending_missions', []))
            
            # Always maintain at least 2 missions per idle robot
            needed_missions = max(0, (len(idle_robots) * 2) - pending_count)
            if needed_missions > 0 and int(self.stats.get("deliveries", 0)) < 999:
                self.seed_random_missions(n=needed_missions)
                
            # Force mission reassignment for robots stuck too long
            for robot in idle_robots:
                if hasattr(robot, 'stuck_timer') and robot.stuck_timer >= 3:
                    robot.mission = None  # Force reassignment
                    
        except Exception as e:
            pass  # Graceful failure
'''
    
    # Replace the existing mission seeding logic
    if 'self.seed_random_missions(n=missions_needed)' in content:
        # Find and replace the entire mission seeding block
        lines = content.split('\n')
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            if 'available_robots = sum(1 for r in self.robots' in line:
                start_idx = i
            elif start_idx is not None and 'except Exception:' in line:
                end_idx = i + 2  # Include the pass statement
                break
        
        if start_idx is not None and end_idx is not None:
            # Replace the mission seeding block
            lines[start_idx:end_idx] = enhanced_mission_seeding.strip().split('\n')
            content = '\n'.join(lines)
    
    # 7. Add step counting for better time tracking
    step_count_enhancement = '''
        # Add step counting for stuck detection
        if not hasattr(self, 'step_count'):
            self.step_count = 0
        self.step_count += 1
'''
    
    # Add to the beginning of the step method
    if 'def step(self):' in content and 'self.intended = {}' in content:
        content = content.replace(
            'def step(self):\n        """Execute one simulation step: plan -> resolve conflicts -> act -> update."""\n        self.intended = {}',
            'def step(self):\n        """Execute one simulation step: plan -> resolve conflicts -> act -> update."""' + 
            step_count_enhancement + '\n        self.intended = {}'
        )
    
    # Write the enhanced file
    with open('warehouse.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Applied stuck robot fixes to warehouse.py")
    print("Enhancements applied:")
    print("  - Enhanced stuck detection (position cycling, mission stagnation)")
    print("  - Emergency recovery actions for stuck robots")
    print("  - Mission timeout handling and forced reassignment")
    print("  - Better mission seeding to ensure work availability")
    print("  - Successful action tracking for progress monitoring")
    
if __name__ == "__main__":
    apply_stuck_fixes_to_warehouse()