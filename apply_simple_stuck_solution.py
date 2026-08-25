"""
Simple and targeted stuck robot solution.
This applies minimal but effective changes to improve win rates.
"""

def apply_simple_stuck_solution():
    """Apply a simple, targeted stuck robot solution"""
    
    # Read the current warehouse.py file
    with open('warehouse.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add simple stuck detection to robot setup
    if 'self.stuck_counter = 0      # Count consecutive similar movements' in content:
        content = content.replace(
            'self.stuck_counter = 0      # Count consecutive similar movements',
            'self.stuck_counter = 0      # Count consecutive similar movements\n' +
            '        self.position_tracker = []  # Track recent positions\n' +
            '        self.action_success_counter = 0  # Track successful actions'
        )
    
    # 2. Add a simple method to check if robot is truly stuck
    simple_stuck_check = '''
    def is_really_stuck(self):
        """Simple check if robot is really stuck (same position for too long)"""
        if len(self.position_tracker) < 5:
            return False
        
        # Check if we've been in the same few positions for too long
        recent_positions = self.position_tracker[-5:]
        unique_positions = len(set(recent_positions))
        
        # If we've only been in 1-2 positions in last 5 steps, we're stuck
        return unique_positions <= 2
'''
    
    # Add this method after the detect_oscillation method
    if 'return False' in content and 'def detect_oscillation' in content:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'def detect_oscillation' in line:
                # Find the end of this method and add the new method
                for j in range(i + 1, len(lines)):
                    if (lines[j].strip() and not lines[j].startswith('    ') and 
                        not lines[j].strip().startswith('#')):
                        lines.insert(j, simple_stuck_check)
                        break
                break
        content = '\n'.join(lines)
    
    # 3. Add position tracking to the act method
    position_tracking = '''
        # Track position for stuck detection
        if hasattr(self, 'position_tracker'):
            self.position_tracker.append(self.position)
            if len(self.position_tracker) > 8:
                self.position_tracker.pop(0)
        
        # Track successful actions
        if a in ["PICKUP", "DISCHARGE"]:
            self.action_success_counter = 0  # Reset - we did something useful
        elif a in DIRS and tuple(next_pos) != tuple(prev_pos):
            self.action_success_counter = 0  # Reset - we moved successfully
        else:
            self.action_success_counter += 1  # Increment failure counter
'''
    
    # Add position tracking after the action execution in act method
    if 'self.battery = max(self.battery - 0.10, 0)' in content:
        content = content.replace(
            'self.battery = max(self.battery - 0.10, 0)',
            'self.battery = max(self.battery - 0.10, 0)\n\n' + position_tracking
        )
    
    # 4. Add simple stuck recovery to the plan method
    simple_recovery = '''
        # Simple stuck recovery
        if hasattr(self, 'is_really_stuck') and self.is_really_stuck():
            # Force mission reset for really stuck robots
            self.mission = None
            self.target = None
            if hasattr(self, 'position_tracker'):
                self.position_tracker.clear()
            print(f"Robot {getattr(self, 'id', '?')} was stuck, resetting mission")
        
        # Also reset mission if no successful actions for too long
        if hasattr(self, 'action_success_counter') and self.action_success_counter >= 15:
            self.mission = None
            self.target = None
            self.action_success_counter = 0
            print(f"Robot {getattr(self, 'id', '?')} had no success, resetting mission")
'''
    
    # Add this at the beginning of the plan method, right after the feasible actions are determined
    if 'feasible = self.valid_actions(' in content:
        content = content.replace(
            'feasible = self.valid_actions(\n            *self.position,\n            self.carrying,\n            self.target,\n            self.mission,\n            box_location\n        )',
            'feasible = self.valid_actions(\n            *self.position,\n            self.carrying,\n            self.target,\n            self.mission,\n            box_location\n        )\n\n' + simple_recovery
        )
    
    # 5. Improve mission seeding to ensure robots always have work
    better_mission_seeding = '''
        # Better mission seeding - ensure every robot has opportunities
        try:
            idle_robots = [r for r in self.robots if r.mission in (None, "RESTING")]
            pending_count = len(getattr(self, 'pending_missions', []))
            
            # Always maintain enough missions for all robots
            if len(idle_robots) > pending_count and int(self.stats.get("deliveries", 0)) < 999:
                needed = len(idle_robots) - pending_count + 2  # Extra buffer
                self.seed_random_missions(n=needed)
        except Exception:
            pass  # Graceful failure
'''
    
    # Replace the complex mission seeding with simpler version
    if 'needed_missions = max(0, (len(idle_robots) * 2) - pending_count)' in content:
        # Find and replace the mission seeding block
        lines = content.split('\n')
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            if 'idle_robots = [r for r in self.robots if r.mission in (None, "RESTING")]' in line:
                start_idx = i
                break
        
        if start_idx is not None:
            # Find the end of the try block
            for i in range(start_idx, len(lines)):
                if 'except Exception' in lines[i]:
                    end_idx = i + 2  # Include the pass statement
                    break
            
            if end_idx is not None:
                # Replace the mission seeding block
                lines[start_idx-1:end_idx] = ['        # Better mission seeding - ensure every robot has opportunities'] + better_mission_seeding.strip().split('\n')
                content = '\n'.join(lines)
    
    # Write the enhanced file
    with open('warehouse.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Applied simple stuck robot solution to warehouse.py")
    print("Simple improvements applied:")
    print("  - Position tracking to detect truly stuck robots")
    print("  - Success counter to track robot effectiveness")
    print("  - Mission reset for stuck or ineffective robots")
    print("  - Improved mission seeding to ensure work availability")
    print("  - Minimal code changes to avoid breaking existing logic")

if __name__ == "__main__":
    apply_simple_stuck_solution()