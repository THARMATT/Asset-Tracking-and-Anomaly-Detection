# ==========================================
# UNIT TESTS: ANOMALY DETECTION ENGINE
# ==========================================

import pytest

from anomaly_engine import (
    validate_event_payload,
    evaluate_scan_event,
    evaluate_inventory_audit,
    process_and_save_scan_event,
    run_and_save_inventory_audit
)
from database import (
    set_exit_authorization,
    get_events,
    get_connection
)
from config import (
    NORMAL,
    MISPLACED,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNKNOWN_ASSET,
    MISSING_INVESTIGATION,
    INVALID_EVENT,
    SHELF_01,
    SHELF_02,
    SHELF_03,
    MAIN_GATE,
    EVENT_TYPE_AUDIT
)


# ==========================================
# 1. TEST CASES A THROUGH H
# ==========================================

def test_case_a_normal_expected_zone(temp_db):
    """Test Case A: A001 at SHELF_01 -> NORMAL."""
    event = {
        "asset_id": "A001",
        "location": SHELF_01,
        "message_id": "test-msg-a"
    }
    result = evaluate_scan_event(event, db_path=temp_db)

    assert result["status"] == NORMAL
    assert result["asset_id"] == "A001"
    assert result["detected_zone"] == SHELF_01
    assert result["expected_zone"] == SHELF_01
    assert result["event_metadata"]["is_anomaly"] is False
    assert "verified in expected zone" in result["message"]


def test_case_b_misplaced_asset(temp_db):
    """Test Case B: A002 at SHELF_03 -> MISPLACED."""
    # A002 is expected in SHELF_01
    event = {
        "asset_id": "A002",
        "location": SHELF_03,
        "message_id": "test-msg-b"
    }
    result = evaluate_scan_event(event, db_path=temp_db)

    assert result["status"] == MISPLACED
    assert result["asset_id"] == "A002"
    assert result["detected_zone"] == SHELF_03
    assert result["expected_zone"] == SHELF_01
    assert result["event_metadata"]["is_anomaly"] is True
    assert result["event_metadata"]["severity"] == "WARNING"
    assert "misplaced in zone 'SHELF_03'" in result["message"]


def test_case_c_authorized_gate_exit(temp_db):
    """Test Case C: A004 at MAIN_GATE with valid authorization -> AUTHORIZED_EXIT."""
    # A004 has authorized_exit = 1 by default
    event = {
        "asset_id": "A004",
        "location": MAIN_GATE,
        "message_id": "test-msg-c"
    }
    result = evaluate_scan_event(event, db_path=temp_db)

    assert result["status"] == AUTHORIZED_EXIT
    assert result["asset_id"] == "A004"
    assert result["detected_zone"] == MAIN_GATE
    assert result["expected_zone"] == SHELF_02
    assert result["event_metadata"]["authorized"] == 1
    assert result["event_metadata"]["is_anomaly"] is False
    assert "valid exit authorization" in result["message"]


def test_case_d_unauthorized_gate_exit(temp_db):
    """Test Case D: A005 at MAIN_GATE without valid authorization -> UNAUTHORIZED_EXIT."""
    # A005 has authorized_exit = 0 by default
    event = {
        "asset_id": "A005",
        "location": MAIN_GATE,
        "message_id": "test-msg-d"
    }
    result = evaluate_scan_event(event, db_path=temp_db)

    assert result["status"] == UNAUTHORIZED_EXIT
    assert result["asset_id"] == "A005"
    assert result["detected_zone"] == MAIN_GATE
    assert result["expected_zone"] == SHELF_03
    assert result["event_metadata"]["authorized"] == 0
    assert result["event_metadata"]["is_anomaly"] is True
    assert result["event_metadata"]["severity"] == "HIGH"
    assert "SECURITY ALERT" in result["message"]
    assert "WITHOUT exit authorization" in result["message"]


def test_case_e_unregistered_unknown_asset(temp_db):
    """Test Case E: An unregistered asset ID -> UNKNOWN_ASSET."""
    event = {
        "asset_id": "UNREGISTERED_TAG_999",
        "location": SHELF_02,
        "message_id": "test-msg-e"
    }
    result = evaluate_scan_event(event, db_path=temp_db)

    assert result["status"] == UNKNOWN_ASSET
    assert result["asset_id"] == "UNREGISTERED_TAG_999"
    assert result["detected_zone"] == SHELF_02
    assert result["expected_zone"] is None
    assert result["event_metadata"]["is_anomaly"] is True
    assert "not registered in the system" in result["message"]


def test_case_f_invalid_or_missing_fields(temp_db):
    """Test Case F: An invalid or missing required field -> INVALID_EVENT."""
    # F.1: Missing location
    res1 = evaluate_scan_event({"asset_id": "A001"}, db_path=temp_db)
    assert res1["status"] == INVALID_EVENT
    assert "Missing or empty required field: 'location'" in res1["message"]

    # F.2: Missing asset_id
    res2 = evaluate_scan_event({"location": SHELF_01}, db_path=temp_db)
    assert res2["status"] == INVALID_EVENT
    assert "Missing or empty required field: 'asset_id'" in res2["message"]

    # F.3: Non-dictionary payload
    res3 = evaluate_scan_event("invalid string payload", db_path=temp_db)
    assert res3["status"] == INVALID_EVENT
    assert "Payload must be a JSON dictionary object" in res3["message"]

    # F.4: Unrecognized facility zone
    res4 = evaluate_scan_event({"asset_id": "A001", "location": "PARKING_ROOFTOP"}, db_path=temp_db)
    assert res4["status"] == INVALID_EVENT
    assert "Unrecognized zone: 'PARKING_ROOFTOP'" in res4["message"]

    # F.5: Empty string fields
    res5 = evaluate_scan_event({"asset_id": "   ", "location": SHELF_01}, db_path=temp_db)
    assert res5["status"] == INVALID_EVENT


def test_case_g_unseen_asset_during_ordinary_scan_is_not_missing(temp_db):
    """
    Test Case G: An asset not seen during an ordinary scan must not automatically become missing.
    Only scanned assets receive evaluation events; absent assets are left untouched.
    """
    # A single scan arrives for A001 only.
    # Assets A002, A003, A004, A005 are not in this scan.
    scan_event = {
        "asset_id": "A001",
        "location": SHELF_01,
        "message_id": "ordinary-scan-single"
    }

    # Evaluate and persist the single event
    eval_res = process_and_save_scan_event(scan_event, db_path=temp_db)
    assert eval_res["status"] == NORMAL

    # Check database event history: only 1 event recorded, no automatic "MISSING" flags for A002-A005
    events_resp = get_events(db_path=temp_db)
    assert events_resp["total_count"] == 1
    recorded_event = events_resp["items"][0]
    assert recorded_event["asset_id"] == "A001"
    assert recorded_event["status"] == NORMAL

    # Verify no asset was marked missing
    missing_events = get_events(status=MISSING_INVESTIGATION, db_path=temp_db)
    assert missing_events["total_count"] == 0


def test_case_h_inventory_audit_flags_undetected_assets(temp_db):
    """
    Test Case H: A completed audit may flag an expected but undetected asset for investigation.
    """
    # Suppose during a formal audit, only A001, A002, and A004 are scanned.
    # A003 and A005 are missing.
    scanned_batch = ["A001", "A002", "A004"]

    audit_report = evaluate_inventory_audit(scanned_batch, db_path=temp_db)

    assert audit_report["total_expected"] == 5
    assert audit_report["total_detected"] == 3
    assert audit_report["total_missing"] == 2
    assert set(audit_report["missing_asset_ids"]) == {"A003", "A005"}
    assert audit_report["all_assets_present"] is False

    # Check the evaluations for the missing assets
    for missing_eval in audit_report["missing_evaluations"]:
        assert missing_eval["status"] == MISSING_INVESTIGATION
        assert missing_eval["event_metadata"]["event_type"] == EVENT_TYPE_AUDIT
        assert missing_eval["event_metadata"]["is_anomaly"] is True
        assert "Investigation required" in missing_eval["message"]


# ==========================================
# 2. BOUNDARY & DYNAMIC BEHAVIOR TESTS
# ==========================================

def test_dynamic_authorization_change_at_gate(temp_db):
    """
    Verify that updating exit authorization changes evaluation results dynamically:
    1. A002 initially unauthorized -> UNAUTHORIZED_EXIT
    2. Grant authorization -> AUTHORIZED_EXIT
    3. Revoke authorization -> UNAUTHORIZED_EXIT
    """
    gate_event = {"asset_id": "A002", "location": MAIN_GATE}

    # 1. Initial state (A002 is unauthorized)
    res1 = evaluate_scan_event(gate_event, db_path=temp_db)
    assert res1["status"] == UNAUTHORIZED_EXIT
    assert res1["event_metadata"]["authorized"] == 0

    # 2. Grant authorization for A002
    set_exit_authorization("A002", 1, notes="Approved laptop repair", db_path=temp_db)
    res2 = evaluate_scan_event(gate_event, db_path=temp_db)
    assert res2["status"] == AUTHORIZED_EXIT
    assert res2["event_metadata"]["authorized"] == 1

    # 3. Revoke authorization
    set_exit_authorization("A002", 0, notes="Revoked repair permit", db_path=temp_db)
    res3 = evaluate_scan_event(gate_event, db_path=temp_db)
    assert res3["status"] == UNAUTHORIZED_EXIT
    assert res3["event_metadata"]["authorized"] == 0


def test_dynamic_facility_zone_addition(temp_db):
    """
    Verify that registering a new facility zone dynamically makes it valid for detection.
    """
    event = {"asset_id": "A003", "location": "LAB_CLEAN_ROOM"}

    # Initially unrecognized
    res1 = evaluate_scan_event(event, db_path=temp_db)
    assert res1["status"] == INVALID_EVENT
    assert "Unrecognized zone: 'LAB_CLEAN_ROOM'" in res1["message"]

    # Insert new zone into database
    with get_connection(temp_db) as conn:
        conn.execute("""
            INSERT INTO zones (zone_id, zone_name, zone_type, description)
            VALUES ('LAB_CLEAN_ROOM', 'Specialized Clean Room Lab', 'STORAGE', 'Precision test lab');
        """)

    # Now the zone is recognized dynamically; asset A003 expected in SHELF_02 is MISPLACED in LAB_CLEAN_ROOM
    res2 = evaluate_scan_event(event, db_path=temp_db)
    assert res2["status"] == MISPLACED
    assert res2["detected_zone"] == "LAB_CLEAN_ROOM"


def test_run_and_save_inventory_audit_persistence(temp_db):
    """
    Verify run_and_save_inventory_audit records audit metadata and individual events in DB.
    """
    # All assets detected except A005
    scanned_tags = ["A001", "A002", "A003", "A004"]

    audit_summary = run_and_save_inventory_audit(
        scanned_asset_ids=scanned_tags,
        notes="End-of-shift quarterly inventory audit",
        db_path=temp_db
    )

    assert audit_summary["audit_id"] is not None
    assert audit_summary["total_missing"] == 1
    assert audit_summary["missing_asset_ids"] == ["A005"]

    # Verify that an event was saved in the events table with MISSING_INVESTIGATION
    events_resp = get_events(status=MISSING_INVESTIGATION, db_path=temp_db)
    assert events_resp["total_count"] == 1
    missing_record = events_resp["items"][0]
    assert missing_record["asset_id"] == "A005"
    assert missing_record["status"] == MISSING_INVESTIGATION
    assert missing_record["event_type"] == EVENT_TYPE_AUDIT
    assert missing_record["location"] == "NOT_DETECTED"
