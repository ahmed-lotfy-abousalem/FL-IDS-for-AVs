# ============================================================
# run_local.ps1  —  Run from d:\GP\av\
# Runs full FL training in local simulation (no Pi needed).
# All 4 clients run on this machine.
#
# Usage:
#   .\run_local.ps1           # 15 rounds (default)
#   .\run_local.ps1 -Rounds 10
#   .\run_local.ps1 -Rounds 20
# ============================================================

param(
    [int]$Rounds = 40
)

Write-Host "Activating virtual environment..."
& "d:\GP\fl_env\Scripts\Activate.ps1"

$env:GIDS_DATA_DIR   = "d:\GP\gp\can_processed"
$env:GIDS_NUM_ROUNDS = "$Rounds"
$env:GIDS_FCM_CREDS  = "d:\GP\gids_fcm_key.json"

Write-Host ""
Write-Host "Starting local FL training"
Write-Host "  Rounds   : $Rounds"
Write-Host "  Data dir : $env:GIDS_DATA_DIR"
Write-Host "  Weights  -> d:\GP\gp\saved_model\gids_weights.pkl"
Write-Host ""
Write-Host "Pre-training will run first (~5-10 min), then $Rounds FL rounds."
Write-Host ""

Set-Location "$PSScriptRoot"
python run_fl.py local-simulation
