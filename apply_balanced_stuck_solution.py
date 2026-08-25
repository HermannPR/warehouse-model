#!/usr/bin/env python3
"""
Apply a balanced stuck robot detection and recovery solution to warehouse.py
This version is more conservative to avoid over-detection while still preventing robots from getting truly stuck.
"""

import re

def apply_balanced_stuck_solution():
    # Read the original warehouse.py
    with open('warehouse.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove any existing stuck detection code first
    # Remove position_tracker initialization
    content = re.sub(r'\s*self\.position_tracker = deque\(maxlen=\d+\)\s*\n', '', content)
    content = re.sub(r'\s*from collections import deque\s*\n', '', content)
    
    # Remove is_really_stuck method
    content = re.sub(r'\s*def is_really_stuck\(self\):.*?return False\s*\n', '', content, flags=re.DOTALL)
    
    # Remove stuck detection from plan() method
    content = re.sub(r'\s*# Check if robot is stuck.*?self\.current_task_finished = True\s*\n', '', content, flags=re.DOTALL)
    
    # Remove position tracking from act() method
    content = re.sub(r'\s*# Track position for stuck detection.*?\n', '', content)
    content = re.sub(r'\s*self\.position_tracker\.append\(self\.pos\)\s*\n', '', content)
    
    # Now apply the new balanced solution
    
    # Add imports at the top
    if 'from collections import deque' not in content:
        import_section = content.split('\n')
        for i, line in enumerate(import_section):
            if line.startswith('import') or line.startswith('from'):
                continue
            else:
                import_section.insert(i, 'from collections import deque')
                break
        content = '\n'.join(import_section)
    
    # Add position tracker initialization in __init__
    init_pattern = r'(def __init__\(self, unique_id, model\):.*?self\.success_reward = 10)'
    replacement = r'\1\n        # Balanced stuck detection\n        self.position_tracker = deque(maxlen=12)  # Increased buffer\n        self.stuck_threshold = 8  # More conservative threshold\n        self.last_reset_step = -20  # Cooldown tracking'
    content = re.sub(init_pattern, replacement, content, flags=re.DOTALL)
    
    # Add the is_really_stuck method - more conservative version
    stuck_method = '''
    def is_really_stuck(self):
        """
        Balanced stuck detection - only triggers for truly stuck situations
        Returns True if robot is genuinely stuck and needs intervention
        """
        # Don't check if we recently reset or don't have enough history
        if (self.model.current_step - self.last_reset_step) < 20:
            return False
            
        if len(self.position_tracker) < self.stuck_threshold:
            return False
        
        # Check for position repetition (oscillation)
        positions = list(self.position_tracker)
        unique_positions = len(set(positions))
        
        # Only consider stuck if visiting very few unique positions
        if unique_positions <= 2:
            # Additional check: are we making progress on current task?
            if hasattr(self, 'target_box') and self.target_box is not None:
                # If we have a task but haven't moved much, we're stuck
                return True
            elif hasattr(self, 'target_location') and self.target_location is not None:
                # Same for delivery tasks
                return True
        
        return False
'''
    
    # Insert the method after the __init__ method
    init_end_pattern = r'(def __init__\(self, unique_id, model\):.*?self\.last_reset_step = -20)'
    content = re.sub(init_end_pattern, r'\1' + stuck_method, content, flags=re.DOTALL)
    
    # Add stuck detection to the plan() method - more conservative
    plan_pattern = r'(def plan\(self\):.*?action = self\.choose_action\(state_key\))'
    stuck_detection = '''
        # Conservative stuck detection and recovery
        if self.is_really_stuck():
            print(f"Robot {self.unique_id} appears genuinely stuck, resetting mission")
            self.current_task_finished = True
            self.last_reset_step = self.model.current_step
            # Reset mission state
            if hasattr(self, 'target_box'):
                self.target_box = None
            if hasattr(self, 'target_location'):
                self.target_location = None
            # Try a random action to break out
            action = self.random.choice(['up', 'down', 'left', 'right'])
        
        action = self.choose_action(state_key)'''
    
    replacement_plan = r'\1\n        ' + stuck_detection
    content = re.sub(plan_pattern, replacement_plan, content, flags=re.DOTALL)
    
    # Add position tracking to act() method
    act_pattern = r'(def act\(self\):.*?self\.model\.grid\.move_agent\(self, new_pos\))'
    act_replacement = r'\1\n        # Track position for balanced stuck detection\n        self.position_tracker.append(self.pos)'
    content = re.sub(act_pattern, act_replacement, content, flags=re.DOTALL)
    
    # Save the modified content
    with open('warehouse.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Applied balanced stuck robot detection and recovery solution!")
    print("📊 Features:")
    print("  - Conservative stuck detection (12-position buffer, 8-position threshold)")
    print("  - 20-step cooldown period between resets")
    print("  - Only triggers for genuine oscillation with active tasks")
    print("  - Random action to break out of stuck states")

if __name__ == "__main__":
    apply_balanced_stuck_solution()