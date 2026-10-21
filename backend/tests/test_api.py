# ==========================================
# UNIT TESTS: FLASK REST API ENDPOINTS
# ==========================================

import pytest
import json

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
    MAIN_GATE
)


# ==========================================
# 1. HEALTH & SYSTEM ENDPOINTS
# ==========================================

def test_api_health_endpoint(client):
    """Verify that /api/health returns 200, healthy status, and safe metadata."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["database_status"] == "connected"
    assert "timestamp" in data
    # Ensure raw system file paths and secrets are not leaked
    assert "database_path" not in data
    assert "\\" not in str(data.get("database_status"))


# ==========================================
# 2. ASSET MANAGEMENT ENDPOINTS
# ==========================================

def test_api_list_assets_endpoint(client):
    """Verify that /api/assets returns the 5 seeded sample assets."""
    response = client.get("/api/assets")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 5

    asset_ids = {a["asset_id"] for a in data["data"]}
    assert asset_ids == {"A001", "A002", "A003", "A004", "A005"}


def test_api_list_assets_active_filter(client):
    """Verify filtering active assets via ?active_only=true."""
    # Deactivate asset A003
    client.put(
        "/api/assets/A003",
        data=json.dumps({"active": 0}),
        content_type="application/json"
    )

    response = client.get("/api/assets?active_only=true")
    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 4
    active_ids = {a["asset_id"] for a in data["data"]}
    assert "A003" not in active_ids


def test_api_get_single_asset_endpoint(client):
    """Verify retrieving a single asset by asset_id and proper 404 handling."""
    # Existing asset
    response = client.get("/api/assets/A001")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["data"]["asset_name"] == "Laptop"
    assert data["data"]["expected_zone"] == SHELF_01

    # Non-existent asset
    not_found = client.get("/api/assets/NON_EXISTENT_404")
    assert not_found.status_code == 404
    assert not_found.get_json()["success"] is False
    assert "not found" in not_found.get_json()["error"]


def test_api_modify_asset_metadata(client):
    """Verify modifying asset attributes safely via PUT /api/assets/<id>."""
    put_resp = client.put(
        "/api/assets/A001",
        data=json.dumps({
            "asset_name": "Ultra Laptop Pro",
            "category": "High-Performance Compute",
            "expected_zone": SHELF_02
        }),
        content_type="application/json"
    )
    assert put_resp.status_code == 200
    assert put_resp.get_json()["success"] is True

    # Check updated values
    get_resp = client.get("/api/assets/A001")
    assert get_resp.get_json()["data"]["asset_name"] == "Ultra Laptop Pro"
    assert get_resp.get_json()["data"]["expected_zone"] == SHELF_02

    # Attempt updating non-existent asset
    bad_put = client.put(
        "/api/assets/NOT_FOUND_99",
        data=json.dumps({"asset_name": "Ghost"}),
        content_type="application/json"
    )
    assert bad_put.status_code == 404


# ==========================================
# 3. EXIT AUTHORIZATION ENDPOINTS
# ==========================================

def test_api_authorization_check_and_update(client):
    """Verify checking and modifying authorization status via REST API."""
    # Check A002 (Monitor) - initially unauthorized (0)
    resp = client.get("/api/authorization/A002")
    assert resp.status_code == 200
    assert resp.get_json()["authorized_exit"] is False

    # Grant exit authorization for A002
    put_resp = client.put(
        "/api/authorization/A002",
        data=json.dumps({"authorized_exit": 1, "notes": "Approved offsite repair"}),
        content_type="application/json"
    )
    assert put_resp.status_code == 200
    assert put_resp.get_json()["authorized_exit"] is True

    # Verify authorization check now returns True
    recheck = client.get("/api/authorization/A002")
    assert recheck.get_json()["authorized_exit"] is True

    # 400 error on missing required field
    missing_auth = client.put(
        "/api/authorization/A002",
        data=json.dumps({"notes": "Missing authorized_exit field"}),
        content_type="application/json"
    )
    assert missing_auth.status_code == 400


# ==========================================
# 4. DASHBOARD SUMMARY ENDPOINT
# ==========================================

def test_api_summary_endpoint(client):
    """
    Verify dashboard summary returns all required metrics with explicit definitions:
    registered_assets, total_events, normal_events, misplaced_events,
    authorized_exits, unauthorized_exits, unknown_assets, missing_investigations.
    """
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    totals = data["data"]
    assert "registered_assets" in totals
    assert totals["registered_assets"] == 5
    assert "active_assets" in totals
    assert totals["active_assets"] == 5
    assert "total_events" in totals
    assert "normal_events" in totals
    assert "misplaced_events" in totals
    assert "authorized_exits" in totals
    assert "unauthorized_exits" in totals
    assert "unknown_assets" in totals
    assert "missing_investigations" in totals

    # Definitions
    assert "definitions" in totals
    defs = totals["definitions"]
    assert "registered_assets" in defs
    assert "normal_events" in defs
    assert "missing_investigations" in defs


# ==========================================
# 5. POST /api/events ANOMALY PROCESSING
# ==========================================

def test_api_post_event_normal(client):
    """Post normal event through shared engine -> 201 Created and NORMAL."""
    payload = {
        "asset_id": "A001",
        "location": SHELF_01,
        "message_id": "api-msg-normal-1"
    }
    resp = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 201
    res_data = resp.get_json()["data"]
    assert res_data["status"] == NORMAL
    assert res_data["asset_id"] == "A001"
    assert res_data["detected_zone"] == SHELF_01
    assert res_data["expected_zone"] == SHELF_01


def test_api_post_event_misplaced(client):
    """Post misplaced event -> 201 Created and MISPLACED."""
    payload = {
        "asset_id": "A002",
        "location": SHELF_03,
        "message_id": "api-msg-misplaced-1"
    }
    resp = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 201
    res_data = resp.get_json()["data"]
    assert res_data["status"] == MISPLACED
    assert res_data["detected_zone"] == SHELF_03
    assert res_data["expected_zone"] == SHELF_01


def test_api_post_event_gate_authorized(client):
    """Post authorized gate exit -> 201 Created and AUTHORIZED_EXIT."""
    payload = {
        "asset_id": "A004",
        "location": MAIN_GATE,
        "message_id": "api-msg-gate-auth"
    }
    resp = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 201
    res_data = resp.get_json()["data"]
    assert res_data["status"] == AUTHORIZED_EXIT


def test_api_post_event_gate_unauthorized(client):
    """Post unauthorized gate exit -> 201 Created and UNAUTHORIZED_EXIT."""
    payload = {
        "asset_id": "A005",
        "location": MAIN_GATE,
        "message_id": "api-msg-gate-unauth"
    }
    resp = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 201
    res_data = resp.get_json()["data"]
    assert res_data["status"] == UNAUTHORIZED_EXIT
    assert res_data["event_metadata"]["is_anomaly"] is True


def test_api_post_event_unknown_asset(client):
    """Post scan with uncataloged asset ID -> 201 Created and UNKNOWN_ASSET."""
    payload = {
        "asset_id": "UNKNOWN_TAG_777",
        "location": SHELF_02,
        "message_id": "api-msg-unknown-tag"
    }
    resp = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 201
    res_data = resp.get_json()["data"]
    assert res_data["status"] == UNKNOWN_ASSET
    assert res_data["asset_id"] == "UNKNOWN_TAG_777"


def test_api_post_event_client_status_override_prevention(client):
    """
    Verify that client CANNOT override backend anomaly classification.
    Client passes 'status': 'NORMAL' for a misplaced item (A002 at SHELF_03).
    Backend MUST classify and persist as MISPLACED.
    """
    tampered_payload = {
        "asset_id": "A002",
        "location": SHELF_03,
        "status": "NORMAL",  # Tampered client-supplied status
        "message_id": "api-msg-tampered-override"
    }
    resp = client.post("/api/events", data=json.dumps(tampered_payload), content_type="application/json")
    assert resp.status_code == 201
    res_data = resp.get_json()["data"]
    # The anomaly engine must override client claim
    assert res_data["status"] == MISPLACED
    assert res_data["status"] != "NORMAL"


def test_api_post_event_deduplication(client):
    """
    Submitting the same message_id twice must not create a duplicate database record.
    First call returns 201; second call returns 200 with duplicate=True.
    """
    payload = {
        "asset_id": "A001",
        "location": SHELF_01,
        "message_id": "dedup-test-uuid-999"
    }

    resp1 = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp1.status_code == 201
    assert resp1.get_json()["duplicate"] is False

    resp2 = client.post("/api/events", data=json.dumps(payload), content_type="application/json")
    assert resp2.status_code == 200
    assert resp2.get_json()["duplicate"] is True

    # Check database event count
    events_resp = client.get("/api/events?asset_id=A001")
    assert events_resp.get_json()["data"]["total_count"] == 1


def test_api_post_event_invalid_payloads(client):
    """Verify that malformed or incomplete payloads return 400 Bad Request."""
    # Missing location
    r1 = client.post("/api/events", data=json.dumps({"asset_id": "A001"}), content_type="application/json")
    assert r1.status_code == 400
    assert r1.get_json()["status"] == INVALID_EVENT

    # Missing asset_id
    r2 = client.post("/api/events", data=json.dumps({"location": SHELF_01}), content_type="application/json")
    assert r2.status_code == 400
    assert r2.get_json()["status"] == INVALID_EVENT

    # Unrecognized zone
    r3 = client.post(
        "/api/events",
        data=json.dumps({"asset_id": "A001", "location": "UNKNOWN_PLANET_ZONE"}),
        content_type="application/json"
    )
    assert r3.status_code == 400
    assert r3.get_json()["status"] == INVALID_EVENT
    assert "Unrecognized zone" in r3.get_json()["error"]


# ==========================================
# 6. GET /api/events PAGINATION & FILTERS
# ==========================================

def test_api_get_events_pagination_and_zone_filter(client):
    """Verify pagination and filtering by zone, status, and asset_id."""
    # Seed 10 events
    for i in range(10):
        client.post(
            "/api/events",
            data=json.dumps({
                "asset_id": "A001" if i < 5 else "A002",
                "location": SHELF_01 if i < 5 else SHELF_03,
                "message_id": f"batch-filter-msg-{i}"
            }),
            content_type="application/json"
        )

    # Filter by zone
    resp_zone = client.get("/api/events?zone=SHELF_01")
    assert resp_zone.status_code == 200
    assert resp_zone.get_json()["data"]["total_count"] == 5

    # Filter by status
    resp_status = client.get(f"/api/events?status={MISPLACED}")
    assert resp_status.status_code == 200
    assert resp_status.get_json()["data"]["total_count"] == 5

    # Pagination test
    resp_page = client.get("/api/events?limit=4&offset=0")
    assert resp_page.status_code == 200
    data = resp_page.get_json()["data"]
    assert len(data["items"]) == 4
    assert data["total_count"] == 10
    assert data["has_more"] is True


# ==========================================
# 7. INVENTORY AUDIT ENDPOINTS
# ==========================================

def test_api_audits_workflow(client):
    """
    Verify triggering an audit via POST /api/audits and retrieving
    past audits via GET /api/audits.
    """
    # Trigger audit with A003 missing
    scanned_tags = ["A001", "A002", "A004", "A005"]
    audit_payload = {
        "scanned_asset_ids": scanned_tags,
        "notes": "Mid-day scheduled inventory audit"
    }

    audit_post = client.post("/api/audits", data=json.dumps(audit_payload), content_type="application/json")
    assert audit_post.status_code == 201
    audit_data = audit_post.get_json()["data"]
    assert audit_data["total_missing"] == 1
    assert audit_data["missing_asset_ids"] == ["A003"]

    # Retrieve audit history
    audit_get = client.get("/api/audits")
    assert audit_get.status_code == 200
    audits_history = audit_get.get_json()["data"]["items"]
    assert len(audits_history) >= 1
    assert audits_history[0]["notes"] == "Mid-day scheduled inventory audit"

    # Verify that the missing asset A003 was recorded in events
    events_resp = client.get(f"/api/events?status={MISSING_INVESTIGATION}")
    assert events_resp.status_code == 200
    missing_items = events_resp.get_json()["data"]["items"]
    assert len(missing_items) == 1
    assert missing_items[0]["asset_id"] == "A003"
