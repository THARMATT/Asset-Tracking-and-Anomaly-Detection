"""
Core IoT asset simulator and rule-based anomaly detection.
Ported from the standalone iot_asset_tracker_final subproject and adapted
to write directly into the main project's SQLite database via location_service.

DESIGN CONSTRAINTS:
  - Location / telemetry data is INDEPENDENT of RFID gate-authorization logic.
  - Coordinates are labeled source='simulator'; they are NOT real GPS fixes.
  - The anomaly thresholds here (temperature, battery, speed) are telemetry
    thresholds and do NOT replace the RFID-based anomaly_engine.py.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import atan2, cos, radians, sin
from typing import Any

# ---------------------------------------------------------------------------
# 1. VIRTUAL ASSET REGISTRY
#    Eight simulated IoT assets near New Delhi, India.
#    These are stored in the SQLite 'assets' table under a separate category
#    so they remain distinct from the existing 5 RFID-tracked assets.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IoTAsset:
    asset_id: str
    asset_name: str
    asset_type: str        # human-readable type (Delivery Van, Forklift …)
    zone: str              # logical zone label used for display
    home_lat: float        # starting / home latitude
    home_lon: float        # starting / home longitude


IOT_ASSETS: list[IoTAsset] = [
    IoTAsset("AST-001", "Delivery Van Alpha",   "Delivery Van",   "Warehouse A", 28.6139, 77.2090),
    IoTAsset("AST-002", "Forklift Bravo",       "Forklift",       "Warehouse A", 28.6150, 77.2110),
    IoTAsset("AST-003", "Delivery Van Charlie", "Delivery Van",   "Sector 10",   28.6200, 77.2150),
    IoTAsset("AST-004", "Cold Storage Delta",   "Cold Storage",   "Warehouse B", 28.6250, 77.2050),
    IoTAsset("AST-005", "Generator Echo",       "Generator",      "Warehouse B", 28.6270, 77.2100),
    IoTAsset("AST-006", "Delivery Truck Foxtrot","Delivery Truck","Sector 12",   28.6300, 77.2200),
    IoTAsset("AST-007", "Forklift Golf",        "Forklift",       "Warehouse C", 28.6350, 77.2150),
    IoTAsset("AST-008", "Cold Storage Hotel",   "Cold Storage",   "Warehouse C", 28.6380, 77.2070),
]

# Map asset_id → IoTAsset for fast lookup
IOT_ASSET_MAP: dict[str, IoTAsset] = {a.asset_id: a for a in IOT_ASSETS}

# ---------------------------------------------------------------------------
# 2. ANOMALY THRESHOLDS (telemetry-based, independent of RFID rules)
# ---------------------------------------------------------------------------

THRESHOLDS: dict[str, float] = {
    "temperature_high_c": 45.0,
    "temperature_low_c":  -5.0,
    "battery_low_pct":    15.0,
    "speed_high_kmh":     80.0,
}


# ---------------------------------------------------------------------------
# 3. MOVEMENT ENGINE
#    Each asset orbits slowly around its home coordinate using a deterministic
#    trigonometric model so that positions change gradually rather than jumping.
# ---------------------------------------------------------------------------

def advance_position(asset: IoTAsset, latitude: float, longitude: float,
                     idx: int) -> tuple[float, float]:
    """
    Advance an asset one step along its circular simulated route.
    Identical algorithm to the standalone asset_movement.py.
    """
    lon_scale = max(cos(radians(asset.home_lat)), 0.1)
    x = (float(longitude) - asset.home_lon) * lon_scale
    y = float(latitude)   - asset.home_lat
    angle = atan2(y, x)
    if abs(x) + abs(y) < 0.00005:
        angle = idx * 0.79
    angle += 0.14 if idx % 2 == 0 else -0.14
    radius = 0.0010 + (idx % 4) * 0.00012
    return (
        round(asset.home_lat + radius * sin(angle), 6),
        round(asset.home_lon + (radius * cos(angle)) / lon_scale, 6),
    )


# ---------------------------------------------------------------------------
# 4. TELEMETRY GENERATION
# ---------------------------------------------------------------------------

def generate_reading(
    asset: IoTAsset,
    idx: int,
    current_lat: float,
    current_lon: float,
    rng: random.Random | None = None,
    force_demo_anomaly: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Generate one telemetry reading for an asset at the given position.
    Returns (reading_dict, anomaly_events_list).
    """
    rng = rng or random.Random()

    new_lat, new_lon = advance_position(asset, current_lat, current_lon, idx)

    temperature_c  = round(rng.uniform(18.0, 38.0), 1)
    battery_pct    = round(rng.uniform(25.0, 100.0), 1)
    speed_kmh      = round(rng.uniform(0.0, 65.0), 1)

    # Deterministic demo anomaly: AST-001 gets a high-temperature spike.
    if force_demo_anomaly and asset.asset_id == "AST-001":
        temperature_c = 58.0

    reading: dict[str, Any] = {
        "timestamp":     datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "asset_id":      asset.asset_id,
        "asset_type":    asset.asset_type,
        "zone":          asset.zone,
        "latitude":      new_lat,
        "longitude":     new_lon,
        "temperature_c": temperature_c,
        "battery_pct":   battery_pct,
        "speed_kmh":     speed_kmh,
    }

    anomaly_events = detect_anomalies(reading)
    reading["anomaly_count"] = len(anomaly_events)
    reading["status"] = "ALERT" if anomaly_events else "NORMAL"
    return reading, anomaly_events


def detect_anomalies(reading: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one event dict for every violated threshold rule."""
    events: list[dict[str, Any]] = []
    checks = [
        (float(reading["temperature_c"]) > THRESHOLDS["temperature_high_c"],
         "temperature_c", reading["temperature_c"], THRESHOLDS["temperature_high_c"],
         "HIGH", "Temperature is above the safe operating limit."),
        (float(reading["temperature_c"]) < THRESHOLDS["temperature_low_c"],
         "temperature_c", reading["temperature_c"], THRESHOLDS["temperature_low_c"],
         "HIGH", "Temperature is below the safe operating limit."),
        (float(reading["battery_pct"]) < THRESHOLDS["battery_low_pct"],
         "battery_pct", reading["battery_pct"], THRESHOLDS["battery_low_pct"],
         "MEDIUM", "Battery level is critically low."),
        (float(reading["speed_kmh"]) > THRESHOLDS["speed_high_kmh"],
         "speed_kmh", reading["speed_kmh"], THRESHOLDS["speed_high_kmh"],
         "HIGH", "Asset speed is above the configured limit."),
    ]
    for violated, metric, value, threshold, severity, message in checks:
        if violated:
            events.append({
                "timestamp":      reading["timestamp"],
                "asset_id":       reading["asset_id"],
                "zone":           reading["zone"],
                "metric":         metric,
                "observed_value": value,
                "threshold":      threshold,
                "severity":       severity,
                "message":        message,
            })
    return events
