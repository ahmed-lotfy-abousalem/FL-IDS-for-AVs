# ============================================================
# start_laptop_clients.ps1  —  Run from d:\GP\av\
# Opens 3 new PowerShell windows, one per virtual client.
#   Client 0 -> DoS dataset
#   Client 1 -> Fuzzy dataset
#   Client 2 -> RPM dataset
# SuperLink must already be running before executing this.
# ============================================================

$venv      = "d:\GP\fl_env\Scripts\Activate.ps1"
$superlink = "192.168.1.23:9092"

function Start-SuperNode($nodeId, $label, $clientappioPort) {
    $cmd = "& '$venv'; " +
           "`$env:GIDS_DATA_DIR = 'd:\GP\gp\can_processed'; " +
           "Write-Host 'Client $nodeId ($label) connecting...'; " +
           "flower-supernode " +
           "--superlink $superlink " +
           "--node-config 'node_id=$nodeId' " +
           "--clientappio-api-address 0.0.0.0:$clientappioPort " +
           "--insecure"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd
    Write-Host "Launched Client $nodeId ($label) on clientappio port $clientappioPort"
}

Write-Host "Starting 3 virtual SuperNodes on laptop..."
Start-SuperNode 0 "DoS"   9094
Start-SuperNode 1 "Fuzzy" 9095
Start-SuperNode 2 "RPM"   9096

Write-Host ""
Write-Host "All 3 laptop clients launched."
Write-Host "Next: start Pi client, then run:  flwr run . distributed"
