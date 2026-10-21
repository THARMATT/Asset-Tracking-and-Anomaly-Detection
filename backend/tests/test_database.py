# ==========================================
# UNIT TESTS: DATABASE & FOUNDATION
# ==========================================

import sqlite3
import pytest
from datetime import datetime

from database import (
    initialize_database,
    seed_demo_data,
    get_asset,
    get_assets,
    update_asset,
    check_exit_authorization,
    set_exit_authorization,
    save_event,
    get_events,
    retrieve_summary_counts,
    get_all_zones,
    get_connection
)
from config import (
    NORMAL,
    MISPLACED,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNKNOWN_ASSET,
    SHELF_01,
    SHELF_02,
    SHELF_03,
    MAIN_GATE
)


# ==========================================
# 1. DATABASE INITIALIZATION & SCHEMA TESTS
# ==========================================

def test_database_initialization_tables_and_indexes(empty_db):
    """Verify that all required tables and indexes are created properly."""
    with get_connection(empty_db) as conn:
        cursor = conn.cursor()

        # Check table existence
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}
        assert "assets" in tables
        assert "authorization" in tables
        assert "events" in tables
        assert "zones" in tables

        # Check unique partial index for deduplication
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_events_message_id';")
        assert cursor.fetchone() is not None


# ==========================================
# 2. DEMO SEEDING & IDEMPOTENCY TESTS
# ==========================================

def test_demo_seeding_creates_sample_assets(temp_db):
    """Verify that the 5 sample assets and their authorizations are seeded."""
    assets = get_assets(db_path=temp_db)
    asset_ids = [a["asset_id"] for a in assets]
    assert len(assets) == 5
    assert set(asset_ids) == {"A001", "A002", "A003", "A004", "A005"}

    # Verify initial sample exit authorization statuses
    # A001: Laptop, SHELF_01, authorized
    # A002: Monitor, SHELF_01, NOT authorized
    # A003: Keyboard, SHELF_02, authorized
    # A004: Projector, SHELF_02, authorized
    # A005: Scanner, SHELF_03, NOT authorized
    assert check_exit_authorization("A001", db_path=temp_db) is True
    assert check_exit_authorization("A002", db_path=temp_db) is False
    assert check_exit_authorization("A003", db_path=temp_db) is True
    assert check_exit_authorization("A004", db_path=temp_db) is True
    assert check_exit_authorization("A005", db_path=temp_db) is False


def test_seed_demo_data_is_repeatable_and_preserves_edits(temp_db):
    """Verify that re-running seed_demo_data does NOT overwrite user modifications."""
    # Modify asset A001 name and flip authorization
    update_asset(
        "A001",
        asset_name="Custom Executive Laptop",
        authorized_exit=0,
        notes="Revoked loan permission",
        db_path=temp_db
    )

    # Re-run seed operation
    seed_demo_data(db_path=temp_db)

    # Asset A001 must retain user edits, not reverted to default
    asset = get_asset("A001", db_path=temp_db)
    assert asset["asset_name"] == "Custom Executive Laptop"
    assert asset["authorized_exit"] == 0
    assert asset["authorization_notes"] == "Revoked loan permission"


# ==========================================
# 3. EXIT AUTHORIZATION TESTS
# ==========================================

def test_exit_authorization_unknown_asset_is_unauthorized(temp_db):
    """Unknown or uncataloged asset IDs must NEVER be authorized to exit."""
    assert check_exit_authorization("UNKNOWN_XYZ_999", db_path=temp_db) is False
    assert check_exit_authorization("", db_path=temp_db) is False


def test_exit_authorization_not_inferred_from_existence(empty_db):
    """An asset existing in the database without an explicit authorization record must return False."""
    with get_connection(empty_db) as conn:
        conn.execute("""
            INSERT INTO assets (asset_id, asset_name, category, expected_zone, created_at, updated_at)
            VALUES ('A999', 'Unassigned Tablet', 'IT', 'SHELF_01', '2026-10-21T00:00:00Z', '2026-10-21T00:00:00Z');
        """)

    # Even though asset A999 exists, exit authorization must evaluate to False
    assert check_exit_authorization("A999", db_path=empty_db) is False

    # Once explicitly granted, authorization evaluates to True
    assert set_exit_authorization("A999", 1, notes="Approved gate exit", db_path=empty_db) is True
    assert check_exit_authorization("A999", db_path=empty_db) is True


def test_set_exit_authorization_fails_for_nonexistent_asset(temp_db):
    """Setting authorization on a non-existent asset must safely return False."""
    assert set_exit_authorization("DOES_NOT_EXIST", 1, db_path=temp_db) is False


# ==========================================
# 4. EVENT PERSISTENCE & DEDUPLICATION TESTS
# ==========================================

def test_save_event_persists_and_retrieves_records(temp_db):
    """Verify saving an event stores all required fields and UTC ISO 8601 timestamp."""
    result = save_event(
        asset_id="A001",
        detected_zone=SHELF_01,
        event_type="INTERNAL_SCAN",
        status=NORMAL,
        message="Asset verified in expected shelf",
        authorized=None,
        message_id="msg-uuid-101",
        db_path=temp_db
    )

    assert result["duplicate"] is False
    assert result["event_id"] is not None

    events_resp = get_events(limit=10, db_path=temp_db)
    assert events_resp["total_count"] == 1
    event = events_resp["items"][0]

    assert event["asset_id"] == "A001"
    assert event["location"] == SHELF_01
    assert event["status"] == NORMAL
    assert event["message_id"] == "msg-uuid-101"

    # Verify timestamp parseable as ISO 8601
    dt = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    assert dt is not None


def test_save_event_deduplication_via_message_id(temp_db):
    """Submitting the same message_id must NOT insert a duplicate record."""
    first = save_event(
        asset_id="A002",
        detected_zone=SHELF_03,
        event_type="INTERNAL_SCAN",
        status=MISPLACED,
        message_id="unique-msg-555",
        db_path=temp_db
    )
    assert first["duplicate"] is False

    second = save_event(
        asset_id="A002",
        detected_zone=SHELF_03,
        event_type="INTERNAL_SCAN",
        status=MISPLACED,
        message_id="unique-msg-555",
        db_path=temp_db
    )
    assert second["duplicate"] is True
    assert second["event_id"] == first["event_id"]

    # Verify database total events remains 1
    events = get_events(db_path=temp_db)
    assert events["total_count"] == 1


def test_save_event_handles_unknown_asset_id(temp_db):
    """Events for uncataloged assets must be stored without foreign key violations."""
    result = save_event(
        asset_id="UNKNOWN_RFID_404",
        detected_zone=MAIN_GATE,
        event_type="GATE_SCAN",
        status=UNKNOWN_ASSET,
        message="Unrecognized tag detected at gate",
        db_path=temp_db
    )
    assert result["duplicate"] is False
    assert result["event_id"] is not None

    events = get_events(asset_id="UNKNOWN_RFID_404", db_path=temp_db)
    assert events["total_count"] == 1
    assert events["items"][0]["status"] == UNKNOWN_ASSET


# ==========================================
# 5. PAGINATION & FILTERING TESTS
# ==========================================

def test_events_pagination_and_filtering(temp_db):
    """Verify offset, limit, and status/location filters."""
    # Insert 15 test events
    for i in range(15):
        save_event(
            asset_id=f"A00{(i % 5) + 1}",
            detected_zone=SHELF_01 if i < 10 else MAIN_GATE,
            event_type="INTERNAL_SCAN" if i < 10 else "GATE_SCAN",
            status=NORMAL if i < 10 else UNAUTHORIZED_EXIT,
            message_id=f"page-test-msg-{i}",
            db_path=temp_db
        )

    # Test limit and offset
    page1 = get_events(limit=5, offset=0, db_path=temp_db)
    assert len(page1["items"]) == 5
    assert page1["total_count"] == 15
    assert page1["has_more"] is True

    page2 = get_events(limit=5, offset=5, db_path=temp_db)
    assert len(page2["items"]) == 5
    # Ensure disjoint items across pages
    page1_ids = {item["event_id"] for item in page1["items"]}
    page2_ids = {item["event_id"] for item in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)

    # Test status filtering
    gate_events = get_events(status=UNAUTHORIZED_EXIT, db_path=temp_db)
    assert gate_events["total_count"] == 5
    for item in gate_events["items"]:
        assert item["status"] == UNAUTHORIZED_EXIT


# ==========================================
# 6. ASSET METADATA UPDATE & SUMMARY TESTS
# ==========================================

def test_update_asset_metadata(temp_db):
    """Verify asset metadata modification updates fields and timestamps."""
    original = get_asset("A003", db_path=temp_db)
    original_updated_at = original["updated_at"]

    updated = update_asset(
        "A003",
        asset_name="Mechanical Wireless Keyboard",
        expected_zone=SHELF_01,
        active=0,
        db_path=temp_db
    )

    assert updated is not None
    assert updated["asset_name"] == "Mechanical Wireless Keyboard"
    assert updated["expected_zone"] == SHELF_01
    assert updated["active"] == 0
    assert updated["updated_at"] >= original_updated_at


def test_retrieve_summary_counts(temp_db):
    """Verify summary counts reflect current asset and authorization numbers."""
    summary = retrieve_summary_counts(db_path=temp_db)
    assert summary["total_assets"] == 5
    assert summary["active_assets"] == 5
    assert summary["authorized_exit_count"] == 3  # A001, A003, A004
    assert summary["unauthorized_exit_count"] == 2  # A002, A005
    assert summary["total_events"] == 0


def test_get_all_zones(temp_db):
    """Verify predefined zones are returned."""
    zones = get_all_zones(db_path=temp_db)
    zone_ids = [z["zone_id"] for z in zones]
    assert SHELF_01 in zone_ids
    assert SHELF_02 in zone_ids
    assert SHELF_03 in zone_ids
    assert MAIN_GATE in zone_ids
