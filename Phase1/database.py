
# ==========================================
# DATABASE MANAGEMENT
# IoT ASSET TRACKING SYSTEM
# ==========================================

import sqlite3
from contextlib import contextmanager

from config import DATABASE_NAME


# ==========================================
# 1. DATABASE CONNECTION
# ==========================================

@contextmanager
def get_connection():
    """Open the database and close it safely after use."""

    connection = sqlite3.connect(DATABASE_NAME)

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ==========================================
# 2. CREATE DATABASE TABLES
# ==========================================

def create_tables():
    """Create the required tables if they do not exist."""

    with get_connection() as connection:

        cursor = connection.cursor()

        # Registered assets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                expected_zone TEXT NOT NULL
            )
        """)

        # Tracking event history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id TEXT,
                event_type TEXT,
                location TEXT,
                timestamp TEXT,
                status TEXT
            )
        """)

        # Demo exit permissions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authorization (
                asset_id TEXT PRIMARY KEY,
                authorized_exit INTEGER NOT NULL
            )
        """)


# ==========================================
# 3. INSERT SAMPLE ASSETS
# ==========================================

def insert_assets():

    create_tables()

    assets = [
        ("A001", "Laptop", "SHELF_01"),
        ("A002", "Monitor", "SHELF_01"),
        ("A003", "Keyboard", "SHELF_02"),
        ("A004", "Projector", "SHELF_02"),
        ("A005", "Scanner", "SHELF_03")
    ]

    with get_connection() as connection:

        connection.executemany("""
            INSERT OR REPLACE INTO assets
            (asset_id, asset_name, expected_zone)
            VALUES (?, ?, ?)
        """, assets)

    print("Sample assets inserted successfully!")


# ==========================================
# 4. INSERT EXIT AUTHORIZATION
# ==========================================

def insert_authorization():

    create_tables()

    authorization_data = [
        ("A001", 1),
        ("A002", 0),
        ("A003", 1),
        ("A004", 1),
        ("A005", 0)
    ]

    with get_connection() as connection:

        connection.executemany("""
            INSERT OR REPLACE INTO authorization
            (asset_id, authorized_exit)
            VALUES (?, ?)
        """, authorization_data)

    print("Authorization records inserted successfully!")


# ==========================================
# 5. GET ONE ASSET
# ==========================================

def get_asset(asset_id):

    create_tables()

    with get_connection() as connection:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT asset_id, asset_name, expected_zone
            FROM assets
            WHERE asset_id = ?
        """, (asset_id,))

        return cursor.fetchone()


# ==========================================
# 6. GET ALL ASSETS
# ==========================================

def get_all_assets():

    create_tables()

    with get_connection() as connection:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT asset_id, asset_name, expected_zone
            FROM assets
            ORDER BY asset_id
        """)

        return cursor.fetchall()


# ==========================================
# 7. CHECK EXIT AUTHORIZATION
# ==========================================

def check_authorization(asset_id):

    create_tables()

    with get_connection() as connection:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT authorized_exit
            FROM authorization
            WHERE asset_id = ?
        """, (asset_id,))

        result = cursor.fetchone()

    # Unknown assets are not authorized
    if result is None:
        return False

    return bool(result[0])


# ==========================================
# 8. RECORD A TRACKING EVENT
# ==========================================

def record_event(
    asset_id,
    event_type,
    location,
    timestamp,
    status
):

    create_tables()

    with get_connection() as connection:

        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO events (
                asset_id,
                event_type,
                location,
                timestamp,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            asset_id,
            event_type,
            location,
            timestamp,
            status
        ))


# ==========================================
# 9. GET EVENT HISTORY
# ==========================================

def get_all_events():

    create_tables()

    with get_connection() as connection:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                event_id,
                asset_id,
                event_type,
                location,
                timestamp,
                status
            FROM events
            ORDER BY event_id
        """)

        return cursor.fetchall()


# ==========================================
# 10. CLEAR EVENT HISTORY
# ==========================================

def clear_events():

    create_tables()

    with get_connection() as connection:

        cursor = connection.cursor()

        cursor.execute("DELETE FROM events")


# ==========================================
# END OF DATABASE FILE
# ==========================================
