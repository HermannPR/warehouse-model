#!/usr/bin/env python3
"""
Quick test script to verify the updated visualization with external info panel.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from visualize import WarehouseVisualizer
    from warehouse import Warehouse
    print("✓ Successfully imported modules")
    
    # Create a quick test model
    params = {'config_path': 'layout.json'}
    model = Warehouse(parameters=params)
    model.setup()
    model.auto_cycle_reset = True
    print("✓ Model created and initialized")
    
    # Create visualizer with external info panel
    viz = WarehouseVisualizer(model, fps=5)
    print("✓ Visualizer created with external info panel")
    print("  - Map is now on the left side")
    print("  - Information panel is on the right side") 
    print("  - Controls information is displayed at bottom of info panel")
    print("  - Status information is clearly separated from the map")
    
    print("\nStarting visualization...")
    print("Note: The information is now displayed OUTSIDE the map area!")
    
    # Run visualization for a short demo
    viz.run(max_steps=100)
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()