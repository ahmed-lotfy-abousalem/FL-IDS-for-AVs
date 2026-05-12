"""Stream FL training logs — bypasses flwr CLI typer incompatibility."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flwr.cli.log import _log_with_control_api
from flwr.cli.flower_config import read_superlink_connection

run_id    = int(sys.argv[1]) if len(sys.argv) > 1 else 15183627546183963582
federation = sys.argv[2] if len(sys.argv) > 2 else "local-simulation"

conn = read_superlink_connection(federation)
_log_with_control_api(conn, run_id, stream=True)
