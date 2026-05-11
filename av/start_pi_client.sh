#!/usr/bin/env bash
# ============================================================
# start_pi_client.sh  —  Run ON the Raspberry Pi
#   ssh ids@192.168.137.157
#   cd /home/ids/gids-fl/av
#   bash start_pi_client.sh
#
# Starts Flower SuperNode as Client 3 (Gear dataset).
# GIDS_DATA_DIR tells task.py where to find the .npy files
# regardless of where flwr unpacks the code bundle.
# ============================================================

set -e

SUPERLINK="192.168.137.1:9092"
DATA_DIR="/home/ids/gids-fl/gp/can_processed"
VENV="/home/ids/gids-fl/fl_env/bin/activate"

if [ ! -f "$DATA_DIR/gear_X_train.npy" ]; then
    echo "ERROR: Gear dataset not found at $DATA_DIR"
    echo "Copy from laptop:  scp 'D:\\GP\\gp\\can_processed\\gear_*' ids@192.168.137.157:$DATA_DIR/"
    exit 1
fi

echo "Activating virtual environment..."
source "$VENV"

export GIDS_DATA_DIR="$DATA_DIR"

echo ""
echo "Starting Pi SuperNode — Client 3 (Gear)"
echo "  SuperLink : $SUPERLINK"
echo "  Data dir  : $GIDS_DATA_DIR"
echo ""

flower-supernode \
    --superlink "$SUPERLINK" \
    --node-config "node_id=3" \
    --insecure
