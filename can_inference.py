#!/usr/bin/env python3
"""
GIDS CAN Inference Engine  —  runs on the Client Pi (192.168.1.150)

Reads CAN frames from the physical MCP2515 bus (--source can, default) or
from MQTT (--source mqtt), builds non-overlapping 29-frame windows (319
features), loads D1+D2 weights, runs GIDS combined detection, and publishes
results to gids/attack and gids/status for the Flutter dashboard.

Usage:
  # Physical CAN bus (MCP2515 on can0) — requires sudo for AF_CAN socket:
  sudo python3 can_inference.py
  sudo python3 can_inference.py --iface can0 --broker 192.168.1.23

  # MQTT source (legacy / no hardware):
  python3 can_inference.py --source mqtt

Topics:
  Subscribe:  gids/can_frames  — (mqtt source only)
  Publish:    gids/attack      — attack detection events  (every REPORT_EVERY windows)
              gids/status      — inference stats for the dashboard
"""

import argparse
import json
import os
import pickle
import socket
import struct
import sys
import time

import numpy as np
import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Constants  (must match the preprocessing used during training)
# ---------------------------------------------------------------------------

WINDOW_SIZE  = 29       # frames per sample
N_FEATURES   = 11       # features per frame: delta_t + can_id + dlc + 8 data bytes
FLAT_DIM     = WINDOW_SIZE * N_FEATURES   # 319

DELTA_T_NORM = 0.005    # normalise inter-frame gap by 5 ms
CAN_ID_MAX   = 2047.0   # 11-bit standard CAN ID
DLC_MAX      = 8.0

REPORT_EVERY     = 50   # publish gids/attack every N complete windows
ATTACK_THRESHOLD = 10.0 # fire gids/attack when rolling attack% exceeds this


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _parse_can_id(id_str: str) -> int:
    try:
        return int(id_str, 16)
    except (ValueError, TypeError):
        pass
    try:
        return int(id_str)
    except (ValueError, TypeError):
        return 0


def extract_window(frames: list) -> np.ndarray:
    """
    Convert WINDOW_SIZE frame dicts → flat float32 array of shape (FLAT_DIM, 1).
    Frame dict: {"ts": float, "id": str, "dlc": int, "data": [8 ints], ...}
    """
    feats = []
    prev_ts = float(frames[0]["ts"])
    for f in frames:
        ts      = float(f["ts"])
        delta_t = (ts - prev_ts) / DELTA_T_NORM
        prev_ts = ts

        can_id = _parse_can_id(str(f.get("id", "0")))
        dlc    = int(f.get("dlc", 8))
        data   = list(f.get("data", []))
        if len(data) < 8:
            data += [0] * (8 - len(data))

        feats += [
            min(max(delta_t, 0.0), 10.0),   # clamp outlier inter-frame gaps
            min(can_id / CAN_ID_MAX, 1.0),
            min(dlc    / DLC_MAX,    1.0),
        ] + [min(b / 255.0, 1.0) for b in data[:8]]

    arr = np.array(feats, dtype=np.float32)   # (FLAT_DIM,)
    return arr.reshape(FLAT_DIM, 1)            # (FLAT_DIM, 1) — channel dim for model


# ---------------------------------------------------------------------------
# Model construction  (mirrors av/av/task.py — no flwr dependency)
# ---------------------------------------------------------------------------

def _build_discriminator(name_prefix: str):
    from keras.layers import Dense, Flatten, Input
    from keras.models import Model

    input_shape = (FLAT_DIM, 1)
    inp = Input(shape=input_shape, name=f"{name_prefix}_input")
    x   = Flatten(name=f"{name_prefix}_flatten")(inp)
    x   = Dense(128, activation="relu",    name=f"{name_prefix}_dense1")(x)
    x   = Dense(64,  activation="relu",    name=f"{name_prefix}_dense2")(x)
    out = Dense(1,   activation="sigmoid", name=f"{name_prefix}_output")(x)
    return Model(inputs=inp, outputs=out, name=name_prefix)


def _default_weights_path() -> str:
    data_dir = os.environ.get("GIDS_DATA_DIR", "")
    if data_dir:
        base = os.path.dirname(data_dir)
    else:
        base = os.path.expanduser("~/gids-fl/gp")
    return os.path.join(base, "saved_model", "gids_weights.pkl")


def load_models(weights_path: str):
    if not os.path.exists(weights_path):
        print(f"[GIDS] ERROR: weights not found at {weights_path}")
        print("       Run FL training first (flwr run . distributed), then:")
        print("       scp d:/GP/gp/saved_model/gids_weights.pkl ids@192.168.1.150:~/gids-fl/gp/saved_model/")
        sys.exit(1)

    d1 = _build_discriminator("d1")
    d2 = _build_discriminator("d2")

    with open(weights_path, "rb") as f:
        w = pickle.load(f)

    d1.set_weights(w["d1"])
    d2.set_weights(w["d2"])
    print(f"[GIDS] Weights loaded — {weights_path}")
    # Warm up Keras graph (avoids first-prediction latency spike)
    dummy = np.zeros((1, FLAT_DIM, 1), dtype=np.float32)
    d1.predict(dummy, verbose=0)
    d2.predict(dummy, verbose=0)
    print("[GIDS] Models ready.")
    return d1, d2


# ---------------------------------------------------------------------------
# Inference engine
# ---------------------------------------------------------------------------

class GidsInference:

    def __init__(self, d1, d2, broker: str, port: int, client_id: int,
                 source: str = "can") -> None:
        self.d1        = d1
        self.d2        = d2
        self.client_id = client_id
        self._source   = source        # "can" or "mqtt"

        self._frame_buf  = []          # accumulate frames until WINDOW_SIZE
        self._X_batch    = []          # accumulate windows until REPORT_EVERY
        self._ds_buf     = []          # dataset label for each pending window
        self._total_wins = 0           # windows processed since start
        self._roll_preds = []          # last REPORT_EVERY * 4 binary predictions

        self._t_start = time.time()

        self._mqc = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="gids-inference",
        )
        self._mqc.on_connect = self._on_connect
        self._mqc.on_message = self._on_frame
        self._mqc.connect(broker, port, keepalive=60)

    # ── MQTT callbacks ────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            if self._source == "mqtt":
                client.subscribe("gids/can_frames", qos=0)
                print("[GIDS] Connected to broker — listening on gids/can_frames")
            else:
                print("[GIDS] Connected to broker (publish-only for CAN source)")
        else:
            print(f"[GIDS] Broker connect error: rc={rc}")

    def _on_frame(self, client, userdata, msg):
        try:
            frame = json.loads(msg.payload)
        except Exception:
            return
        self._process_frame(frame)

    def _process_frame(self, frame: dict) -> None:
        self._frame_buf.append(frame)
        if len(self._frame_buf) < WINDOW_SIZE:
            return

        # Complete window — extract features and queue for batch inference
        X = extract_window(self._frame_buf)          # (319, 1)
        self._X_batch.append(X)
        self._ds_buf.append(str(frame.get("dataset", "live")))
        self._frame_buf = []                          # non-overlapping windows
        self._total_wins += 1

        if len(self._X_batch) >= REPORT_EVERY:
            self._run_inference()

    # ── Batch inference ───────────────────────────────────────────────────

    def _run_inference(self) -> None:
        X = np.stack(self._X_batch, axis=0)          # (N, 319, 1)
        dataset = self._ds_buf[-1]

        d1_prob = self.d1.predict(X, verbose=0).flatten()   # (N,)
        d2_prob = self.d2.predict(X, verbose=0).flatten()

        attacks = ((d1_prob > 0.5) | (d2_prob < 0.5)).astype(int)

        self._roll_preds.extend(attacks.tolist())
        # Keep rolling window at ~4 × REPORT_EVERY for smoothing
        if len(self._roll_preds) > REPORT_EVERY * 4:
            self._roll_preds = self._roll_preds[-REPORT_EVERY * 4:]

        attack_pct = float(np.mean(self._roll_preds)) * 100.0
        elapsed    = time.time() - self._t_start
        fps        = self._total_wins * WINDOW_SIZE / max(elapsed, 1e-3)

        print(
            f"[GIDS] wins={self._total_wins:,}  "
            f"attack={attack_pct:.1f}%  "
            f"dataset={dataset}  "
            f"fps={fps:,.0f}"
        )

        # gids/status — updates dashboard Round/Accuracy/Loss cards
        self._mqc.publish("gids/status", json.dumps({
            "type":     "status",
            "round":    0,
            "loss":     round(float(np.mean(d1_prob)), 4),
            "accuracy": round(100.0 - attack_pct, 2),
        }), qos=1)

        # gids/attack — fires when rolling attack% exceeds threshold
        if attack_pct > ATTACK_THRESHOLD:
            self._mqc.publish("gids/attack", json.dumps({
                "type":       "attack",
                "client_id":  self.client_id,
                "dataset":    dataset,
                "attack_pct": round(attack_pct, 1),
                "round":      0,
            }), qos=1)
            print(f"  → gids/attack published ({attack_pct:.1f}% flagged)")

        self._X_batch = []
        self._ds_buf  = []

    def run(self) -> None:
        print("[GIDS] Inference engine running (MQTT source). Press Ctrl-C to stop.")
        try:
            self._mqc.loop_forever()
        except KeyboardInterrupt:
            print("\n[GIDS] Stopped.")
        finally:
            self._mqc.loop_stop()
            self._mqc.disconnect()

    # ── CAN bus source ────────────────────────────────────────────────────

    _CAN_FMT = "=IB3x8s"   # 16 bytes: can_id (4) + dlc (1) + pad (3) + data (8)

    def run_can(self, iface: str = "can0") -> None:
        sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        sock.bind((iface,))
        self._mqc.loop_start()   # non-blocking: handles publish while we block on recv
        print(f"[GIDS] Reading CAN frames from {iface}. Press Ctrl-C to stop.")
        try:
            while True:
                raw = sock.recv(16)
                can_id_raw, dlc, data = struct.unpack(self._CAN_FMT, raw)
                can_id = can_id_raw & 0x1FFFFFFF   # strip EFF/RTR/ERR flags
                dlc    = min(dlc, 8)
                frame  = {
                    "ts":      time.time(),
                    "id":      format(can_id, 'X'),
                    "dlc":     dlc,
                    "data":    list(data[:dlc]) + [0] * (8 - dlc),
                    "dataset": "live",
                }
                self._process_frame(frame)
        except KeyboardInterrupt:
            print("\n[GIDS] Stopped.")
        finally:
            sock.close()
            self._mqc.loop_stop()
            self._mqc.disconnect()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="GIDS CAN Inference Engine")
    ap.add_argument("--source",    default="can", choices=["can", "mqtt"],
                    help="Frame source: 'can' = MCP2515 bus (default), 'mqtt' = MQTT topic")
    ap.add_argument("--iface",     default="can0",
                    help="CAN interface name when --source can (default: can0)")
    ap.add_argument("--broker",    default=os.environ.get("GIDS_MQTT_HOST", "192.168.1.23"),
                    help="MQTT broker IP (default: 192.168.1.23)")
    ap.add_argument("--port",      type=int,
                    default=int(os.environ.get("GIDS_MQTT_PORT", "1883")))
    ap.add_argument("--weights",   default=_default_weights_path(),
                    help="Path to gids_weights.pkl")
    ap.add_argument("--client-id", type=int, default=3,
                    help="Client ID reported in gids/attack messages (default: 3)")
    args = ap.parse_args()

    print(f"[GIDS] Source:    {args.source}" +
          (f" ({args.iface})" if args.source == "can" else ""))
    print(f"[GIDS] Broker:    {args.broker}:{args.port}")
    print(f"[GIDS] Weights:   {args.weights}")
    print(f"[GIDS] Client ID: {args.client_id}")

    d1, d2 = load_models(args.weights)
    engine = GidsInference(d1, d2, args.broker, args.port, args.client_id,
                           source=args.source)
    if args.source == "can":
        engine.run_can(args.iface)
    else:
        engine.run()


if __name__ == "__main__":
    main()
