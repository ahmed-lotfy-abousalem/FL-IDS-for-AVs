# ============================================================
# start_broker.ps1  —  Run from d:\GP\av\
# Starts the amqtt MQTT broker on port 1883 (TCP) and 8883 (WebSocket).
# Flutter app and GIDS clients publish/subscribe through this broker.
# ============================================================

Write-Host "Activating virtual environment..."
& "d:\GP\fl_env\Scripts\Activate.ps1"

Write-Host ""
Write-Host "Starting MQTT broker"
Write-Host "  TCP        -> 0.0.0.0:1883  (Pi clients, GIDS notify.py)"
Write-Host "  WebSocket  -> 0.0.0.0:8883  (Flutter app on phone)"
Write-Host ""
Write-Host "Keep this window open. Phone/Pi must reach 192.168.1.23 on these ports."
Write-Host ""

amqtt -c "$PSScriptRoot\mqtt_broker.yaml"
