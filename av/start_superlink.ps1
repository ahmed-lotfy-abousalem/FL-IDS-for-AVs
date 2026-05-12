# ============================================================
# start_superlink.ps1  —  Run from d:\GP\av\
# Starts the Flower SuperLink on the laptop (192.168.1.23)
#   Port 9091 — ServerAppIo  (internal ServerApp process)
#   Port 9092 — Fleet API    (SuperNodes connect here)
#   Port 9093 — Control API  (flwr run submits app here)
# ============================================================

Write-Host "Activating virtual environment..."
& "d:\GP\fl_env\Scripts\Activate.ps1"

$env:GIDS_DATA_DIR  = "d:\GP\gp\can_processed"
$env:GIDS_FCM_CREDS = "d:\GP\gids_fcm_key.json"
Write-Host "GIDS_DATA_DIR  = $env:GIDS_DATA_DIR"
Write-Host "GIDS_FCM_CREDS = $env:GIDS_FCM_CREDS"

Write-Host ""
Write-Host "Starting Flower SuperLink"
Write-Host "  Fleet API  -> 0.0.0.0:9092  (SuperNodes)"
Write-Host "  Control    -> 0.0.0.0:9093  (flwr run)"
Write-Host ""
Write-Host "Keep this window open. Start laptop clients next."
Write-Host ""

flower-superlink `
    --insecure `
    --fleet-api-address 0.0.0.0:9092 `
    --serverappio-api-address 0.0.0.0:9091 `
    --control-api-address 0.0.0.0:9093
