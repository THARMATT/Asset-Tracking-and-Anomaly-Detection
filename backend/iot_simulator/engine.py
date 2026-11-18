"""
IoT Simulator Engine — background thread that:
  1. Seeds the 8 IoT virtual assets into the main project's SQLite 'assets' table
     (only on first run; uses INSERT OR IGNORE so existing records are safe).
  2. Advances each asset's position on every tick (default 5 s).
  3. Calls location_service.insert_location() to persist telemetry.
  4. Keeps current positions in memory so the map always has latest data.
  5. Can be started / paused / stopped via the Flask API.

Thread-safety: all shared state is protected by _lock (threading.Lock).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from iot_simulator.asset_tracker import (
    IOT_ASSETS,
    IOT_ASSET_MAP,
    generate_reading,
    detect_anomalies,
    THRESHOLDS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# INTERNAL STATE
# ---------------------------------------------------------------------------
_lock = threading.Lock()

# Positions dict: asset_id -> (lat, lon)
_positions: Dict[str, tuple[float, float]] = {}

# Latest readings: asset_id -> reading dict
_latest: Dict[str, Dict[str, Any]] = {}

# Latest anomaly events: asset_id -> list of events
_latest_anomalies: Dict[str, list] = {}

# Engine metadata
_cycle_count: int = 0
_started_at: Optional[str] = None
_last_tick_at: Optional[str] = None
_running: bool = False
_paused: bool = False
_thread: Optional[threading.Thread] = None
_db_path: Optional[str] = None


# ---------------------------------------------------------------------------
# DB SEED
# ---------------------------------------------------------------------------

def seed_iot_assets(db_path: str) -> None:
    """
    Insert the 8 IoT virtual assets into the 'assets' table.
    Uses INSERT OR IGNORE so existing rows are never overwritten.
    The expected_zone column references zone_id; we use 'SHELF_01' as a safe
    default since all IoT assets are labelled as 'IoT Simulation' category.
    Zones for IoT assets are purely logical (Warehouse A / B / C, Sector …)
    and are stored in asset_name / category, not the zone foreign-key.
    """
    # Import here to avoid circular import at module load time
    from database import get_connection, get_utc_now

    now = get_utc_now()
    rows = [
        (
            a.asset_id,
            a.asset_name,
            "IoT Simulation",   # category — clearly distinct from RFID assets
            "SHELF_01",         # expected_zone FK — a valid zone that always exists
            1,                  # active
            now,
            now,
        )
        for a in IOT_ASSETS
    ]

    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO assets
                (asset_id, asset_name, category, expected_zone, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            rows,
        )
    logger.info("IoT simulator: %d virtual assets seeded (INSERT OR IGNORE).", len(rows))


# ---------------------------------------------------------------------------
# POSITION INITIALISATION
# ---------------------------------------------------------------------------

def _init_positions() -> None:
    """Set every asset to its home coordinate if not already tracked."""
    for asset in IOT_ASSETS:
        if asset.asset_id not in _positions:
            _positions[asset.asset_id] = (asset.home_lat, asset.home_lon)


# ---------------------------------------------------------------------------
# SINGLE TICK  (generates one reading per asset and persists it)
# ---------------------------------------------------------------------------

def _run_tick(force_demo_anomaly: bool = False) -> None:
    global _cycle_count, _last_tick_at

    import random
    rng = random.Random()

    for idx, asset in enumerate(IOT_ASSETS):
        try:
            current_lat, current_lon = _positions.get(
                asset.asset_id, (asset.home_lat, asset.home_lon)
            )

            reading, anomaly_events = generate_reading(
                asset, idx, current_lat, current_lon,
                rng=rng,
                force_demo_anomaly=force_demo_anomaly,
            )

            new_lat = reading["latitude"]
            new_lon = reading["longitude"]

            # Persist to SQLite via location_service
            try:
                from location_service import insert_location
                insert_location(
                    asset_id=asset.asset_id,
                    latitude=new_lat,
                    longitude=new_lon,
                    source="simulator",
                    temperature=reading["temperature_c"],
                    battery_level=reading["battery_pct"],
                    speed=reading["speed_kmh"],
                    recorded_at=reading["timestamp"],
                    db_path=_db_path,
                )
            except Exception as exc:
                logger.warning("Failed to persist location for %s: %s", asset.asset_id, exc)

            with _lock:
                _positions[asset.asset_id] = (new_lat, new_lon)
                _latest[asset.asset_id] = reading
                _latest_anomalies[asset.asset_id] = anomaly_events

        except Exception as exc:
            logger.error("Tick error for asset %s: %s", asset.asset_id, exc)

    with _lock:
        _cycle_count += 1
        _last_tick_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# BACKGROUND THREAD LOOP
# ---------------------------------------------------------------------------

def _loop(interval_s: float) -> None:
    global _running, _paused
    logger.info("IoT simulator thread started (interval=%ss).", interval_s)
    while _running:
        if not _paused:
            _run_tick()
        time.sleep(interval_s)
    logger.info("IoT simulator thread stopped.")


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def start(db_path: str, interval_s: float = 5.0) -> None:
    """Start the background simulation loop."""
    global _thread, _running, _paused, _started_at, _db_path

    if _running:
        logger.info("IoT simulator is already running.")
        return

    _db_path = db_path

    # Seed virtual assets into the DB (safe to call multiple times)
    seed_iot_assets(db_path)

    _init_positions()

    # Generate one initial tick immediately so the map has data straight away
    _run_tick(force_demo_anomaly=True)

    _running = True
    _paused = False
    _started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    _thread = threading.Thread(
        target=_loop,
        args=(interval_s,),
        daemon=True,
        name="iot-simulator",
    )
    _thread.start()
    logger.info("IoT simulator started.")


def stop() -> None:
    """Stop the background simulation loop."""
    global _running, _thread
    _running = False
    if _thread and _thread.is_alive():
        _thread.join(timeout=10)
    _thread = None
    logger.info("IoT simulator stopped.")


def pause() -> None:
    """Pause the loop without stopping the thread."""
    global _paused
    _paused = True
    logger.info("IoT simulator paused.")


def resume() -> None:
    """Resume a paused loop."""
    global _paused
    _paused = False
    logger.info("IoT simulator resumed.")


def trigger_tick(force_demo_anomaly: bool = False) -> dict:
    """Manually trigger one simulation tick (used by the Flask API)."""
    if _db_path is None:
        raise RuntimeError("Simulator has not been initialised with a db_path.")
    _run_tick(force_demo_anomaly=force_demo_anomaly)
    return get_status()


def get_status() -> dict:
    """Return a serialisable status snapshot."""
    with _lock:
        return {
            "running":        _running,
            "paused":         _paused,
            "cycle_count":    _cycle_count,
            "started_at":     _started_at,
            "last_tick_at":   _last_tick_at,
            "asset_count":    len(IOT_ASSETS),
            "thresholds":     THRESHOLDS,
        }


def get_latest_readings() -> list[dict]:
    """Return the most recent reading for every IoT asset."""
    with _lock:
        result = []
        for asset in IOT_ASSETS:
            reading = _latest.get(asset.asset_id)
            if reading:
                entry = dict(reading)
                entry["anomaly_events"] = _latest_anomalies.get(asset.asset_id, [])
                result.append(entry)
        return result
