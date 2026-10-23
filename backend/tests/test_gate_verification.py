# ==========================================
# UNIT TESTS: STAGE 06 — MAIN-GATE VERIFICATION
# IoT-Based Smart Asset Tracking System
# ==========================================

import pytest

from anomaly_engine import evaluate_scan_event, process_and_save_scan_event
from database import (
    set_exit_authorization,
    get_authorization,
    get_events,
    get_connection,
)
from config import (
    NORMAL,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNKNOWN_ASSET,
    SHELF_01,
    SHELF_03,
    MAIN_GATE,
)


# ==========================================
# HELPERS
# ==========================================

def _gate_event(asset_id: str, msg_id: str) -> dict:
    return {"asset_id": asset_id, "location": MAIN_GATE, "message_id": msg_id}


def _internal_event(asset_id: str, location: str, msg_id: str) -> dict:
    return {"asset_id": asset_id, "location": location, "message_id": msg_id}


# ==========================================
# 1. VALID AUTHORIZATION — no expiry, active
# ==========================================

def test_valid_authorization(temp_db):
    """
    A004 at MAIN_GATE with authorized_exit=1 and no expiry/revocation
    should produce AUTHORIZED_EXIT.
    """
    result = evaluate_scan_event(
        _gate_event("A004", "gate-test-01-valid"),
        db_path=temp_db
    )
    assert result["status"] == AUTHORIZED_EXIT, f"Expected AUTHORIZED_EXIT, got: {result['status']}"
    assert result["event_metadata"]["authorized"] == 1
    assert result["event_metadata"]["is_anomaly"] is False


# ==========================================
# 2. NO AUTHORIZATION RECORD
# ==========================================

def test_no_authorization(temp_db):
    """
    An asset with no authorization record at MAIN_GATE -> UNAUTHORIZED_EXIT.
    A001's record is deleted to create this condition.
    """
    with get_connection(temp_db) as conn:
        conn.execute("DELETE FROM authorization WHERE asset_id = 'A001';")

    result = evaluate_scan_event(
        _gate_event("A001", "gate-test-02-noauth"),
        db_path=temp_db
    )
    assert result["status"] == UNAUTHORIZED_EXIT
    assert result["event_metadata"]["authorized"] == 0
    assert result["event_metadata"]["is_anomaly"] is True


# ==========================================
# 3. EXPIRED AUTHORIZATION
# ==========================================

def test_expired_authorization(temp_db):
    """
    An asset with authorized_exit=1 but valid_until in the past
    should produce UNAUTHORIZED_EXIT.
    """
    set_exit_authorization(
        "A003", 1,
        notes="Expired permit",
        valid_until="2020-01-01T00:00:00+00:00",
        db_path=temp_db
    )
    result = evaluate_scan_event(
        _gate_event("A003", "gate-test-03-expired"),
        db_path=temp_db
    )
    assert result["status"] == UNAUTHORIZED_EXIT, f"Expected UNAUTHORIZED_EXIT for expired, got: {result['status']}"
    assert result["event_metadata"]["authorized"] == 0


# ==========================================
# 4. REVOKED AUTHORIZATION
# ==========================================

def test_revoked_authorization(temp_db):
    """
    An asset with authorized_exit=1 but revoked_at set -> UNAUTHORIZED_EXIT.
    """
    set_exit_authorization(
        "A004", 1,
        revoked_at="2026-01-01T00:00:00+00:00",
        revocation_reason="Returned from loan",
        db_path=temp_db
    )
    result = evaluate_scan_event(
        _gate_event("A004", "gate-test-04-revoked"),
        db_path=temp_db
    )
    assert result["status"] == UNAUTHORIZED_EXIT, f"Expected UNAUTHORIZED_EXIT for revoked, got: {result['status']}"
    assert result["event_metadata"]["authorized"] == 0


# ==========================================
# 5. UNKNOWN ASSET AT GATE
# ==========================================

def test_unknown_asset_at_gate(temp_db):
    """
    An unregistered asset ID at MAIN_GATE -> UNKNOWN_ASSET.
    """
    result = evaluate_scan_event(
        _gate_event("UNKNOWN_GHOST", "gate-test-05-unknown"),
        db_path=temp_db
    )
    assert result["status"] == UNKNOWN_ASSET
    assert result["event_metadata"]["is_anomaly"] is True


# ==========================================
# 6. ASSET WITH WRONG AUTHORIZATION RECORD
# ==========================================

def test_wrong_asset_id_in_authorization(temp_db):
    """
    A002 (unauthorized in temp_db) at gate -> UNAUTHORIZED_EXIT,
    even though A003 is authorized. Authorization is per-asset-id.
    """
    result_a002 = evaluate_scan_event(
        _gate_event("A002", "gate-test-06-wrong-id"),
        db_path=temp_db
    )
    assert result_a002["status"] == UNAUTHORIZED_EXIT
    assert result_a002["asset_id"] == "A002"

    # A003 should still be authorized at the gate (its own record)
    result_a003 = evaluate_scan_event(
        _gate_event("A003", "gate-test-06-right-id"),
        db_path=temp_db
    )
    assert result_a003["status"] == AUTHORIZED_EXIT
    assert result_a003["asset_id"] == "A003"


# ==========================================
# 7. DUPLICATE GATE EVENT (deduplication)
# ==========================================

def test_duplicate_gate_event(temp_db):
    """
    Sending the same message_id twice should produce a duplicate=True on the second call,
    with no extra event record created.
    """
    event = _gate_event("A004", "gate-test-07-dup-msg")

    result1 = process_and_save_scan_event(event, db_path=temp_db)
    result2 = process_and_save_scan_event(event, db_path=temp_db)

    assert result1["persistence"]["duplicate"] is False
    assert result2["persistence"]["duplicate"] is True

    events = get_events(asset_id="A004", db_path=temp_db)
    gate_events = [e for e in events["items"] if e["location"] == MAIN_GATE]
    # Only one unique event should exist for this message_id
    msg_ids = [e["message_id"] for e in gate_events]
    assert msg_ids.count("gate-test-07-dup-msg") == 1


# ==========================================
# 8. INVALID AUTHORIZATION REQUEST (API PUT)
# ==========================================

def test_invalid_authorization_request(client):
    """
    PUT /api/authorization/<asset_id> without 'authorized_exit' -> 400.
    """
    resp = client.put("/api/authorization/A001", json={"notes": "missing field"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "authorized_exit" in data["error"]


def test_invalid_authorization_bad_date(client):
    """
    PUT /api/authorization/<asset_id> with invalid ISO 8601 valid_until -> 400.
    """
    resp = client.put("/api/authorization/A001", json={
        "authorized_exit": 1,
        "valid_until": "not-a-date"
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "valid_until" in data["error"]


# ==========================================
# 9. NORMAL INTERNAL THEN UNAUTHORIZED GATE
# ==========================================

def test_normal_internal_then_unauthorized_gate(temp_db):
    """
    A005 scanned at SHELF_03 (its expected zone) -> NORMAL.
    Then A005 scanned at MAIN_GATE -> UNAUTHORIZED_EXIT.
    (A005 is authorized_exit=0: strictly internal asset.)
    """
    # A005 expected zone is SHELF_03
    internal_result = evaluate_scan_event(
        _internal_event("A005", SHELF_03, "gate-test-09-internal"),
        db_path=temp_db
    )
    assert internal_result["status"] == NORMAL, f"Expected NORMAL, got: {internal_result['status']}"
    assert internal_result["event_metadata"]["is_anomaly"] is False

    gate_result = evaluate_scan_event(
        _gate_event("A005", "gate-test-09-gate"),
        db_path=temp_db
    )
    assert gate_result["status"] == UNAUTHORIZED_EXIT
    assert gate_result["event_metadata"]["authorized"] == 0
    assert gate_result["event_metadata"]["is_anomaly"] is True
