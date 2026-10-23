# ==========================================
# DATABASE MANAGEMENT MODULE
# IoT-Based Smart Asset Tracking System
# ==========================================

import sqlite3
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set

from config import (
    DATABASE_PATH,
    DEFAULT_ZONES,
    RECOGNIZED_ZONES,
    NORMAL,
    MISPLACED,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNKNOWN_ASSET,
    MISSING_INVESTIGATION,
    INVALID_EVENT
)

logger = logging.getLogger(__name__)


# ==========================================
# 1. TIME HELPER
# ==========================================

def get_utc_now() -> str:
    """Return the current time in UTC using standard ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ==========================================
# 2. SAFE CONNECTION CONTEXT MANAGER
# ==========================================

@contextmanager
def get_connection(db_path: Optional[str] = None):
    """
    Open SQLite database connection with row factory and foreign keys enabled.
    Ensures safe commit on success, rollback on error, and clean closing.
    """
    target_db = db_path or DATABASE_PATH

    # Ensure parent directory exists
    Path(target_db).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target_db, timeout=20.0)
    connection.row_factory = sqlite3.Row

    # Enforce foreign key constraints in SQLite
    connection.execute("PRAGMA foreign_keys = ON;")

    try:
        yield connection
        connection.commit()
    except Exception as exc:
        connection.rollback()
        logger.error(f"Database error on {target_db}: {exc}")
        raise
    finally:
        connection.close()


# ==========================================
# 3. SCHEMA INITIALIZATION
# ==========================================

def initialize_database(db_path: Optional[str] = None, seed: bool = True) -> None:
    """
    Automatically create all required tables, constraints, and indexes.
    Optionally seeds demo assets and predefined zones without overwriting existing data.
    """
    target_db = db_path or DATABASE_PATH
    logger.info(f"Initializing database at: {target_db}")

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Set journal mode and consume result
        cursor.execute("PRAGMA journal_mode = WAL;").fetchall()

        # 3.1 Facility Zones Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                zone_id TEXT PRIMARY KEY,
                zone_name TEXT NOT NULL,
                zone_type TEXT NOT NULL DEFAULT 'STORAGE',
                description TEXT
            );
        """)

        # 3.2 Assets Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                expected_zone TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (expected_zone) REFERENCES zones(zone_id) ON UPDATE CASCADE
            );
        """)

        # 3.3 Exit Authorization Table
        # Exit authorization is kept distinct from asset existence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authorization (
                asset_id TEXT PRIMARY KEY,
                authorized_exit INTEGER NOT NULL CHECK (authorized_exit IN (0, 1)),
                valid_until TEXT,
                requested_by TEXT,
                approved_by TEXT,
                revoked_at TEXT,
                revocation_reason TEXT,
                notes TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
            );
        """)

        # Inline migration: add new columns if they don't exist (for existing databases)
        _new_cols = [
            ("requested_by", "TEXT"),
            ("approved_by", "TEXT"),
            ("revoked_at", "TEXT"),
            ("revocation_reason", "TEXT"),
        ]
        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(authorization)").fetchall()}
        for col_name, col_type in _new_cols:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE authorization ADD COLUMN {col_name} {col_type};")
                logger.info(f"Migration: added column 'authorization.{col_name}'")

        # 3.4 Tracking Events Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                asset_id TEXT,
                location TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'INTERNAL_SCAN',
                status TEXT NOT NULL,
                message TEXT,
                timestamp TEXT NOT NULL,
                authorized INTEGER,
                raw_payload TEXT
            );
        """)

        # 3.5 Inventory Audits Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_timestamp TEXT NOT NULL,
                total_expected INTEGER NOT NULL,
                detected_count INTEGER NOT NULL,
                missing_count INTEGER NOT NULL,
                missing_asset_ids TEXT NOT NULL,
                notes TEXT
            );
        """)

        # 3.6 Create Performance Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_expected_zone ON assets(expected_zone);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_active ON assets(active);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_asset_id ON events(asset_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_location ON events(location);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audits_timestamp ON audits(audit_timestamp);")

        # Unique partial index for deduplication via message_id (only when supplied)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_events_message_id
            ON events(message_id)
            WHERE message_id IS NOT NULL;
        """)

        # 3.7 Seed structural facility zones
        cursor.executemany("""
            INSERT OR IGNORE INTO zones (zone_id, zone_name, zone_type, description)
            VALUES (?, ?, ?, ?);
        """, DEFAULT_ZONES)

    if seed:
        seed_demo_data(db_path=target_db)


# ==========================================
# 4. DEMO DATA SEEDING (SAFE & IDEMPOTENT)
# ==========================================

def seed_demo_data(db_path: Optional[str] = None) -> None:
    """
    Safely seed predefined zones and 5 sample assets.
    Uses INSERT OR IGNORE to never overwrite changes made by the user.
    """
    target_db = db_path or DATABASE_PATH
    now = get_utc_now()

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Seed Predefined Zones
        cursor.executemany("""
            INSERT OR IGNORE INTO zones (zone_id, zone_name, zone_type, description)
            VALUES (?, ?, ?, ?);
        """, DEFAULT_ZONES)

        # 5 Sample Assets
        # A001: Laptop, SHELF_01, authorized
        # A002: Monitor, SHELF_01, unauthorized
        # A003: Keyboard, SHELF_02, authorized
        # A004: Projector, SHELF_02, authorized
        # A005: Scanner, SHELF_03, unauthorized
        demo_assets = [
            ("A001", "Laptop", "IT Equipment", "SHELF_01", 1, now, now),
            ("A002", "Monitor", "IT Equipment", "SHELF_01", 1, now, now),
            ("A003", "Keyboard", "Peripherals", "SHELF_02", 1, now, now),
            ("A004", "Projector", "AV Equipment", "SHELF_02", 1, now, now),
            ("A005", "Scanner", "Warehouse Handhelds", "SHELF_03", 1, now, now),
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO assets
            (asset_id, asset_name, category, expected_zone, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, demo_assets)

        # Seed Corresponding Exit Authorization Records
        demo_authorizations = [
            ("A001", 1, "Authorized client demo loan", now),
            ("A002", 0, "Fixed desk monitor - exit not permitted", now),
            ("A003", 1, "Staff accessory permit", now),
            ("A004", 1, "Conference presentation loan", now),
            ("A005", 0, "Warehouse asset - strictly internal", now),
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO authorization
            (asset_id, authorized_exit, notes, updated_at)
            VALUES (?, ?, ?, ?);
        """, demo_authorizations)

    logger.info("Demo data verified and seeded successfully.")


# ==========================================
# 5. ASSET REUSABLE FUNCTIONS
# ==========================================

def get_asset(asset_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve single asset by ID, including its exit authorization status.
    Returns None if asset is not registered.
    """
    target_db = db_path or DATABASE_PATH

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.asset_id,
                a.asset_name,
                a.category,
                a.expected_zone,
                a.active,
                a.created_at,
                a.updated_at,
                auth.authorized_exit,
                auth.notes AS authorization_notes,
                auth.valid_until AS authorization_valid_until
            FROM assets a
            LEFT JOIN authorization auth ON a.asset_id = auth.asset_id
            WHERE a.asset_id = ?;
        """, (asset_id,))

        row = cursor.fetchone()
        return dict(row) if row else None


def get_assets(active_only: bool = False, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve all registered assets with their expected zone and authorization status.
    """
    target_db = db_path or DATABASE_PATH

    query = """
        SELECT
            a.asset_id,
            a.asset_name,
            a.category,
            a.expected_zone,
            a.active,
            a.created_at,
            a.updated_at,
            COALESCE(auth.authorized_exit, 0) AS authorized_exit,
            auth.notes AS authorization_notes,
            auth.valid_until AS authorization_valid_until
        FROM assets a
        LEFT JOIN authorization auth ON a.asset_id = auth.asset_id
    """
    params: List[Any] = []

    if active_only:
        query += " WHERE a.active = 1"

    query += " ORDER BY a.asset_id ASC;"

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def update_asset(
    asset_id: str,
    asset_name: Optional[str] = None,
    category: Optional[str] = None,
    expected_zone: Optional[str] = None,
    active: Optional[int] = None,
    authorized_exit: Optional[int] = None,
    notes: Optional[str] = None,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Safely update asset metadata and/or exit authorization.
    Returns the updated asset dict or None if asset does not exist.
    """
    target_db = db_path or DATABASE_PATH
    now = get_utc_now()

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Check if asset exists
        cursor.execute("SELECT asset_id FROM assets WHERE asset_id = ?;", (asset_id,))
        if not cursor.fetchone():
            return None

        # Build dynamic update for assets table
        update_fields = []
        update_values = []

        if asset_name is not None:
            update_fields.append("asset_name = ?")
            update_values.append(asset_name)

        if category is not None:
            update_fields.append("category = ?")
            update_values.append(category)

        if expected_zone is not None:
            update_fields.append("expected_zone = ?")
            update_values.append(expected_zone)

        if active is not None:
            update_fields.append("active = ?")
            update_values.append(1 if active else 0)

        if update_fields:
            update_fields.append("updated_at = ?")
            update_values.append(now)
            update_values.append(asset_id)

            cursor.execute(f"""
                UPDATE assets
                SET {', '.join(update_fields)}
                WHERE asset_id = ?;
            """, update_values)

        # Update or set authorization if provided
        if authorized_exit is not None:
            auth_val = 1 if authorized_exit else 0
            cursor.execute("""
                INSERT INTO authorization (asset_id, authorized_exit, notes, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    authorized_exit = excluded.authorized_exit,
                    notes = COALESCE(excluded.notes, authorization.notes),
                    updated_at = excluded.updated_at;
            """, (asset_id, auth_val, notes, now))

    return get_asset(asset_id, db_path=target_db)


# ==========================================
# 6. EXIT AUTHORIZATION FUNCTIONS
# ==========================================

def check_exit_authorization(asset_id: str, db_path: Optional[str] = None) -> bool:
    """
    Check whether an asset is authorized to exit through the main gate.
    Rules (in order):
    - If no record exists: returns False.
    - If authorized_exit = 0: returns False.
    - If revoked_at is not NULL: returns False (revoked).
    - If valid_until is not NULL and is in the past: returns False (expired).
    - Otherwise: returns True.
    """
    target_db = db_path or DATABASE_PATH
    now = get_utc_now()

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT authorized_exit, valid_until, revoked_at
            FROM authorization
            WHERE asset_id = ?;
        """, (asset_id,))

        row = cursor.fetchone()
        if row is None:
            return False

        if not bool(row["authorized_exit"]):
            return False

        # Check revocation
        if row["revoked_at"] is not None:
            return False

        # Check temporal validity
        if row["valid_until"] is not None:
            try:
                expiry = row["valid_until"].replace("Z", "+00:00")
                now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
                exp_dt = datetime.fromisoformat(expiry)
                if now_dt > exp_dt:
                    return False
            except (ValueError, TypeError):
                pass  # Malformed valid_until treated as no expiry

        return True


def set_exit_authorization(
    asset_id: str,
    authorized_exit: int,
    notes: Optional[str] = None,
    valid_until: Optional[str] = None,
    requested_by: Optional[str] = None,
    approved_by: Optional[str] = None,
    revoked_at: Optional[str] = None,
    revocation_reason: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Set or update exit authorization for an asset.
    All fields are optional except asset_id and authorized_exit.
    Setting revoked_at to a non-None value revokes the authorization.
    Setting authorized_exit=0 is also considered a revocation.
    """
    target_db = db_path or DATABASE_PATH
    now = get_utc_now()
    auth_val = 1 if authorized_exit else 0

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Asset must exist before authorizing
        cursor.execute("SELECT asset_id FROM assets WHERE asset_id = ?;", (asset_id,))
        if not cursor.fetchone():
            return False

        cursor.execute("""
            INSERT INTO authorization (asset_id, authorized_exit, notes, valid_until,
                                       requested_by, approved_by, revoked_at, revocation_reason, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                authorized_exit = excluded.authorized_exit,
                notes = CASE WHEN excluded.notes IS NOT NULL THEN excluded.notes ELSE authorization.notes END,
                valid_until = excluded.valid_until,
                requested_by = CASE WHEN excluded.requested_by IS NOT NULL THEN excluded.requested_by ELSE authorization.requested_by END,
                approved_by = CASE WHEN excluded.approved_by IS NOT NULL THEN excluded.approved_by ELSE authorization.approved_by END,
                revoked_at = excluded.revoked_at,
                revocation_reason = CASE WHEN excluded.revocation_reason IS NOT NULL THEN excluded.revocation_reason ELSE authorization.revocation_reason END,
                updated_at = excluded.updated_at;
        """, (asset_id, auth_val, notes, valid_until, requested_by, approved_by, revoked_at, revocation_reason, now))

        return True


def get_authorization(asset_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the full authorization record for an asset."""
    target_db = db_path or DATABASE_PATH
    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM authorization WHERE asset_id = ?;", (asset_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_authorizations(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all authorization records ordered by asset_id."""
    target_db = db_path or DATABASE_PATH
    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT auth.*, a.asset_name, a.expected_zone
            FROM authorization auth
            JOIN assets a ON auth.asset_id = a.asset_id
            ORDER BY auth.asset_id;
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_exit_authorization_reason(asset_id: str, db_path: Optional[str] = None) -> str:
    """Return a human-readable reason why an asset is not authorized to exit."""
    target_db = db_path or DATABASE_PATH
    now = get_utc_now()

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT authorized_exit, valid_until, revoked_at, revocation_reason
            FROM authorization WHERE asset_id = ?;
        """, (asset_id,))
        row = cursor.fetchone()

    if row is None:
        return "no authorization record on file"
    if not bool(row["authorized_exit"]):
        return "authorization is explicitly denied"
    if row["revoked_at"] is not None:
        reason = row["revocation_reason"] or "no reason recorded"
        return f"authorization was revoked at {row['revoked_at']} ({reason})"
    if row["valid_until"] is not None:
        try:
            expiry = row["valid_until"].replace("Z", "+00:00")
            now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
            exp_dt = datetime.fromisoformat(expiry)
            if now_dt > exp_dt:
                return f"authorization expired at {row['valid_until']}"
        except (ValueError, TypeError):
            pass
    return "authorization denied"


# ==========================================
# 7. EVENT TRACKING & DEDUPLICATION
# ==========================================

def save_event(
    asset_id: Optional[str],
    detected_zone: str,
    event_type: str,
    status: str,
    message: Optional[str] = None,
    authorized: Optional[int] = None,
    message_id: Optional[str] = None,
    raw_payload: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Persist an asset tracking event using parameterized queries.
    Deduplicates events by message_id if provided.
    Returns dict with event_id and duplicate flag.
    """
    target_db = db_path or DATABASE_PATH
    event_time = timestamp or get_utc_now()
    payload_str = json.dumps(raw_payload) if isinstance(raw_payload, dict) else (raw_payload or "")

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Check for message_id deduplication
        if message_id:
            cursor.execute("SELECT event_id FROM events WHERE message_id = ?;", (message_id,))
            existing = cursor.fetchone()
            if existing:
                logger.info(f"Duplicate message_id '{message_id}' ignored.")
                return {
                    "event_id": existing["event_id"],
                    "duplicate": True,
                    "message": "Event already processed (deduplicated)"
                }

        cursor.execute("""
            INSERT INTO events (
                message_id,
                asset_id,
                location,
                event_type,
                status,
                message,
                timestamp,
                authorized,
                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            message_id,
            asset_id,
            detected_zone,
            event_type,
            status,
            message,
            event_time,
            authorized,
            payload_str
        ))

        new_event_id = cursor.lastrowid
        return {
            "event_id": new_event_id,
            "duplicate": False,
            "message": "Event recorded successfully"
        }


def get_events(
    limit: int = 50,
    offset: int = 0,
    asset_id: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve paginated events with optional filters and safe boundary limits.
    Returns dict containing items, total_count, limit, and offset.
    """
    target_db = db_path or DATABASE_PATH

    # Safe pagination clamps
    safe_limit = max(1, min(int(limit), 500))
    safe_offset = max(0, int(offset))

    where_clauses: List[str] = []
    params: List[Any] = []

    if asset_id:
        where_clauses.append("asset_id = ?")
        params.append(asset_id)

    if status:
        where_clauses.append("status = ?")
        params.append(status)

    if location:
        where_clauses.append("location = ?")
        params.append(location)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Get total matching count
        count_query = f"SELECT COUNT(*) AS total FROM events {where_sql};"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()["total"]

        # Fetch paginated items ordered newest first
        query = f"""
            SELECT
                event_id,
                message_id,
                asset_id,
                location,
                event_type,
                status,
                message,
                timestamp,
                authorized,
                raw_payload
            FROM events
            {where_sql}
            ORDER BY event_id DESC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(query, params + [safe_limit, safe_offset])
        rows = [dict(row) for row in cursor.fetchall()]

        return {
            "items": rows,
            "total_count": total_count,
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": (safe_offset + len(rows)) < total_count
        }


# ==========================================
# 8. SUMMARY COUNTS & DASHBOARD METRICS
# ==========================================

def retrieve_summary_counts(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute aggregate summary counts for assets, authorization, and event statuses.
    """
    target_db = db_path or DATABASE_PATH

    with get_connection(target_db) as conn:
        cursor = conn.cursor()

        # Asset metrics
        cursor.execute("SELECT COUNT(*) AS total FROM assets;")
        total_assets = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS active FROM assets WHERE active = 1;")
        active_assets = cursor.fetchone()["active"]

        # Authorization metrics
        cursor.execute("SELECT COUNT(*) AS auth_cnt FROM authorization WHERE authorized_exit = 1;")
        authorized_count = cursor.fetchone()["auth_cnt"]

        cursor.execute("SELECT COUNT(*) AS unauth_cnt FROM authorization WHERE authorized_exit = 0;")
        unauthorized_count = cursor.fetchone()["unauth_cnt"]

        # Events metrics
        cursor.execute("SELECT COUNT(*) AS total_events FROM events;")
        total_events = cursor.fetchone()["total_events"]

        # Status breakdown in events
        cursor.execute("""
            SELECT status, COUNT(*) AS count
            FROM events
            GROUP BY status;
        """)
        status_breakdown = {row["status"]: row["count"] for row in cursor.fetchall()}

        # Assets by expected zone
        cursor.execute("""
            SELECT expected_zone, COUNT(*) AS count
            FROM assets
            GROUP BY expected_zone;
        """)
        zone_breakdown = {row["expected_zone"]: row["count"] for row in cursor.fetchall()}

        normal_events = status_breakdown.get(NORMAL, 0)
        misplaced_events = status_breakdown.get(MISPLACED, 0)
        authorized_exits = status_breakdown.get(AUTHORIZED_EXIT, 0)
        unauthorized_exits = status_breakdown.get(UNAUTHORIZED_EXIT, 0)
        unknown_assets = status_breakdown.get(UNKNOWN_ASSET, 0)
        missing_investigations = status_breakdown.get(MISSING_INVESTIGATION, 0)

        return {
            "registered_assets": total_assets,
            "total_assets": total_assets,  # Backward compatibility alias
            "active_assets": active_assets,
            "total_events": total_events,
            "normal_events": normal_events,
            "misplaced_events": misplaced_events,
            "authorized_exits": authorized_exits,
            "unauthorized_exits": unauthorized_exits,
            "unknown_assets": unknown_assets,
            "missing_investigations": missing_investigations,
            "authorized_exit_count": authorized_count,
            "unauthorized_exit_count": unauthorized_count,
            "status_breakdown": status_breakdown,
            "zone_breakdown": zone_breakdown,
            "definitions": {
                "registered_assets": "Total count of registered physical assets in the system",
                "active_assets": "Count of registered assets currently marked active",
                "total_events": "Total count of recorded asset tracking events",
                "normal_events": "Scans where an asset was detected in its expected storage zone",
                "misplaced_events": "Scans where an asset was detected in an unexpected internal zone",
                "authorized_exits": "Scans at MAIN_GATE where asset had valid exit authorization",
                "unauthorized_exits": "Scans at MAIN_GATE where asset lacked valid exit authorization",
                "unknown_assets": "Scans referencing an uncataloged or unregistered asset ID",
                "missing_investigations": "Flagged records where an asset was not detected during an inventory audit"
            }
        }


# ==========================================
# 9. ZONE LOOKUP REUSABLE FUNCTION
# ==========================================

def get_all_zones(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all registered facility zones."""
    target_db = db_path or DATABASE_PATH

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT zone_id, zone_name, zone_type, description FROM zones ORDER BY zone_id;")
        return [dict(row) for row in cursor.fetchall()]


def get_recognized_zones(db_path: Optional[str] = None) -> Set[str]:
    """Retrieve set of all recognized zone codes from database and default config."""
    target_db = db_path or DATABASE_PATH
    zones = set(RECOGNIZED_ZONES)

    try:
        with get_connection(target_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT zone_id FROM zones;")
            zones.update(row["zone_id"] for row in cursor.fetchall())
    except Exception as exc:
        logger.warning(f"Could not load dynamic zones from database: {exc}")

    return zones


# ==========================================
# 10. INVENTORY AUDIT PERSISTENCE
# ==========================================

def save_audit_record(
    total_expected: int,
    detected_count: int,
    missing_count: int,
    missing_asset_ids: List[str],
    notes: Optional[str] = None,
    timestamp: Optional[str] = None,
    db_path: Optional[str] = None
) -> int:
    """Persist an inventory audit execution log."""
    target_db = db_path or DATABASE_PATH
    audit_time = timestamp or get_utc_now()
    missing_json = json.dumps(missing_asset_ids)

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audits (
                audit_timestamp,
                total_expected,
                detected_count,
                missing_count,
                missing_asset_ids,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            audit_time,
            total_expected,
            detected_count,
            missing_count,
            missing_json,
            notes
        ))
        return cursor.lastrowid


def get_audit_history(
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve paginated inventory audit execution logs."""
    target_db = db_path or DATABASE_PATH
    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))

    with get_connection(target_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM audits;")
        total_count = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT
                audit_id,
                audit_timestamp,
                total_expected,
                detected_count,
                missing_count,
                missing_asset_ids,
                notes
            FROM audits
            ORDER BY audit_id DESC
            LIMIT ? OFFSET ?;
        """, (safe_limit, safe_offset))

        rows = []
        for r in cursor.fetchall():
            item = dict(r)
            try:
                item["missing_asset_ids"] = json.loads(item["missing_asset_ids"])
            except Exception:
                pass
            rows.append(item)

        return {
            "items": rows,
            "total_count": total_count,
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": (safe_offset + len(rows)) < total_count
        }
