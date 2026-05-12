"""
Workaround for flwr CLI / typer 0.15.x incompatibility.

Usage:
  python run_fl.py                   # local simulation (default)
  python run_fl.py distributed       # distributed SuperLink
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flwr.cli.run.run import run

federation = sys.argv[1] if len(sys.argv) > 1 else "local-simulation"
run(app='.', superlink=federation)
