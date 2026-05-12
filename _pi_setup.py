"""
One-shot setup script for both Raspberry Pis.

Client Pi  192.168.1.150  — receives can_inference.py, creates saved_model dir,
                               verifies paho-mqtt is in the FL venv.
Attacker Pi 192.168.1.151 — receives can_replayer.py + 4 attack CSVs,
                               creates a lean venv with paho-mqtt/pandas/numpy.
"""

import io
import os
import stat
import sys
import threading
import time
import paramiko

# ---------------------------------------------------------------------------
CLIENT_HOST  = "192.168.1.150"
ATTACKER_HOST = "192.168.1.151"
USER     = "ids"
PASSWORD = "ids"

SCRIPTS_DIR = r"d:\GP"
GP_DIR      = r"d:\GP\gp"
CSV_FILES   = [
    "DoS_dataset.csv",
    "Fuzzy_dataset.csv",
    "RPM_dataset.csv",
    "gear_dataset.csv",
]
# ---------------------------------------------------------------------------


def banner(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def ssh_connect(host: str) -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, username=USER, password=PASSWORD, timeout=30)
    print(f"[{host}] SSH connected")
    return c


def run(ssh: paramiko.SSHClient, cmd: str, host: str) -> str:
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=300)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    if out:
        for line in out.splitlines():
            print(f"  [{host}] {line}")
    if err and exit_code != 0:
        for line in err.splitlines():
            print(f"  [{host}] ERR: {line}")
    return out


def put_file(sftp: paramiko.SFTPClient, local_path: str, remote_path: str, host: str) -> None:
    size_mb = os.path.getsize(local_path) / 1_048_576
    label   = os.path.basename(local_path)
    print(f"  [{host}] Uploading {label}  ({size_mb:.1f} MB) -> {remote_path}")
    sftp.put(local_path, remote_path)
    print(f"  [{host}] OK: {label}")


def makedirs_sftp(sftp: paramiko.SFTPClient, path: str, host: str) -> None:
    parts = path.lstrip("/").split("/")
    cur   = ""
    for p in parts:
        cur = f"{cur}/{p}"
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)
            print(f"  [{host}] mkdir {cur}")


# ---------------------------------------------------------------------------
# Client Pi setup
# ---------------------------------------------------------------------------

def setup_client_pi() -> None:
    host = CLIENT_HOST
    banner(f"Setting up CLIENT Pi  ({host})")

    ssh  = ssh_connect(host)
    sftp = ssh.open_sftp()

    # Directories
    run(ssh, "mkdir -p ~/gids-fl/gp/saved_model", host)

    # Copy can_inference.py
    put_file(sftp, os.path.join(SCRIPTS_DIR, "can_inference.py"),
             "/home/ids/gids-fl/can_inference.py", host)

    # Ensure paho-mqtt is in the FL venv
    print(f"  [{host}] Checking paho-mqtt in fl_env …")
    out = run(ssh, "~/gids-fl/fl_env/bin/pip show paho-mqtt 2>&1 | head -2", host)
    if "Name: paho-mqtt" not in out:
        print(f"  [{host}] Installing paho-mqtt …")
        run(ssh, "~/gids-fl/fl_env/bin/pip install --quiet paho-mqtt", host)
    else:
        print(f"  [{host}] paho-mqtt already present")

    # Quick smoke-test: can we import keras and paho from the venv?
    smoke = run(ssh,
        "~/gids-fl/fl_env/bin/python -c "
        "\"import keras, paho.mqtt.client; print('imports OK')\"",
        host)
    if "imports OK" not in smoke:
        print(f"  [{host}] WARNING: keras/paho import test failed — check venv")

    # chmod +x
    sftp.chmod("/home/ids/gids-fl/can_inference.py", stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)

    sftp.close()
    ssh.close()
    banner(f"CLIENT Pi ({host}) — DONE")


# ---------------------------------------------------------------------------
# Attacker Pi setup
# ---------------------------------------------------------------------------

def setup_attacker_pi() -> None:
    host = ATTACKER_HOST
    banner(f"Setting up ATTACKER Pi  ({host})")

    ssh  = ssh_connect(host)
    sftp = ssh.open_sftp()

    # Directories
    run(ssh, "mkdir -p ~/gids-fl/gp", host)

    # Copy can_replayer.py
    put_file(sftp, os.path.join(SCRIPTS_DIR, "can_replayer.py"),
             "/home/ids/gids-fl/can_replayer.py", host)

    # Copy CSVs
    print(f"\n  [{host}] Uploading attack datasets …")
    for csv in CSV_FILES:
        local = os.path.join(GP_DIR, csv)
        if not os.path.exists(local):
            print(f"  [{host}] SKIP: {local} not found locally")
            continue
        put_file(sftp, local, f"/home/ids/gids-fl/gp/{csv}", host)

    # Create lean venv if it doesn't exist
    venv_check = run(ssh, "test -f ~/gids-fl/fl_env/bin/activate && echo exists || echo missing", host)
    if "missing" in venv_check:
        print(f"  [{host}] Creating venv …")
        run(ssh, "python3 -m venv ~/gids-fl/fl_env", host)

    # Install required packages (no TF/keras needed on attacker)
    print(f"  [{host}] Installing paho-mqtt pandas numpy …")
    run(ssh,
        "~/gids-fl/fl_env/bin/pip install --quiet --upgrade paho-mqtt pandas numpy",
        host)

    # Smoke test
    smoke = run(ssh,
        "~/gids-fl/fl_env/bin/python -c "
        "\"import paho.mqtt.client, pandas, numpy; print('imports OK')\"",
        host)
    if "imports OK" not in smoke:
        print(f"  [{host}] WARNING: import test failed — check venv")

    # chmod +x
    sftp.chmod("/home/ids/gids-fl/can_replayer.py", stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)

    sftp.close()
    ssh.close()
    banner(f"ATTACKER Pi ({host}) — DONE")


# ---------------------------------------------------------------------------
# Run both in parallel
# ---------------------------------------------------------------------------

errors = []

def _safe(fn):
    try:
        fn()
    except Exception as e:
        errors.append(f"{fn.__name__}: {e}")
        print(f"\nERROR in {fn.__name__}: {e}")

t_client   = threading.Thread(target=_safe, args=(setup_client_pi,),   daemon=True)
t_attacker = threading.Thread(target=_safe, args=(setup_attacker_pi,), daemon=True)

t_client.start()
t_attacker.start()
t_client.join()
t_attacker.join()

if errors:
    print("\n\nSome steps FAILED:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n\nAll Pi setup steps completed successfully.")
    print("\nNext steps:")
    print("  1. Run FL training: cd av && flwr run . distributed")
    print("  2. After round 3 completes, copy weights:")
    print("       scp d:/GP/gp/saved_model/gids_weights.pkl ids@192.168.1.150:~/gids-fl/gp/saved_model/")
    print("  3. Client Pi:   ~/gids-fl/fl_env/bin/python ~/gids-fl/can_inference.py")
    print("  4. Attacker Pi: ~/gids-fl/fl_env/bin/python ~/gids-fl/can_replayer.py --dataset DoS --speed 50 --loop")
