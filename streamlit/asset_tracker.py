"""Software-only IoT asset tracking and anomaly detection prototype.

Uses only Python's standard library. Generates simulated telemetry, detects
rule-based anomalies, and writes CSV files for later dashboard integration.
"""
from __future__ import annotations

import argparse
import csv
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Asset:
    asset_id: str
    asset_type: str
    zone: str
    latitude: float
    longitude: float


ASSETS: tuple[Asset, ...] = (
    Asset("AST-001", "Delivery Van", "Warehouse A", 28.6139, 77.2090),
    Asset("AST-002", "Forklift", "Warehouse A", 28.6145, 77.2101),
    Asset("AST-003", "Delivery Van", "Sector 10", 28.6200, 77.2150),
    Asset("AST-004", "Cold Storage Unit", "Warehouse B", 28.6250, 77.2200),
    Asset("AST-005", "Generator", "Warehouse B", 28.6260, 77.2180),
    Asset("AST-006", "Delivery Truck", "Sector 12", 28.6310, 77.2250),
    Asset("AST-007", "Forklift", "Warehouse C", 28.6350, 77.2300),
    Asset("AST-008", "Cold Storage Unit", "Warehouse C", 28.6370, 77.2320),
    # Dedicated Wokwi ESP32 asset; the ID and home coordinates match main.cpp.
    Asset("ASSET_001", "ESP32 Demo Asset", "Delhi Demo Zone", 28.613909, 77.209015),
)

TELEMETRY_FIELDS = [
    "timestamp", "asset_id", "asset_type", "zone", "latitude", "longitude",
    "temperature_c", "battery_pct", "speed_kmh", "status", "anomalies",
]
ANOMALY_FIELDS = [
    "timestamp", "asset_id", "zone", "metric", "observed_value", "threshold", "severity", "message",
]
LATEST_FIELDS = [
    "timestamp", "asset_id", "asset_type", "zone", "latitude", "longitude",
    "temperature_c", "battery_pct", "speed_kmh", "status", "anomalies",
]

# Simple rules are intentionally transparent and easy to explain in a viva.
GEOFENCE_RADIUS_M = 150.0

THRESHOLDS = {
    "temperature_high_c": 45.0,
    "temperature_low_c": -5.0,
    "battery_low_pct": 15.0,
    "speed_high_kmh": 80.0,
}


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp, including the UTC offset."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def generate_reading(asset: Asset, rng: random.Random, timestamp: str,
                     force_anomaly: bool = False) -> dict:
    """Create one plausible simulated telemetry record for an asset."""
    # Tiny coordinate changes make movement visible while keeping the demo local.
    latitude = round(asset.latitude + rng.uniform(-0.002, 0.002), 6)
    longitude = round(asset.longitude + rng.uniform(-0.002, 0.002), 6)
    temperature = round(rng.uniform(18.0, 38.0), 1)
    battery = round(rng.uniform(25.0, 100.0), 1)
    speed = round(rng.uniform(0.0, 65.0), 1)

    # Deliberately inject known abnormal values during the first demo cycle so
    # users can verify the detection logic without waiting for random events.
    if force_anomaly:
        slot = int(asset.asset_id[-1]) % 4
        if slot == 1:
            temperature = 58.0
        elif slot == 2:
            battery = 8.0
        elif slot == 3:
            speed = 105.0
        elif slot == 0:
            temperature = -9.0

    return {
        "timestamp": timestamp,
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "zone": asset.zone,
        "latitude": latitude,
        "longitude": longitude,
        "temperature_c": temperature,
        "battery_pct": battery,
        "speed_kmh": speed,
    }


def calculate_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates in metres."""
    from math import asin, cos, radians, sin, sqrt

    earth_radius_m = 6_371_000.0
    lat1_rad, lat2_rad = radians(float(lat1)), radians(float(lat2))
    dlat = lat2_rad - lat1_rad
    dlon = radians(float(lon2)) - radians(float(lon1))
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    # Clamp against tiny floating-point overshoots near the antipodes.
    a = min(1.0, max(0.0, a))
    return 2 * earth_radius_m * asin(sqrt(a))


def evaluate_geofence(asset_id: str, latitude: float, longitude: float,
                      radius_m: float = GEOFENCE_RADIUS_M) -> tuple[str, float]:
    """Return (INSIDE/OUTSIDE, distance_m) relative to this asset's home location."""
    asset = next((item for item in ASSETS if item.asset_id == asset_id), None)
    if asset is None:
        raise ValueError(f"Unknown asset ID: {asset_id}")
    if radius_m <= 0:
        raise ValueError("Geofence radius must be positive")
    distance = calculate_distance_m(latitude, longitude, asset.latitude, asset.longitude)
    return ("INSIDE" if distance <= radius_m else "OUTSIDE", round(distance, 1))


def make_geofence_event(reading: dict, distance_m: float, event_type: str) -> dict:
    """Build a log entry for a geofence exit or re-entry transition."""
    if event_type == "EXIT":
        severity = "HIGH"
        message = "Asset moved outside its permitted geofence boundary"
    elif event_type == "ENTRY":
        severity = "INFO"
        message = "Asset returned inside its permitted geofence boundary"
    else:
        raise ValueError("event_type must be 'EXIT' or 'ENTRY'")
    return {
        "timestamp": reading["timestamp"],
        "asset_id": reading["asset_id"],
        "zone": reading.get("zone", "Unknown"),
        "metric": "geofence_distance_m",
        "observed_value": round(float(distance_m), 1),
        "threshold": GEOFENCE_RADIUS_M,
        "severity": severity,
        "message": message,
    }


def detect_anomalies(reading: dict) -> list[dict]:
    """Return zero or more anomaly events for a telemetry reading."""
    events: list[dict] = []
    temperature = float(reading["temperature_c"])
    battery = float(reading["battery_pct"])
    speed = float(reading["speed_kmh"])

    def add(metric: str, value: float, threshold: float, severity: str, message: str) -> None:
        events.append({
            "timestamp": reading["timestamp"],
            "asset_id": reading["asset_id"],
            "zone": reading["zone"],
            "metric": metric,
            "observed_value": value,
            "threshold": threshold,
            "severity": severity,
            "message": message,
        })

    if temperature > THRESHOLDS["temperature_high_c"]:
        add("temperature_c", temperature, THRESHOLDS["temperature_high_c"], "HIGH",
            "Temperature is above the safe upper limit")
    if temperature < THRESHOLDS["temperature_low_c"]:
        add("temperature_c", temperature, THRESHOLDS["temperature_low_c"], "HIGH",
            "Temperature is below the safe lower limit")
    if battery < THRESHOLDS["battery_low_pct"]:
        add("battery_pct", battery, THRESHOLDS["battery_low_pct"], "MEDIUM",
            "Battery level is critically low")
    if speed > THRESHOLDS["speed_high_kmh"]:
        add("speed_kmh", speed, THRESHOLDS["speed_high_kmh"], "HIGH",
            "Speed is above the configured limit")
    return events


def _append_csv(path: Path, fields: list[str], rows: Iterable[dict]) -> None:
    """Append rows and create the CSV header if the file is new or empty."""
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        writer.writerows(rows)


def _write_latest(path: Path, fields: list[str], rows: list[dict]) -> None:
    """Replace the snapshot file with the most recent reading per asset."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_simulation(iterations: int = 10, interval: float = 1.0,
                   output_dir: str | Path = "data", seed: int | None = None,
                   demo_anomalies: bool = True) -> dict:
    """Run the simulator and return a summary useful for tests and scripts."""
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if interval < 0:
        raise ValueError("interval cannot be negative")

    rng = random.Random(seed)
    out = Path(output_dir)
    telemetry_path = out / "telemetry.csv"
    anomalies_path = out / "anomaly_log.csv"
    latest_path = out / "latest_assets.csv"
    latest_by_id: dict[str, dict] = {}
    total_readings = 0
    total_anomalies = 0

    print(f"Starting simulation: {len(ASSETS)} assets, {iterations} cycle(s)")
    print(f"Output folder: {out.resolve()}")
    for cycle in range(iterations):
        timestamp = utc_timestamp()
        cycle_readings: list[dict] = []
        cycle_events: list[dict] = []
        for asset in ASSETS:
            reading = generate_reading(
                asset, rng, timestamp,
                force_anomaly=(demo_anomalies and cycle == 0),
            )
            events = detect_anomalies(reading)
            reading["anomalies"] = len(events)
            reading["status"] = "ALERT" if events else "NORMAL"
            cycle_readings.append(reading)
            cycle_events.extend(events)
            latest_by_id[asset.asset_id] = reading

        _append_csv(telemetry_path, TELEMETRY_FIELDS, cycle_readings)
        _append_csv(anomalies_path, ANOMALY_FIELDS, cycle_events)
        _write_latest(latest_path, LATEST_FIELDS,
                      [latest_by_id[key] for key in sorted(latest_by_id)])
        total_readings += len(cycle_readings)
        total_anomalies += len(cycle_events)
        print(f"Cycle {cycle + 1}/{iterations}: {len(cycle_readings)} readings, "
              f"{len(cycle_events)} anomaly event(s)")
        if cycle < iterations - 1 and interval > 0:
            time.sleep(interval)

    summary = {
        "assets": len(ASSETS),
        "iterations": iterations,
        "readings_written_this_run": total_readings,
        "anomalies_detected_this_run": total_anomalies,
        "telemetry_csv": str(telemetry_path),
        "anomaly_log_csv": str(anomalies_path),
        "latest_assets_csv": str(latest_path),
    }
    print("\nSimulation complete.")
    print(f"Readings generated: {total_readings}")
    print(f"Anomalies detected: {total_anomalies}")
    print(f"Telemetry: {telemetry_path}")
    print(f"Anomaly log: {anomalies_path}")
    print(f"Latest snapshot: {latest_path}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate IoT asset telemetry and detect anomalies.")
    parser.add_argument("--iterations", type=int, default=10,
                        help="number of telemetry cycles (default: 10)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="seconds between cycles (default: 1; use 0 for fast testing)")
    parser.add_argument("--output-dir", default="data",
                        help="folder for CSV output (default: ./data)")
    parser.add_argument("--seed", type=int, default=None,
                        help="optional random seed for reproducible normal readings")
    parser.add_argument("--no-demo-anomalies", action="store_true",
                        help="do not force example anomalies in the first cycle")
    args = parser.parse_args()
    try:
        run_simulation(args.iterations, args.interval, args.output_dir, args.seed,
                       demo_anomalies=not args.no_demo_anomalies)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
