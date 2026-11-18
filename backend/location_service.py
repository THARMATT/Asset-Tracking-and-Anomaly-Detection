# ==========================================
# LOCATION SERVICE MODULE
# IoT-Based Smart Asset Tracking System
# ==========================================
#
# Manages spatial location records for assets.
# IMPORTANT DESIGN CONSTRAINTS:
#   - Location data is entirely INDEPENDENT of RFID/gate authorization logic.
#   - Coordinates NEVER affect anomaly status, gate permits, or exit authorization.
#   - If no GPS hardware is present, all coordinates are labeled as
#     source='simulator' or source='manual' to prevent false precision.
# ==========================================

import logging
from typing import Optional, Dict, Any, List

from database import get_connection, get_utc_now, get_asset
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

# ==========================================
# VALID SOURCE LABELS
# ==========================================
VALID_SOURCES = {"device", "simulator", "manual"}

# ==========================================
# DB MIGRATION (IDEMPOTENT)
# Called from initialize_database() in database.py
# ==========================================

def migrate_location_table(cursor) -> None:
    """
    Create the asset_locations table and its indexes if they do not exist.
    Safe to call multiple times (uses IF NOT EXISTS and PRAGMA checks).
    """
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_locations (
            location_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id      TEXT    NOT NULL,
            latitude      REAL    NOT NULL,
            longitude     REAL    NOT NULL,
            recorded_at   TEXT    NOT NULL,
            source        TEXT    NOT NULL DEFAULT 'simulator'
                          CHECK (source IN ('device', 'simulator', 'manual')),
            accuracy_m    REAL,
            message_id    TEXT,
            temperature   REAL,
            battery_level REAL,
            speed         REAL,
            FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
        );
    """)

    # Unique partial index for deduplication via message_id
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_locations_message_id
        ON asset_locations(message_id)
        WHERE message_id IS NOT NULL;
    """)

    # Performance indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_locations_asset_id
        ON asset_locations(asset_id);
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_locations_recorded_at
        ON asset_locations(recorded_at);
    """)

    logger.info("asset_locations table migration complete.")


# ==========================================
# VALIDATION HELPERS
# ==========================================

def _validate_lat(lat: Any) -> float:
    """Validate and return latitude in [-90, 90]."""
    try:
        v = float(lat)
    except (TypeError, ValueError):
        raise ValueError(f"latitude must be a number, got: {lat!r}")
    if not -90.0 <= v <= 90.0:
        raise ValueError(f"latitude {v} is out of range [-90, 90]")
    return v


def _validate_lon(lon: Any) -> float:
    """Validate and return longitude in [-180, 180]."""
    try:
        v = float(lon)
    except (TypeError, ValueError):
        raise ValueError(f"longitude must be a number, got: {lon!r}")
    if not -180.0 <= v <= 180.0:
        raise ValueError(f"longitude {v} is out of range [-180, 180]")
    return v


def _validate_source(source: Any) -> str:
    """Validate source label."""
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}, got: {source!r}")
    return source


def _optional_float(value: Any, field: str) -> Optional[float]:
    """Parse an optional float field, returning None if absent/None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number or null, got: {value!r}")


# ==========================================
# CORE SERVICE FUNCTIONS
# ==========================================

def insert_location(
    asset_id: str,
    latitude: Any,
    longitude: Any,
    source: str = "simulator",
    accuracy_m: Optional[Any] = None,
    message_id: Optional[str] = None,
    temperature: Optional[Any] = None,
    battery_level: Optional[Any] = None,
    speed: Optional[Any] = None,
    recorded_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate and insert a new asset location record.

    Returns:
        dict with location_id, duplicate flag, and message.

    Raises:
        ValueError: for invalid field values.
        LookupError: if asset_id does not exist.
    """
    target_db = db_path or DATABASE_PATH

    # Validate fields
    lat = _validate_lat(latitude)
    lon = _validate_lon(longitude)
    src = _validate_source(source)
    acc = _optional_float(accuracy_m, "accuracy_m")
    tmp = _optional_float(temperature, "temperature")
    bat = _optional_float(battery_level, "battery_level")
    spd = _optional_float(speed, "speed")
    ts = recorded_at or get_utc_now()

    # Verify asset exists
    asset = get_asset(asset_id, db_path=target_db)
    if asset is None:
        raise LookupError(f"Asset '{asset_id}' does not exist.")

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Deduplication by message_id
        if message_id:
            cursor.execute(
                "SELECT location_id FROM asset_locations WHERE message_id = ?;",
                (message_id,)
            )
            existing = cursor.fetchone()
            if existing:
                logger.info(f"Duplicate location message_id '{message_id}' ignored.")
                return {
                    "location_id": existing["location_id"],
                    "duplicate": True,
                    "message": "Location already recorded (deduplicated by message_id)"
                }

        cursor.execute("""
            INSERT INTO asset_locations
                (asset_id, latitude, longitude, recorded_at, source,
                 accuracy_m, message_id, temperature, battery_level, speed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (asset_id, lat, lon, ts, src, acc, message_id, tmp, bat, spd))

        new_id = cursor.lastrowid
        logger.info(f"Location recorded for asset '{asset_id}': ({lat}, {lon}) source={src}")

    return {
        "location_id": new_id,
        "duplicate": False,
        "message": "Location recorded successfully"
    }


def get_latest_locations(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return the most recent location record for every asset that has one,
    joined with asset metadata.
    """
    target_db = db_path or DATABASE_PATH

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                al.location_id,
                al.asset_id,
                al.latitude,
                al.longitude,
                al.recorded_at,
                al.source,
                al.accuracy_m,
                al.temperature,
                al.battery_level,
                al.speed,
                a.asset_name,
                a.category,
                a.expected_zone,
                a.active
            FROM asset_locations al
            INNER JOIN (
                SELECT asset_id, MAX(location_id) AS max_id
                FROM asset_locations
                GROUP BY asset_id
            ) latest ON al.asset_id = latest.asset_id AND al.location_id = latest.max_id
            JOIN assets a ON al.asset_id = a.asset_id
            ORDER BY al.asset_id ASC;
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_asset_location_history(
    asset_id: str,
    limit: int = 100,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Return the N most recent location records for a single asset, newest first.
    """
    target_db = db_path or DATABASE_PATH
    safe_limit = max(1, min(int(limit), 500))

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                location_id, asset_id, latitude, longitude,
                recorded_at, source, accuracy_m, message_id,
                temperature, battery_level, speed
            FROM asset_locations
            WHERE asset_id = ?
            ORDER BY location_id DESC
            LIMIT ?;
        """, (asset_id, safe_limit))
        return [dict(row) for row in cursor.fetchall()]


def get_telemetry_history(
    asset_id: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Return location rows that contain at least one non-null telemetry field
    (temperature, battery_level, or speed).
    """
    target_db = db_path or DATABASE_PATH
    safe_limit = max(1, min(int(limit), 500))

    where = "(temperature IS NOT NULL OR battery_level IS NOT NULL OR speed IS NOT NULL)"
    params: list = []

    if asset_id:
        where = f"asset_id = ? AND {where}"
        params.append(asset_id)

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                location_id, asset_id, latitude, longitude,
                recorded_at, source,
                temperature, battery_level, speed
            FROM asset_locations
            WHERE {where}
            ORDER BY location_id DESC
            LIMIT ?;
        """, params + [safe_limit])
        return [dict(row) for row in cursor.fetchall()]
