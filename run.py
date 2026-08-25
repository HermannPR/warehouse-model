#!/usr/bin/env python3
"""
Quick run script for the warehouse simulation
"""

import os
import sys
import subprocess
from typing import Callable, Dict

def check_dependencies() -> bool:
    """Check if core dependencies are installed. Print pip hints if missing."""
    required = ("numpy", "agentpy")
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("Dependencias faltantes:")
        for m in missing:
            print(f"  pip install {m}")
        return False
    return True

def _python() -> str:
    return sys.executable or "python"

def _abs(*parts: str) -> str:
    return os.path.join(os.getcwd(), *parts)

def run_subprocess(args):
    try:
        subprocess.run(args, check=False)
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario.")
    except Exception as e:
        print(f"Error ejecutando {' '.join(args)}: {e}")

def main():
    if not os.path.exists('layout.json'):
        print("Error: layout.json not found in current directory")
        return
    
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        return
    
    print("Warehouse Q-Learning Simulation")
    print("=" * 40)
    print("1. Test configuration")
    print("2. Quick training (100 episodes) + charts (select robots)")
    print("3. Full training (1000 episodes) + charts (select robots)")
    print("4. Visualization demo")
    print("5. Test run (no visualization)")
    print("0. Exit")
    print("=" * 40)
    
    choice = input("Select option (1-5): ").strip()
    
    train_py = _abs("train.py")
    metrics_dir = _abs("metrics_out")
    os.makedirs(metrics_dir, exist_ok=True)

    def _prompt_robot_count(default: int) -> str:
        try:
            val = input(f"Number of robots to train with (Enter for default {default}): ").strip()
            if val == "":
                return str(default)
            n = int(val)
            if n <= 0:
                print("Using default.")
                return str(default)
            return str(n)
        except Exception:
            print("Invalid input; using default.")
            return str(default)

    def _train_quick():
        n = _prompt_robot_count(1)
        # Use episodic single-phase training with specified robot count
        run_subprocess([
            _python(), train_py, "train", "--episodes", "100", "--episodic", "--export-metrics", metrics_dir, "--plot",
            "--two-robots" if n == "2" else "--single-robot" if n == "1" else "--episodic"
        ] if n in ("1", "2") else [
            _python(), train_py, "train", "--episodes", "100", "--episodic", "--export-metrics", metrics_dir, "--plot", "--epsilon", "0.3", "--single-robot", "--episodes", "100"
        ])

    def _train_full():
        n = _prompt_robot_count(2)
        if n == "1":
            flags = ["--single-robot"]
        elif n == "2":
            flags = ["--two-robots"]
        else:
            flags = ["--episodic"]  # custom n not directly supported; fallback episodic default
        run_subprocess([
            _python(), train_py, "train", "--episodes", "1000", "--episodic", "--export-metrics", metrics_dir, "--plot", *flags
        ])

    actions: Dict[str, Callable[[], None]] = {
        "1": lambda: run_subprocess([_python(), _abs("test_setup.py")]),
        "2": _train_quick,
        "3": _train_full,
        "4": lambda: (lambda n: run_subprocess([
                _python(), train_py, "visualize", "--steps", "1000", "--fps", "8", "--n-robots", n
            ]))( _prompt_robot_count(2) ),
        "5": lambda: run_subprocess([_python(), train_py, "test", "--steps", "500"]),
        "0": lambda: print("Saliendo..."),
    }

    if choice in actions:
        print()
        actions[choice]()
    else:
        print("Opción inválida")

if __name__ == "__main__":
    main()