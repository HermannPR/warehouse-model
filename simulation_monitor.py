#!/usr/bin/env python3
"""
Advanced Simulation Monitor with Automatic Visualization
Runs long simulations and detects stuck states, then launches visualization for analysis
"""

import sys
import time
import subprocess
import json
from collections import deque, defaultdict
sys.path.append('.')

from warehouse import Warehouse
import numpy as np

class SimulationMonitor:
    def __init__(self, config_path='layout.json', n_robots=4):
        self.config_path = config_path
        self.n_robots = n_robots
        self.model = None
        self.history = {
            'positions': deque(maxlen=50),  # Last 50 positions for each robot
            'missions': deque(maxlen=50),   # Last 50 mission states
            'deliveries': deque(maxlen=100), # Last 100 delivery events
            'rewards': deque(maxlen=100),   # Last 100 step rewards
            'battery_levels': deque(maxlen=50), # Last 50 battery readings
        }
        self.stuck_detection = {
            'position_threshold': 10,  # Steps without significant movement
            'mission_threshold': 50,   # Steps without mission progress
            'delivery_threshold': 200, # Steps without any delivery
            'low_reward_threshold': 100, # Steps with consistently low rewards
        }
        self.termination_reasons = []
        
    def setup_simulation(self):
        """Initialize the warehouse simulation"""
        try:
            self.model = Warehouse({'config_path': self.config_path})
            self.model.setup()
            
            # Set number of robots
            if hasattr(self.model, 'robots') and len(self.model.robots) > self.n_robots:
                self.model.robots = self.model.robots[:self.n_robots]
            
            print(f"✓ Simulation setup complete:")
            print(f"  Grid size: {self.model.W}x{self.model.H}")
            print(f"  Robots: {len(self.model.robots)}")
            print(f"  Boxes: {len(self.model.boxes) if hasattr(self.model, 'boxes') else 0}")
            return True
            
        except Exception as e:
            print(f"✗ Setup failed: {e}")
            return False
    
    def detect_stuck_state(self, step):
        """Detect if simulation is stuck in any way"""
        stuck_reasons = []
        
        # Check for position stagnation
        if len(self.history['positions']) >= self.stuck_detection['position_threshold']:
            recent_positions = list(self.history['positions'])[-self.stuck_detection['position_threshold']:]
            if len(set(str(pos) for pos in recent_positions)) <= 2:
                stuck_reasons.append(f"Position stagnation: robots not moving (last {self.stuck_detection['position_threshold']} steps)")
        
        # Check for mission stagnation
        if len(self.history['missions']) >= self.stuck_detection['mission_threshold']:
            recent_missions = list(self.history['missions'])[-self.stuck_detection['mission_threshold']:]
            if len(set(recent_missions)) <= 1:
                stuck_reasons.append(f"Mission stagnation: no mission progress (last {self.stuck_detection['mission_threshold']} steps)")
        
        # Check for delivery stagnation
        if len(self.history['deliveries']) >= self.stuck_detection['delivery_threshold']:
            recent_deliveries = list(self.history['deliveries'])[-self.stuck_detection['delivery_threshold']:]
            if sum(recent_deliveries) == 0:
                stuck_reasons.append(f"Delivery stagnation: no deliveries (last {self.stuck_detection['delivery_threshold']} steps)")
        
        # Check for consistently low rewards
        if len(self.history['rewards']) >= self.stuck_detection['low_reward_threshold']:
            recent_rewards = list(self.history['rewards'])[-self.stuck_detection['low_reward_threshold']:]
            avg_reward = sum(recent_rewards) / len(recent_rewards)
            if avg_reward < -0.05:  # Consistently negative rewards
                stuck_reasons.append(f"Low performance: average reward {avg_reward:.3f} (last {self.stuck_detection['low_reward_threshold']} steps)")
        
        # Check for battery issues
        if len(self.history['battery_levels']) >= 20:
            recent_batteries = list(self.history['battery_levels'])[-20:]
            min_battery = min(recent_batteries) if recent_batteries else 100
            if min_battery < 10:
                stuck_reasons.append(f"Battery crisis: minimum battery {min_battery}%")
        
        return stuck_reasons
    
    def record_step_data(self, step):
        """Record current step data for analysis"""
        try:
            # Record robot positions
            positions = []
            missions = []
            batteries = []
            
            for robot in self.model.robots:
                positions.append(tuple(robot.position) if hasattr(robot, 'position') else (0, 0))
                missions.append(getattr(robot, 'mission', 'UNKNOWN'))
                batteries.append(getattr(robot, 'battery', 100))
            
            self.history['positions'].append(positions)
            self.history['missions'].append(','.join(missions))
            self.history['battery_levels'].append(min(batteries))
            
            # Record deliveries (check if any robot just completed a delivery)
            deliveries_this_step = 0
            for robot in self.model.robots:
                if (hasattr(robot, 'mission') and robot.mission == 'RESTING' and 
                    not getattr(robot, 'carrying', True)):
                    deliveries_this_step += 1
            
            self.history['deliveries'].append(deliveries_this_step)
            
            # Record step reward (approximate from robot states)
            step_reward = 0
            for robot in self.model.robots:
                if hasattr(robot, 'battery') and robot.battery > 90:
                    step_reward += 0.1  # Bonus for good battery
                if hasattr(robot, 'mission') and robot.mission == 'DELIVERY':
                    step_reward += 0.05  # Bonus for active missions
            
            self.history['rewards'].append(step_reward)
            
        except Exception as e:
            print(f"Warning: Could not record step data: {e}")
    
    def check_termination_conditions(self, step, max_steps):
        """Check various termination conditions"""
        termination_info = {
            'terminated': False,
            'reason': None,
            'step': step,
            'max_steps': max_steps
        }
        
        # Check if we reached max steps
        if step >= max_steps:
            termination_info.update({
                'terminated': True,
                'reason': 'MAX_STEPS',
                'message': f'Simulation completed {max_steps} steps successfully'
            })
            return termination_info
        
        # Check for stuck states
        stuck_reasons = self.detect_stuck_state(step)
        if stuck_reasons:
            termination_info.update({
                'terminated': True,
                'reason': 'STUCK_STATE',
                'message': f'Simulation stuck at step {step}',
                'stuck_reasons': stuck_reasons
            })
            return termination_info
        
        # Check for completion (all robots successfully delivering)
        if step > 100:  # Allow some time to get started
            recent_deliveries = list(self.history['deliveries'])[-50:] if len(self.history['deliveries']) >= 50 else []
            if recent_deliveries and sum(recent_deliveries) >= len(self.model.robots) * 2:  # Multiple successful deliveries
                termination_info.update({
                    'terminated': True,
                    'reason': 'SUCCESS',
                    'message': f'Simulation successful: consistent deliveries achieved at step {step}'
                })
                return termination_info
        
        # Check for critical battery failure
        if len(self.history['battery_levels']) >= 10:
            recent_batteries = list(self.history['battery_levels'])[-10:]
            if all(b < 5 for b in recent_batteries):
                termination_info.update({
                    'terminated': True,
                    'reason': 'BATTERY_FAILURE',
                    'message': f'Critical battery failure at step {step}'
                })
                return termination_info
        
        return termination_info
    
    def launch_visualization(self, reason, step):
        """Launch visualization to analyze the current state"""
        print(f"\n🔍 LAUNCHING VISUALIZATION FOR ANALYSIS")
        print(f"Reason: {reason}")
        print(f"Step: {step}")
        print("=" * 60)
        
        try:
            # Save current state information
            state_info = {
                'step': step,
                'reason': reason,
                'robot_states': [],
                'recent_history': {
                    'positions': list(self.history['positions'])[-10:],
                    'missions': list(self.history['missions'])[-10:],
                    'deliveries': list(self.history['deliveries'])[-20:],
                    'battery_levels': list(self.history['battery_levels'])[-10:],
                }
            }
            
            # Record robot states
            for i, robot in enumerate(self.model.robots):
                robot_state = {
                    'id': i,
                    'position': tuple(robot.position) if hasattr(robot, 'position') else (0, 0),
                    'mission': getattr(robot, 'mission', 'UNKNOWN'),
                    'battery': getattr(robot, 'battery', 100),
                    'carrying': getattr(robot, 'carrying', False),
                    'target': getattr(robot, 'target', None)
                }
                state_info['robot_states'].append(robot_state)
            
            # Save state to file
            with open('simulation_state.json', 'w') as f:
                json.dump(state_info, f, indent=2, default=str)
            
            print("Current robot states:")
            for robot_state in state_info['robot_states']:
                print(f"  Robot {robot_state['id']}: {robot_state['mission']} | "
                      f"Pos: {robot_state['position']} | "
                      f"Battery: {robot_state['battery']}% | "
                      f"Carrying: {robot_state['carrying']}")
            
            print(f"\nState saved to: simulation_state.json")
            
            # Launch visualization
            print(f"\n🎮 Starting visualization...")
            cmd = [sys.executable, 'train.py', 'visualize', '--steps', '500', '--n-robots', str(self.n_robots)]
            
            # Run visualization in background and return immediately
            process = subprocess.Popen(cmd, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE,
                                     text=True)
            
            print(f"Visualization started with PID: {process.pid}")
            print("Controls: SPACE=Pause, S=Step, R=Reset, Q=Quit, +/-=Speed")
            print("Close the visualization window when done analyzing.")
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to launch visualization: {e}")
            return False
    
    def run_extended_simulation(self, max_steps=10000, check_interval=50):
        """Run extended simulation with monitoring"""
        print(f"🚀 EXTENDED SIMULATION MONITOR")
        print(f"Max steps: {max_steps:,}")
        print(f"Check interval: {check_interval}")
        print(f"Robots: {self.n_robots}")
        print("=" * 60)
        
        if not self.setup_simulation():
            return False
        
        start_time = time.time()
        last_check = 0
        
        try:
            for step in range(max_steps):
                # Run simulation step
                self.model.step()
                
                # Record data for analysis
                self.record_step_data(step)
                
                # Periodic checks
                if step - last_check >= check_interval:
                    # Check termination conditions
                    termination = self.check_termination_conditions(step, max_steps)
                    
                    if termination['terminated']:
                        elapsed = time.time() - start_time
                        
                        print(f"\n📊 SIMULATION TERMINATED")
                        print(f"Step: {step:,}/{max_steps:,} ({step/max_steps*100:.1f}%)")
                        print(f"Reason: {termination['reason']}")
                        print(f"Message: {termination['message']}")
                        print(f"Elapsed: {elapsed:.1f}s ({step/elapsed:.1f} steps/sec)")
                        
                        if 'stuck_reasons' in termination:
                            print("Stuck reasons:")
                            for reason in termination['stuck_reasons']:
                                print(f"  • {reason}")
                        
                        # Launch visualization for analysis
                        self.launch_visualization(termination['reason'], step)
                        return termination
                    
                    # Progress update
                    if step % (check_interval * 10) == 0:
                        elapsed = time.time() - start_time
                        recent_deliveries = sum(list(self.history['deliveries'])[-check_interval:])
                        avg_reward = np.mean(list(self.history['rewards'])[-check_interval:]) if self.history['rewards'] else 0
                        
                        print(f"Step {step:,}/{max_steps:,} | "
                              f"Deliveries: {recent_deliveries} | "
                              f"Avg Reward: {avg_reward:.3f} | "
                              f"{step/elapsed:.1f} steps/sec")
                    
                    last_check = step
                    
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n⏸️  SIMULATION INTERRUPTED")
            print(f"Step: {step:,}/{max_steps:,}")
            print(f"Elapsed: {elapsed:.1f}s")
            
            # Launch visualization for current state
            self.launch_visualization('INTERRUPTED', step)
            return {'terminated': True, 'reason': 'INTERRUPTED', 'step': step}
        
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ SIMULATION ERROR")
            print(f"Step: {step:,}/{max_steps:,}")
            print(f"Error: {e}")
            print(f"Elapsed: {elapsed:.1f}s")
            
            # Launch visualization for error analysis
            self.launch_visualization('ERROR', step)
            return {'terminated': True, 'reason': 'ERROR', 'step': step, 'error': str(e)}

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extended Simulation Monitor')
    parser.add_argument('--steps', type=int, default=10000, 
                       help='Maximum simulation steps (default: 10000)')
    parser.add_argument('--robots', type=int, default=4,
                       help='Number of robots (default: 4)')
    parser.add_argument('--check-interval', type=int, default=50,
                       help='Steps between checks (default: 50)')
    parser.add_argument('--config', default='layout.json',
                       help='Configuration file (default: layout.json)')
    
    args = parser.parse_args()
    
    monitor = SimulationMonitor(config_path=args.config, n_robots=args.robots)
    result = monitor.run_extended_simulation(max_steps=args.steps, 
                                           check_interval=args.check_interval)
    
    if result:
        print(f"\n📋 FINAL RESULT: {result['reason']} at step {result.get('step', 0)}")
    
    return result

if __name__ == "__main__":
    main()