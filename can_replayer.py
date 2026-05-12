#!/usr/bin/env python3
"""
GIDS CAN Bus Replayer  —  runs on the Attacker Pi (192.168.1.151)
Reads attack CSV datasets and publishes frames to the MQTT broker
as if they were coming from a live CAN bus.

Usage:
  python3 can_replayer.py --dataset DoS
  python3 can_replayer.py --dataset all --speed 100 --loop
  python3 can_replayer.py --dataset Fuzzy --broker 192.168.1.23

Topics published:
  gids/can_frames   — one JSON message per CAN frame
"""

import argparse
import json
import os
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


def replay(df: pd.DataFrame, mqc: mqtt.Client, topic: str,
           speed: float, name: str) -> None:
    df = df.reset_index(drop=True)
    n  = len(df)
    ts = pd.to_numeric(df["Timestamp"], errors="coerce").fillna(0.0).values

    t_wall0 = time.time()
    t_data0 = float(ts[0])

    print(f"\n[{name}] Replaying {n:,} frames at {speed}x speed  "
          f"(estimated {n / speed / 1e3:.0f}s at original rate)")

    for i in range(n):
        # ── timing ──────────────────────────────────────────────────────────
        data_elapsed = float(ts[i]) - t_data0
        wall_elapsed = time.time() - t_wall0
        wait = (data_elapsed / speed) - wall_elapsed
        if wait > 0.001:
            time.sleep(wait)

        # ── build payload ────────────────────────────────────────────────────
        row = df.iloc[i]
        data_bytes = []
        for col in ["DATA0","DATA1","DATA2","DATA3","DATA4","DATA5","DATA6","DATA7"]:
            try:
                data_bytes.append(int(row[col]))
            except (ValueError, TypeError):
                data_bytes.append(0)

        msg = json.dumps({
            "ts":      float(ts[i]),
            "id":      str(row["CAN_ID"]).strip(),
            "dlc":     int(row["DLC"]) if pd.notna(row["DLC"]) else 8,
            "data":    data_bytes,
            "flag":    str(row["Flag"]).strip().upper(),
            "dataset": name,
        })
        mqc.publish(topic, msg, qos=0)

        if i % 10_000 == 0 and i > 0:
            pct = i / n * 100
            fps = i / max(time.time() - t_wall0, 0.001)
            print(f"  [{name}] {pct:5.1f}%  {i:>7,}/{n:,}  {fps:,.0f} frames/s")

    print(f"  [{name}] Done.")


def main() -> None:
    ap = argparse.ArgumentParser(description="GIDS CAN Bus Replayer")
    ap.add_argument("--dataset",  default="DoS",
                    choices=list(DATASETS) + ["all"],
                    help="Attack dataset to replay (default: DoS)")
    ap.add_argument("--broker",   default="192.168.1.23",
                    help="MQTT broker IP (default: 192.168.1.23)")
    ap.add_argument("--port",     type=int, default=1883)
    ap.add_argument("--topic",    default="gids/can_frames")
    ap.add_argument("--speed",    type=float, default=50.0,
                    help="Replay speed multiplier (default: 50x real-time)")
    ap.add_argument("--data-dir", default=os.path.expanduser("~/gids-fl/gp"),
                    help="Directory containing the CSV files")
    ap.add_argument("--loop",     action="store_true",
                    help="Loop continuously until Ctrl-C")
    args = ap.parse_args()

    # ── MQTT ─────────────────────────────────────────────────────────────────
    mqc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gids-replayer")
    mqc.connect(args.broker, args.port, keepalive=60)
    mqc.loop_start()
    print(f"Connected to MQTT broker {args.broker}:{args.port}")
    print(f"Publishing to topic: {args.topic}")

    datasets = list(DATASETS) if args.dataset == "all" else [args.dataset]

    try:
        while True:
            for name in datasets:
                df = load_csv(name, args.data_dir)
                replay(df, mqc, args.topic, args.speed, name)
            if not args.loop:
                break
            print("\nLooping...\n")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        mqc.loop_stop()
        mqc.disconnect()


if __name__ == "__main__":
    main()
