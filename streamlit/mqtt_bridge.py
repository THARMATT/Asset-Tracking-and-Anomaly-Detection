"""Receive ESP32 telemetry over MQTT and update the dashboard CSV files.

Run from this folder:
    python mqtt_bridge.py

ESP32 publishes JSON to:
    <topic-prefix>/<asset_id>/telemetry

Temperature is intentionally generated here in software because the Wokwi
DHT22 was unreliable. The device supplies GPS, speed and battery values.
"""
from __future__ import annotations

import json
import os
import random
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import paho.mqtt.client as mqtt

from asset_tracker import (
    ANOMALY_FIELDS,
    ASSETS,
    GEOFENCE_RADIUS_M,
    LATEST_FIELDS,
    TELEMETRY_FIELDS,
    detect_anomalies,
    evaluate_geofence,
    make_geofence_event,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LATEST_FILE = DATA_DIR / "latest_assets.csv"
TELEMETRY_FILE = DATA_DIR / "telemetry.csv"
ANOMALY_FILE = DATA_DIR / "anomaly_log.csv"

# Public broker is suitable for a classroom demo only. Override with env vars
# to use your own broker. Do not publish private data to a public broker.
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "iot-asset-tracker-demo/change-this-id")
SUBSCRIBE_TOPIC = f"{TOPIC_PREFIX}/+/telemetry"

# Serialize file writes if multiple messages arrive close together.
FILE_LOCK = threading.Lock()
TEMPERATURE_CACHE: dict[str, float] = {}

def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def load_frame(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return pd.DataFrame()

def append_frame(path: Path, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        path, mode="a",
        header=not path.exists() or path.stat().st_size == 0,
        index=False,
    )

def simulate_temperature(asset_id: str) -> float:
    """Generate slowly varying software temperature; no DHT22 required."""
    old = TEMPERATURE_CACHE.get(asset_id, random.uniform(25.0, 31.0))
    new = min(42.0, max(20.0, old + random.uniform(-0.35, 0.45)))
    TEMPERATURE_CACHE[asset_id] = new
    return round(new, 1)

def process_telemetry(payload: dict) -> dict:
    """Validate, enrich, detect anomalies, and persist one ESP32 reading."""
    asset_id = str(payload.get("asset_id", "")).strip()
    asset = next((item for item in ASSETS if item.asset_id == asset_id), None)
    if asset is None:
        raise ValueError(
            f"Unknown asset_id {asset_id!r}. Add it to ASSETS in asset_tracker.py."
        )

    # Accept both the ESP32 field names and common dashboard field aliases.
    latitude = float(payload["latitude"])
    longitude = float(payload["longitude"])
    speed = float(payload.get("speed", payload.get("speed_kmh", 0.0)))
    battery = float(payload.get("battery", payload.get("battery_pct", 100.0)))

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Latitude/longitude are outside valid GPS ranges.")
    if not (0 <= battery <= 100):
        raise ValueError("Battery must be between 0 and 100 percent.")
    if speed < 0:
        raise ValueError("Speed cannot be negative.")

    temperature = simulate_temperature(asset_id)
    timestamp = timestamp_now()
    geofence_status, distance_m = evaluate_geofence(
        asset_id, latitude, longitude, GEOFENCE_RADIUS_M
    )

    reading = {
        "timestamp": timestamp,
        "asset_id": asset_id,
        "asset_type": asset.asset_type,
        "zone": asset.zone,
        "latitude": latitude,
        "longitude": longitude,
        "temperature_c": temperature,
        "battery_pct": battery,
        "speed_kmh": speed,
    }
    sensor_events = detect_anomalies(reading)

    # Only log a geofence event when the asset crosses the boundary, not on
    # every two-second packet while it remains outside.
    previous = load_frame(LATEST_FILE)
    previous_state = "INSIDE"
    if not previous.empty and {"asset_id", "geofence_status"}.issubset(previous.columns):
        match = previous.loc[previous["asset_id"].astype(str) == asset_id]
        if not match.empty and str(match.iloc[-1]["geofence_status"]).upper() in {"INSIDE", "OUTSIDE"}:
            previous_state = str(match.iloc[-1]["geofence_status"]).upper()

    geofence_events = []
    if geofence_status != previous_state:
        event_type = "EXIT" if geofence_status == "OUTSIDE" else "ENTRY"
        geofence_events.append(
            make_geofence_event(reading, distance_m, event_type)
        )

    anomaly_events = sensor_events + (
        [geofence_events[0]] if geofence_status == "OUTSIDE" and geofence_events
        and geofence_events[0]["severity"] == "HIGH" else []
    )
    # Keep the alert active while outside, even after the one-time EXIT event.
    anomaly_count = len(sensor_events) + (1 if geofence_status == "OUTSIDE" else 0)
    status = "ALERT" if anomaly_count else "NORMAL"

    latest_row = {
        **reading,
        "status": status,
        "anomalies": anomaly_count,
        "geofence_status": geofence_status,
        "geofence_distance_m": distance_m,
        "geofence_radius_m": GEOFENCE_RADIUS_M,
        "telemetry_source": "ESP32_MQTT",
    }
    # Keep telemetry.csv on the project's original TELEMETRY_FIELDS schema.
    # Geofence extras live in latest_assets.csv; this avoids corrupting an
    # existing telemetry.csv header created by the built-in simulator.
    telemetry_row = {field: latest_row.get(field, "") for field in TELEMETRY_FIELDS}

    with FILE_LOCK:
        # Keep one latest row per asset while preserving extra dashboard columns.
        latest = load_frame(LATEST_FILE)
        if latest.empty:
            latest = pd.DataFrame(columns=list(dict.fromkeys(
                LATEST_FIELDS + [
                    "geofence_status", "geofence_distance_m",
                    "geofence_radius_m", "telemetry_source",
                ]
            )))
        for column, value in latest_row.items():
            if column not in latest.columns:
                latest[column] = ""
        if "asset_id" not in latest.columns:
            latest["asset_id"] = ""
        latest = latest.loc[latest["asset_id"].astype(str) != asset_id]
        latest = pd.concat([latest, pd.DataFrame([latest_row])], ignore_index=True)
        latest.to_csv(LATEST_FILE, index=False)

        append_frame(TELEMETRY_FILE, pd.DataFrame([telemetry_row]))
        if sensor_events or geofence_events:
            append_frame(
                ANOMALY_FILE,
                pd.DataFrame(sensor_events + geofence_events, columns=ANOMALY_FIELDS),
            )

    print(
        f"{timestamp} | {asset_id} | lat={latitude:.6f}, lon={longitude:.6f} "
        f"| temp={temperature:.1f} C | battery={battery:.0f}% "
        f"| speed={speed:.1f} km/h | geofence={geofence_status} "
        f"({distance_m:.1f} m) | {status}"
    )
    return latest_row

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"Connected to MQTT broker {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(SUBSCRIBE_TOPIC, qos=0)
        print(f"Subscribed: {SUBSCRIBE_TOPIC}")
    else:
        print(f"MQTT connection failed: {reason_code}")

def on_message(client, userdata, message):
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        process_telemetry(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Rejected MQTT message on {message.topic}: {exc}")

def main():
    print("IoT Asset Tracker MQTT bridge")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"Topic:  {SUBSCRIBE_TOPIC}")
    print("Temperature source: Python backend simulation (DHT22 not used)")
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"asset-tracker-bridge-{random.randrange(100000, 999999)}",
    )
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopping MQTT bridge...")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
