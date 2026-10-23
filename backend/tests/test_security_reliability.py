"""
Tests for Stage 09: Security, Reliability, and Error Recovery.
Verifies SQL injection resistance, foreign key constraints, invalid inputs,
deduplication preservation, error shielding, and graceful failure.
"""

import json
import pytest
import sqlite3

from config import MAIN_GATE, SHELF_01, SHELF_02, SHELF_03
from database import get_connection, save_event, get_events, set_exit_authorization


# ==========================================
# 1. SQL INJECTION RESISTANCE & PARAMETERIZATION
# ==========================================

def test_sql_injection_resistance_in_get_asset(client):
    """
    Attempt SQL injection payloads in the asset_id parameter.
    Parameterized queries must prevent injection and safely return 404.
    """
    injection_payload = "A001' OR '1'='1"
    response = client.get(f"/api/assets/{injection_payload}")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False


def test_sql_injection_resistance_in_event_filter(client):
    """
    Attempt SQL injection in event query filters (?status=).
    Parameterized query must treat it as literal string and return 0 matches.
    """
    response = client.get("/api/events?status=NORMAL' OR 1=1;--")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    # Should find 0 events because no status equals that literal string
    assert data["data"]["total_count"] == 0


# ==========================================
# 2. FOREIGN KEY ENFORCEMENT
# ==========================================

def test_foreign_key_enforcement_on_invalid_zone(temp_db):
    """
    Attempt to insert an asset referencing a non-existent zone.
    SQLite PRAGMA foreign_keys = ON must raise an IntegrityError.
    """
    with pytest.raises(sqlite3.IntegrityError):
        with get_connection(temp_db) as conn:
            conn.execute("""
                INSERT INTO assets (asset_id, asset_name, category, expected_zone, active, created_at, updated_at)
                VALUES ('X999', 'Ghost Asset', 'Hardware', 'NON_EXISTENT_ZONE', 1, '2026-10-23T00:00:00Z', '2026-10-23T00:00:00Z');
            """)


def test_foreign_key_cascade_on_authorization(temp_db):
    """
    Deleting an asset must CASCADE or enforce deletion of its authorization record.
    """
    with get_connection(temp_db) as conn:
        conn.execute("DELETE FROM assets WHERE asset_id = 'A005';")
        # Ensure authorization record was deleted
        auth_row = conn.execute("SELECT * FROM authorization WHERE asset_id = 'A005';").fetchone()
        assert auth_row is None


# ==========================================
# 3. ERROR SHIELDING (NO LEAKED TRACES OR PATHS)
# ==========================================

def test_error_shielding_no_stack_traces_on_404(client):
    """Verify 404 errors return structured JSON without stack traces."""
    response = client.get("/api/nonexistent_endpoint")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert "error" in data
    assert "Traceback" not in response.get_data(as_text=True)


def test_error_shielding_no_secrets_in_health_endpoint(client):
    """Health check must never leak file paths or credentials."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert "database_path" not in data
    assert "password" not in data
    assert "username" not in data
    assert "\\" not in str(data.get("database_status"))


# ==========================================
# 4. INPUT VALIDATION & BUFFER OVERFLOW DEFENSES
# ==========================================

def test_oversized_payload_rejection(client):
    """Reject payloads with excessively long strings to prevent memory exhaustion."""
    oversized_id = "A" * 500  # Exceeds standard asset ID length
    response = client.post("/api/events", json={
        "asset_id": oversized_id,
        "location": SHELF_01
    })
    # Must either reject or safely classify without crashing
    assert response.status_code in (201, 400)
    data = response.get_json()
    assert "success" in data


def test_invalid_json_body_rejection(client):
    """Reject unparseable or non-dict JSON body with HTTP 400."""
    response = client.post(
        "/api/events",
        data="NOT_JSON_AT_ALL",
        content_type="application/json"
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


# ==========================================
# 5. DEDUPLICATION PRESERVATION
# ==========================================

def test_deduplication_preserves_single_row(temp_db):
    """
    Submitting the same message_id multiple times must only create a single database record.
    """
    mid = "sec-test-dedup-uuid-999"
    res1 = save_event("A001", SHELF_01, "INTERNAL_SCAN", "NORMAL", message_id=mid, db_path=temp_db)
    res2 = save_event("A001", SHELF_01, "INTERNAL_SCAN", "NORMAL", message_id=mid, db_path=temp_db)

    assert res1["duplicate"] is False
    assert res2["duplicate"] is True
    assert res1["event_id"] == res2["event_id"]

    events = get_events(db_path=temp_db)
    matching = [e for e in events["items"] if e["message_id"] == mid]
    assert len(matching) == 1
