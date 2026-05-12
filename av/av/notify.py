"""
GIDS notification layer — MQTT publish + optional FCM push.

Topics:
  gids/status       — round completion (loss, accuracy); retained
  gids/attack       — attack detected on a client
  gids/update_needed — FL update available (future cloud use); retained

Set GIDS_MQTT_HOST / GIDS_MQTT_PORT env vars to override broker address.
Set GIDS_FCM_CREDS to a path for a Firebase service-account JSON file to
enable FCM push (leave unset to skip FCM without errors).
"""

import json
import os

import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("GIDS_MQTT_HOST", "192.168.1.23")
BROKER_PORT = int(os.environ.get("GIDS_MQTT_PORT", "1883"))
_FCM_CREDS  = os.environ.get("GIDS_FCM_CREDS", "")

_mqtt_client = None


# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------

def _get_mqtt() -> mqtt.Client | None:
    global _mqtt_client
    if _mqtt_client is not None:
        return _mqtt_client
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gids-notify")
    try:
        c.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        c.loop_start()
        _mqtt_client = c
    except Exception as exc:
        print(f"[MQTT] Cannot connect to {BROKER_HOST}:{BROKER_PORT} — {exc}")
    return _mqtt_client


def _publish(topic: str, payload: dict, retain: bool = False) -> None:
    c = _get_mqtt()
    if c:
        c.publish(topic, json.dumps(payload), qos=1, retain=retain)


# ---------------------------------------------------------------------------
# FCM (optional)
# ---------------------------------------------------------------------------

_fcm_app = None

def _get_fcm_app():
    global _fcm_app
    if _fcm_app is not None:
        return _fcm_app
    if not _FCM_CREDS:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(_FCM_CREDS)
        _fcm_app = firebase_admin.initialize_app(cred)
    except Exception as exc:
        print(f"[FCM] Init failed — {exc}")
    return _fcm_app


def _send_fcm(title: str, body: str, topic: str = "gids_alerts") -> None:
    app = _get_fcm_app()
    if app is None:
        return
    try:
        from firebase_admin import messaging
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            topic=topic,
        )
        messaging.send(msg)
    except Exception as exc:
        print(f"[FCM] Send failed — {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def publish_round_status(server_round: int, loss: float, accuracy: float) -> None:
    """Published by server after each round evaluation."""
    _publish("gids/status", {
        "type":     "status",
        "round":    server_round,
        "loss":     round(loss, 4),
        "accuracy": round(accuracy * 100, 2),
    }, retain=True)
    print(f"[MQTT] gids/status  round={server_round}  acc={accuracy*100:.1f}%")


def publish_attack(client_id: int, dataset: str, attack_pct: float, server_round: int) -> None:
    """Published by a client when its test set shows a high attack rate."""
    _publish("gids/attack", {
        "type":       "attack",
        "client_id":  client_id,
        "dataset":    dataset,
        "attack_pct": round(attack_pct * 100, 1),
        "round":      server_round,
    })
    _send_fcm(
        title=f"CAN Attack Detected ({dataset})",
        body=f"Client {client_id} ({dataset}): {attack_pct*100:.1f}% of samples flagged as attacks.",
    )
    print(f"[MQTT] gids/attack  client={client_id}  dataset={dataset}  pct={attack_pct*100:.1f}%")


def publish_update_needed(version: str = "") -> None:
    """Published when a new federated model is ready for deployment."""
    _publish("gids/update_needed", {"type": "update_needed", "version": version}, retain=True)
    _send_fcm(
        title="IDS Update Available",
        body="A new federated model is ready. Connect to Wi-Fi to update.",
    )
    print("[MQTT] gids/update_needed")


def close() -> None:
    global _mqtt_client
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
