#!/usr/bin/env python3
"""
Detailed State Analyzer - Analyzes specific stuck states and provides detailed diagnostics
"""

import sys
import json
from collections import Counter, defaultdict
sys.path.append('.')

from warehouse import Warehouse

class StateAnalyzer:
    def __init__(self, state_file='simulation_state.json'):
        self.state_file = state_file
        self.state_data = None
        
    def load_state(self):
        """Load the saved simulation state"""
        try:
            with open(self.state_file, 'r') as f:
                self.state_data = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading state file: {e}")
            return False
    
    def analyze_stuck_patterns(self):
        """Analyze patterns in stuck states"""
        if not self.state_data:
            print("No state data available")
            return
        
        print("🔍 DETAILED STUCK STATE ANALYSIS")
        print("=" * 50)
        
        # Basic info
        print(f"Step: {self.state_data['step']}")
        print(f"Reason: {self.state_data['reason']}")
        print(f"Robots: {len(self.state_data['robot_states'])}")
        
        # Analyze robot distribution
        missions = Counter(robot['mission'] for robot in self.state_data['robot_states'])
        positions = [tuple(robot['position']) for robot in self.state_data['robot_states']]
        carrying = sum(1 for robot in self.state_data['robot_states'] if robot['carrying'])
        
        print(f"\n📊 Robot Status Distribution:")
        print(f"  Missions: {dict(missions)}")
        print(f"  Carrying boxes: {carrying}/{len(self.state_data['robot_states'])}")
        print(f"  Positions: {positions}")
        
        # Check for position clusters (robots too close)
        position_distances = {}
        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions[i+1:], i+1):
                dist = abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
                position_distances[f"Robot{i}-Robot{j}"] = dist
        
        close_robots = {pair: dist for pair, dist in position_distances.items() if dist <= 2}
        if close_robots:
            print(f"  ⚠️  Close robots (≤2 cells): {close_robots}")
        
        # Analyze battery levels
        batteries = [robot['battery'] for robot in self.state_data['robot_states']]
        print(f"\n🔋 Battery Analysis:")
        print(f"  Range: {min(batteries):.1f}% - {max(batteries):.1f}%")
        print(f"  Average: {sum(batteries)/len(batteries):.1f}%")
        
        if min(batteries) < 20:
            print(f"  ⚠️  Low battery detected!")
        
        # Analyze recent history if available
        if 'recent_history' in self.state_data:
            history = self.state_data['recent_history']
            
            print(f"\n📈 Recent History Analysis:")
            
            # Position changes
            if 'positions' in history and len(history['positions']) > 1:
                position_changes = 0
                for i in range(1, len(history['positions'])):
                    prev_pos = history['positions'][i-1]
                    curr_pos = history['positions'][i]
                    if prev_pos != curr_pos:
                        position_changes += 1
                
                print(f"  Position changes: {position_changes}/{len(history['positions'])-1}")
                if position_changes < len(history['positions']) * 0.2:
                    print(f"  ⚠️  Very low movement detected!")
            
            # Mission changes
            if 'missions' in history:
                mission_changes = len(set(history['missions']))
                print(f"  Unique mission states: {mission_changes}")
                if mission_changes <= 1:
                    print(f"  ⚠️  No mission progress!")
            
            # Deliveries
            if 'deliveries' in history:
                total_deliveries = sum(history['deliveries'])
                print(f"  Recent deliveries: {total_deliveries}")
                if total_deliveries == 0:
                    print(f"  ⚠️  No recent deliveries!")
        
        # Provide diagnostic suggestions
        self.suggest_fixes()
    
    def suggest_fixes(self):
        """Suggest potential fixes based on analysis"""
        print(f"\n💡 DIAGNOSTIC SUGGESTIONS:")
        
        robots = self.state_data['robot_states']
        
        # Check for specific stuck patterns
        all_resting = all(robot['mission'] == 'RESTING' for robot in robots)
        all_delivery = all(robot['mission'] == 'DELIVERY' for robot in robots)
        all_carrying = all(robot['carrying'] for robot in robots)
        none_carrying = not any(robot['carrying'] for robot in robots)
        
        if all_resting:
            print("  • All robots RESTING - possible mission assignment issue")
            print("    → Check if boxes are available and accessible")
            print("    → Verify robot capability levels match available boxes")
        
        elif all_delivery and none_carrying:
            print("  • All robots on DELIVERY but none carrying - possible pathfinding issue")
            print("    → Check if robots can reach target boxes")
            print("    → Verify guidance lines are helping pathfinding")
        
        elif all_carrying:
            print("  • All robots carrying - possible drop point issue")
            print("    → Check if drop points are accessible")
            print("    → Verify robots can find path to drop zones")
        
        else:
            print("  • Mixed state detected - analyze individual robot issues")
        
        # Battery suggestions
        batteries = [robot['battery'] for robot in robots]
        if min(batteries) < 30:
            print("  • Low battery levels detected")
            print("    → Check recharge point accessibility")
            print("    → Verify recharge behavior is working")
        
        # Position clustering suggestions
        positions = [tuple(robot['position']) for robot in robots]
        if len(set(positions)) < len(positions):
            print("  • Robots clustered in same positions")
            print("    → Check conflict resolution system")
            print("    → Verify alternative path finding")

def main():
    analyzer = StateAnalyzer()
    
    if analyzer.load_state():
        analyzer.analyze_stuck_patterns()
    else:
        print("No simulation state file found. Run simulation_monitor.py first to generate state data.")
        
        # Create a quick simulation to generate state
        print("\nRunning quick simulation to generate analysis data...")
        import subprocess
        import sys
        
        cmd = [sys.executable, 'simulation_monitor.py', '--steps', '1000', '--robots', '2']
        subprocess.run(cmd)
        
        # Try analysis again
        if analyzer.load_state():
            analyzer.analyze_stuck_patterns()

if __name__ == "__main__":
    main()