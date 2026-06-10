#!/usr/bin/env python3
"""
GIDS CAN Bus Replayer  —  runs on the Attacker Pi (192.168.1.151)
Reads attack CSV datasets and sends frames either via MQTT or directly
over the MCP2515 CAN bus interface.

Usage:
  python3 can_replayer.py --dataset DoS                          # MQTT (default)
  python3 can_replayer.py --dataset DoS --interface can          # real CAN bus
  python3 can_replayer.py --dataset all --speed 100 --loop
  python3 can_replayer.py --dataset Fuzzy --broker 192.168.1.23

Topics published (MQTT mode):
  gids/can_frames   — one JSON message per CAN frame
"""

import argparse
import json
import os
import socket
import struct
import time

import pandas as pd
import paho.mqtt.client as mqtt

DATASETS = {
    "DoS":   "DoS_dataset.csv",
    "Fuzzy": "Fuzzy_dataset.csv",
    "RPM":   "RPM_dataset.csv",
    "gear":  "gear_dataset.csv",
}

COLUMNS = [
    "Timestamp", "CAN_ID", "DLC",
    "DATA0", "DATA1", "DATA2", "DATA3",
    "DATA4", "DATA5", "DATA6", "DATA7",
    "Flag",
]

CAN_FRAME_FMT = "=IB3x8s"


def load_csv(name: str, data_dir: str) -> pd.DataFrame:
    path = os.path.join(data_dir, DATASETS[name])
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found — copy CSVs to {data_dir}")
    print(f"  Loading {name} from {path} ...")
    df = pd.read_csv(path, header=None, names=COLUMNS, low_memory=False)
    print(f"  {len(df):,} frames  "
          f"(attack={(df['Flag'].astype(str).str.strip().str.upper() == 'T').sum():,}  "
          f"normal={(df['Flag'].astype(str).str.strip().str.upper() == 'R').sum():,})")
    return df


def replay(df: pd.DataFrame, sender, speed: float, name: str) -> None:
    df = df.reset_index(drop=True)
    n  = len(df)
    ts = pd.to_numeric(df["Timestamp"], errors="coerce").fillna(0.0).values

    t_wall0 = time.time()
    t_data0 = float(ts[0])

    print(f"\n[{name}] Replaying {n:,} frames at {speed}x speed")

    for i in range(n):
        data_elapsed = float(ts[i]) - t_data0
        wall_elapsed = time.time() - t_wall0
        wait = (data_elapsed / speed) - wall_elapsed
        if wait > 0.001:
            time.sleep(wait)

        row = df.iloc[i]
        data_bytes = []
        for col in ["DATA0","DATA1","DATA2","DATA3","DATA4","DATA5","DATA6","DATA7"]:
            try:
                data_bytes.append(int(row[col]))
            except (ValueError, TypeError):
                data_bytes.append(0)

        frame = {
            "ts":      float(ts[i]),
            "id":      str(row["CAN_ID"]).strip(),
            "dlc":     int(row["DLC"]) if pd.notna(row["DLC"]) else 8,
            "data":    data_bytes,
            "flag":    str(row["Flag"]).strip().upper(),
            "dataset": name,
        }
        sender(frame)

        if i % 10_000 == 0 and i > 0:
            pct = i / n * 100
            fps = i / max(time.time() - t_wall0, 0.001)
            print(f"  [{name}] {pct:5.1f}%  {i:>7,}/{n:,}  {fps:,.0f} frames/s")

    print(f"  [{name}] Done.")


def make_mqtt_sender(broker: str, port: int, topic: str):
    mqc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gids-replayer")
    mqc.connect(broker, port, keepalive=60)
    mqc.loop_start()
    print(f"Connected to MQTT broker {broker}:{port}")
    print(f"Publishing to topic: {topic}")

    def send(frame: dict):
        mqc.publish(topic, json.dumps(frame), qos=0)

    return send, mqc


def make_can_sender(iface: str):
    sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    sock.bind((iface,))
    print(f"Sending CAN frames on {iface}")

    def send(frame: dict):
        id_str = str(frame.get("id", "0")).strip()
        try:
            can_id = int(id_str, 16)
        except ValueError:
            try:
                can_id = int(id_str)
            except ValueError:
                can_id = 0
        can_id &= 0x7FF
        dlc = min(int(frame.get("dlc", 8)), 8)
        data_list = frame.get("data", [])
        data_b = bytes([int(b) & 0xFF for b in data_list[:dlc]])
        data_b += b'\x00' * (8 - len(data_b))
        raw = struct.pack(CAN_FRAME_FMT, can_id, dlc, data_b)
        try:
            sock.send(raw)
        except OSError:
            pass  # drop frame on bus error

    return send, sock


def main() -> None:
    ap = argparse.ArgumentParser(description="GIDS CAN Bus Replayer")
    ap.add_argument("--dataset",   default="DoS",
                    choices=list(DATASETS) + ["all"],
                    help="Attack dataset to replay (default: DoS)")
    ap.add_argument("--interface", default="mqtt", choices=["mqtt", "can"],
                    help="Transport: 'mqtt' (default) or 'can' (MCP2515 hardware)")
    ap.add_argument("--iface",     default="can0",
                    help="CAN interface name (default: can0)")
    ap.add_argument("--broker",    default="192.168.1.23")
    ap.add_argument("--port",      type=int, default=1883)
    ap.add_argument("--topic",     default="gids/can_frames")
    ap.add_argument("--speed",     type=float, default=None,
                    help="Replay speed multiplier (default: 1x for can, 50x for mqtt)")
    ap.add_argument("--data-dir",  default=os.path.expanduser("~/gids-fl/gp"),
                    help="Directory containing the CSV files")
    ap.add_argument("--loop",      action="store_true",
                    help="Loop continuously until Ctrl-C")
    args = ap.parse_args()

    if args.speed is None:
        args.speed = 1.0 if args.interface == "can" else 50.0

    if args.interface == "can":
        sender, resource = make_can_sender(args.iface)
        # MQTT client for publishing dataset label only (no frame transport)
        mqc_meta = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gids-replayer-meta")
        try:
            mqc_meta.connect(args.broker, args.port, keepalive=60)
            mqc_meta.loop_start()
            print(f"Metadata MQTT connected to {args.broker}:{args.port}")
        except Exception as e:
            print(f"Warning: metadata MQTT unavailable ({e}) — attack type won't show in app")
            mqc_meta = None
    else:
        sender, resource = make_mqtt_sender(args.broker, args.port, args.topic)
        mqc_meta = None

    datasets = list(DATASETS) if args.dataset == "all" else [args.dataset]

    try:
        while True:
            for name in datasets:
                if mqc_meta:
                    mqc_meta.publish("gids/dataset", name, qos=1, retain=True)
                df = load_csv(name, args.data_dir)
                replay(df, sender, args.speed, name)
            if not args.loop:
                break
            print("\nLooping...\n")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if mqc_meta:
            mqc_meta.loop_stop()
            mqc_meta.disconnect()
        if hasattr(resource, 'loop_stop'):
            resource.loop_stop()
            resource.disconnect()
        else:
            resource.close()


if __name__ == "__main__":
    main()
