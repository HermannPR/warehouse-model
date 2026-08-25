#!/usr/bin/env python3
"""
Focused Simulation Analyzer - Tests specific scenarios with trained weights
"""

import sys
import subprocess
import time
sys.path.append('.')

def run_scenario_test(scenario_name, episodes=50, robots=2, steps=5000):
    """Run a specific scenario test"""
    print(f"🎯 SCENARIO: {scenario_name}")
    print(f"Episodes: {episodes} | Robots: {robots} | Max Steps: {steps}")
    print("=" * 60)
    
    # First, train the model
    print("Phase 1: Training...")
    train_cmd = [sys.executable, 'train.py', 'train', 
                 '--episodes', str(episodes), 
                 '--n-robots', str(robots)]
    
    try:
        train_result = subprocess.run(train_cmd, capture_output=True, text=True, timeout=120)
        
        if train_result.returncode == 0:
            print("✓ Training completed successfully")
            
            # Extract success rate from training output
            lines = train_result.stdout.split('\n')
            success_rate = None
            for line in lines:
                if 'Final success rate' in line:
                    try:
                        success_rate = float(line.split(':')[1].strip().rstrip('%'))
                    except:
                        pass
            
            if success_rate is not None:
                print(f"Training success rate: {success_rate}%")
                
                # Now run the extended monitor
                print("\nPhase 2: Extended monitoring...")
                monitor_cmd = [sys.executable, 'simulation_monitor.py',
                              '--steps', str(steps),
                              '--robots', str(robots),
                              '--check-interval', '50']
                
                subprocess.run(monitor_cmd)
                
                return {'success': True, 'training_success_rate': success_rate}
            else:
                print("⚠️ Could not extract success rate")
                return {'success': True, 'training_success_rate': None}
                
        else:
            print(f"✗ Training failed: {train_result.stderr}")
            return {'success': False, 'error': train_result.stderr}
            
    except subprocess.TimeoutExpired:
        print("✗ Training timed out")
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        print(f"✗ Error: {e}")
        return {'success': False, 'error': str(e)}

def main():
    """Run multiple scenario tests"""
    scenarios = [
        {
            'name': 'Quick Learning (2 robots)',
            'episodes': 100,
            'robots': 2,
            'steps': 3000
        },
        {
            'name': 'Team Coordination (4 robots)',
            'episodes': 200,
            'robots': 4,
            'steps': 5000
        },
        {
            'name': 'Endurance Test (2 robots)',
            'episodes': 50,
            'robots': 2,
            'steps': 10000
        }
    ]
    
    print("🚀 SIMULATION SCENARIO ANALYZER")
    print("Running multiple training + monitoring scenarios")
    print("=" * 70)
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*20} SCENARIO {i}/{len(scenarios)} {'='*20}")
        
        result = run_scenario_test(
            scenario['name'],
            scenario['episodes'],
            scenario['robots'],
            scenario['steps']
        )
        
        result['scenario'] = scenario['name']
        results.append(result)
        
        print(f"\nScenario '{scenario['name']}' completed")
        print("-" * 50)
        
        # Brief pause between scenarios
        time.sleep(2)
    
    # Summary report
    print(f"\n{'='*20} FINAL SUMMARY {'='*20}")
    for result in results:
        status = "✓" if result['success'] else "✗"
        success_rate = result.get('training_success_rate', 'N/A')
        print(f"{status} {result['scenario']}: {success_rate}% success rate")
    
    return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Simulation Scenario Analyzer')
    parser.add_argument('--single', action='store_true', 
                       help='Run single quick test instead of full scenarios')
    
    args = parser.parse_args()
    
    if args.single:
        # Quick single test
        result = run_scenario_test('Quick Test', episodes=30, robots=2, steps=2000)
        print(f"\nQuick test result: {result}")
    else:
        # Full scenario testing
        main()