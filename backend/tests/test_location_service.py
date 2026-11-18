# ==========================================
# LOCATION SERVICE TESTS
# IoT-Based Smart Asset Tracking System
# ==========================================
#
# Tests for the asset_locations table migration,
# insert_location service, and all location API routes.
#
# All tests use isolated temp databases via the 'client' fixture from conftest.py.
# ==========================================

import pytest


# ==========================================
# SECTION A: DB MIGRATION & TABLE EXISTS
# ==========================================

class TestLocationTableMigration:
    """Verify that asset_locations table is created by initialize_database."""

    def test_asset_locations_table_exists(self, temp_db):
        """Table must exist after database initialization."""
        from database import get_connection
        with get_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_locations';"
            )
            row = cursor.fetchone()
        assert row is not None, "asset_locations table was not created"

    def test_migration_is_idempotent(self, temp_db):
        """Running initialize_database twice must not raise an error."""
        from database import initialize_database
        initialize_database(db_path=temp_db, seed=False)  # Second call
        from database import get_connection
        with get_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS c FROM asset_locations;")
            row = cursor.fetchone()
        assert row["c"] == 0

    def test_existing_assets_preserved_after_migration(self, temp_db, client):
        """Existing asset and event records must survive the migration."""
        resp = client.get("/api/assets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["data"]) >= 5  # seeded demo assets

    def test_location_table_columns(self, temp_db):
        """Verify all expected columns exist in asset_locations."""
        from database import get_connection
        with get_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(asset_locations);")
            cols = {row["name"] for row in cursor.fetchall()}
        expected = {
            "location_id", "asset_id", "latitude", "longitude",
            "recorded_at", "source", "accuracy_m", "message_id",
            "temperature", "battery_level", "speed"
        }
        assert expected.issubset(cols), f"Missing columns: {expected - cols}"


# ==========================================
# SECTION B: LOCATION SERVICE (unit tests)
# ==========================================

class TestInsertLocation:
    """Unit tests for location_service.insert_location()."""

    def test_valid_location_insert(self, temp_db):
        """Insert a valid location record."""
        from location_service import insert_location
        result = insert_location(
            asset_id="A001",
            latitude=28.6139,
            longitude=77.2090,
            source="simulator",
            db_path=temp_db
        )
        assert result["duplicate"] is False
        assert isinstance(result["location_id"], int)
        assert result["location_id"] > 0

    def test_latitude_too_high(self, temp_db):
        """Latitude > 90 must raise ValueError."""
        from location_service import insert_location
        with pytest.raises(ValueError, match="latitude"):
            insert_location("A001", 91.0, 0.0, db_path=temp_db)

    def test_latitude_too_low(self, temp_db):
        """Latitude < -90 must raise ValueError."""
        from location_service import insert_location
        with pytest.raises(ValueError, match="latitude"):
            insert_location("A001", -91.0, 0.0, db_path=temp_db)

    def test_longitude_too_high(self, temp_db):
        """Longitude > 180 must raise ValueError."""
        from location_service import insert_location
        with pytest.raises(ValueError, match="longitude"):
            insert_location("A001", 0.0, 181.0, db_path=temp_db)

    def test_longitude_too_low(self, temp_db):
        """Longitude < -180 must raise ValueError."""
        from location_service import insert_location
        with pytest.raises(ValueError, match="longitude"):
            insert_location("A001", 0.0, -181.0, db_path=temp_db)

    def test_boundary_values_accepted(self, temp_db):
        """Edge boundary lat/lon values must be accepted."""
        from location_service import insert_location
        r1 = insert_location("A001", -90.0, -180.0, db_path=temp_db)
        assert r1["duplicate"] is False
        r2 = insert_location("A002", 90.0, 180.0, db_path=temp_db)
        assert r2["duplicate"] is False

    def test_unknown_asset_raises_lookup_error(self, temp_db):
        """LookupError must be raised for non-existent asset_id."""
        from location_service import insert_location
        with pytest.raises(LookupError, match="GHOST_ASSET_99"):
            insert_location("GHOST_ASSET_99", 0.0, 0.0, db_path=temp_db)

    def test_invalid_source_raises_value_error(self, temp_db):
        """Invalid source label must raise ValueError."""
        from location_service import insert_location
        with pytest.raises(ValueError, match="source"):
            insert_location("A001", 0.0, 0.0, source="gps_raw", db_path=temp_db)

    def test_all_valid_sources_accepted(self, temp_db):
        """Each of 'device', 'simulator', 'manual' must be accepted."""
        from location_service import insert_location, VALID_SOURCES
        for i, src in enumerate(sorted(VALID_SOURCES)):
            asset_id = ["A001", "A002", "A003"][i]
            r = insert_location(asset_id, float(i), float(i), source=src, db_path=temp_db)
            assert r["duplicate"] is False, f"source='{src}' was rejected"

    def test_message_id_deduplication(self, temp_db):
        """Second insert with same message_id must be a duplicate."""
        from location_service import insert_location
        mid = "loc-msg-dedup-001"
        r1 = insert_location("A001", 10.0, 20.0, message_id=mid, db_path=temp_db)
        r2 = insert_location("A001", 11.0, 21.0, message_id=mid, db_path=temp_db)
        assert r1["duplicate"] is False
        assert r2["duplicate"] is True
        assert r1["location_id"] == r2["location_id"]

    def test_optional_telemetry_fields(self, temp_db):
        """Telemetry fields must be persisted when supplied."""
        from location_service import insert_location, get_asset_location_history
        insert_location(
            "A001", 5.0, 10.0,
            temperature=24.5,
            battery_level=85.0,
            speed=1.2,
            db_path=temp_db
        )
        history = get_asset_location_history("A001", limit=1, db_path=temp_db)
        assert len(history) == 1
        row = history[0]
        assert abs(row["temperature"] - 24.5) < 0.001
        assert abs(row["battery_level"] - 85.0) < 0.001
        assert abs(row["speed"] - 1.2) < 0.001

    def test_non_numeric_latitude_raises(self, temp_db):
        """Non-numeric latitude must raise ValueError."""
        from location_service import insert_location
        with pytest.raises(ValueError, match="latitude"):
            insert_location("A001", "north", 0.0, db_path=temp_db)


# ==========================================
# SECTION C: GET LATEST LOCATIONS
# ==========================================

class TestGetLatestLocations:
    """Tests for location_service.get_latest_locations()."""

    def test_empty_table_returns_empty_list(self, temp_db):
        from location_service import get_latest_locations
        result = get_latest_locations(db_path=temp_db)
        assert result == []

    def test_returns_one_record_per_asset(self, temp_db):
        from location_service import insert_location, get_latest_locations
        # Insert two records for A001 and one for A002
        insert_location("A001", 10.0, 20.0, db_path=temp_db)
        insert_location("A001", 11.0, 21.0, db_path=temp_db)  # newer
        insert_location("A002", 30.0, 40.0, db_path=temp_db)

        result = get_latest_locations(db_path=temp_db)
        asset_ids = [r["asset_id"] for r in result]
        assert asset_ids.count("A001") == 1
        assert asset_ids.count("A002") == 1

    def test_returns_most_recent_record(self, temp_db):
        from location_service import insert_location, get_latest_locations
        insert_location("A001", 10.0, 20.0, db_path=temp_db)
        insert_location("A001", 55.0, 37.0, db_path=temp_db)  # latest (Moscow coords, valid)

        result = get_latest_locations(db_path=temp_db)
        a001 = next(r for r in result if r["asset_id"] == "A001")
        assert abs(a001["latitude"] - 55.0) < 0.001

    def test_includes_asset_metadata(self, temp_db):
        from location_service import insert_location, get_latest_locations
        insert_location("A001", 1.0, 2.0, db_path=temp_db)
        result = get_latest_locations(db_path=temp_db)
        a001 = next(r for r in result if r["asset_id"] == "A001")
        assert "asset_name" in a001
        assert "category" in a001
        assert "expected_zone" in a001


# ==========================================
# SECTION D: GET ASSET LOCATION HISTORY
# ==========================================

class TestGetAssetLocationHistory:
    """Tests for location_service.get_asset_location_history()."""

    def test_history_is_newest_first(self, temp_db):
        from location_service import insert_location, get_asset_location_history
        for i in range(5):
            insert_location("A001", float(i), float(i), db_path=temp_db)
        history = get_asset_location_history("A001", limit=10, db_path=temp_db)
        ids = [r["location_id"] for r in history]
        assert ids == sorted(ids, reverse=True)

    def test_limit_is_respected(self, temp_db):
        from location_service import insert_location, get_asset_location_history
        for i in range(10):
            insert_location("A001", float(i), float(i), db_path=temp_db)
        history = get_asset_location_history("A001", limit=3, db_path=temp_db)
        assert len(history) == 3

    def test_returns_only_requested_asset(self, temp_db):
        from location_service import insert_location, get_asset_location_history
        insert_location("A001", 1.0, 2.0, db_path=temp_db)
        insert_location("A002", 3.0, 4.0, db_path=temp_db)
        history = get_asset_location_history("A001", db_path=temp_db)
        assert all(r["asset_id"] == "A001" for r in history)

    def test_empty_history_for_asset_without_locations(self, temp_db):
        from location_service import get_asset_location_history
        history = get_asset_location_history("A001", db_path=temp_db)
        assert history == []


# ==========================================
# SECTION E: REST API ENDPOINT TESTS
# ==========================================

class TestLocationsAPI:
    """REST API tests for /api/locations and related endpoints."""

    def test_get_latest_locations_empty(self, client):
        resp = client.get("/api/locations/latest")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"] == []

    def test_post_location_valid(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "source": "simulator"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True
        assert data["duplicate"] is False
        assert data["data"]["location_id"] > 0

    def test_post_location_missing_asset_id(self, client):
        resp = client.post("/api/locations", json={
            "latitude": 10.0,
            "longitude": 20.0
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert "asset_id" in data["error"]

    def test_post_location_missing_latitude(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "A001",
            "longitude": 20.0
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False

    def test_post_location_missing_longitude(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0
        })
        assert resp.status_code == 400

    def test_post_location_invalid_latitude(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 999.0,
            "longitude": 77.0
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "latitude" in data["error"].lower()

    def test_post_location_invalid_longitude(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": -999.0
        })
        assert resp.status_code == 400

    def test_post_location_unknown_asset(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "GHOST_XYZ",
            "latitude": 10.0,
            "longitude": 20.0
        })
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False

    def test_post_location_invalid_source(self, client):
        resp = client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0,
            "source": "satellite_fix"
        })
        assert resp.status_code == 400

    def test_post_location_duplicate_message_id(self, client):
        payload = {
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0,
            "message_id": "loc-api-dup-001"
        }
        r1 = client.post("/api/locations", json=payload)
        r2 = client.post("/api/locations", json=payload)
        assert r1.status_code == 201
        assert r2.status_code == 200
        assert r2.get_json()["duplicate"] is True

    def test_get_latest_locations_after_insert(self, client):
        client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0
        })
        resp = client.get("/api/locations/latest")
        data = resp.get_json()
        assert data["count"] >= 1
        found = [r for r in data["data"] if r["asset_id"] == "A001"]
        assert len(found) == 1

    def test_latest_locations_shows_most_recent(self, client):
        client.post("/api/locations", json={"asset_id": "A001", "latitude": 1.0, "longitude": 1.0})
        client.post("/api/locations", json={"asset_id": "A001", "latitude": 55.0, "longitude": 37.0})
        resp = client.get("/api/locations/latest")
        a001 = next(r for r in resp.get_json()["data"] if r["asset_id"] == "A001")
        assert abs(a001["latitude"] - 55.0) < 0.001

    def test_get_asset_location_history_endpoint(self, client):
        client.post("/api/locations", json={"asset_id": "A001", "latitude": 5.0, "longitude": 5.0})
        resp = client.get("/api/assets/A001/locations?limit=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["count"] >= 1

    def test_get_location_history_unknown_asset(self, client):
        resp = client.get("/api/assets/GHOST_ASSET_99/locations")
        assert resp.status_code == 404

    def test_location_history_limit_param(self, client):
        for i in range(10):
            client.post("/api/locations", json={
                "asset_id": "A001",
                "latitude": float(i),
                "longitude": float(i)
            })
        resp = client.get("/api/assets/A001/locations?limit=3")
        data = resp.get_json()
        assert data["count"] == 3

    def test_post_location_non_json_body(self, client):
        resp = client.post(
            "/api/locations",
            data="not-json",
            content_type="text/plain"
        )
        assert resp.status_code == 400

    def test_source_label_preserved_in_response(self, client):
        client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0,
            "source": "manual"
        })
        resp = client.get("/api/locations/latest")
        a001 = next(r for r in resp.get_json()["data"] if r["asset_id"] == "A001")
        assert a001["source"] == "manual"


class TestTelemetryHistoryAPI:
    """Tests for /api/telemetry/history."""

    def test_empty_telemetry_history(self, client):
        resp = client.get("/api/telemetry/history")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"] == []

    def test_telemetry_history_with_data(self, client):
        client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0,
            "temperature": 22.5,
            "battery_level": 90.0
        })
        resp = client.get("/api/telemetry/history")
        data = resp.get_json()
        assert data["count"] >= 1
        row = data["data"][0]
        assert "temperature" in row
        assert "battery_level" in row

    def test_telemetry_excludes_rows_without_telemetry(self, client):
        # Insert location with no telemetry
        client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0
        })
        resp = client.get("/api/telemetry/history")
        data = resp.get_json()
        # Should still be empty (no telemetry fields in any row)
        assert data["count"] == 0

    def test_telemetry_filtered_by_asset_id(self, client):
        client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 1.0,
            "longitude": 1.0,
            "temperature": 20.0
        })
        client.post("/api/locations", json={
            "asset_id": "A002",
            "latitude": 2.0,
            "longitude": 2.0,
            "temperature": 25.0
        })
        resp = client.get("/api/telemetry/history?asset_id=A001")
        data = resp.get_json()
        assert all(r["asset_id"] == "A001" for r in data["data"])

    def test_telemetry_limit_param(self, client):
        for i in range(5):
            client.post("/api/locations", json={
                "asset_id": "A001",
                "latitude": float(i),
                "longitude": float(i),
                "speed": float(i + 1)
            })
        resp = client.get("/api/telemetry/history?limit=2")
        assert resp.get_json()["count"] == 2


class TestSimulatorMovementAPI:
    """Tests for /api/simulator/movement."""

    def test_simulator_disabled_by_default(self, client):
        """Simulator endpoint must return 403 unless env var is set."""
        import os
        os.environ.pop("LOCATION_SIMULATOR_ENABLED", None)
        resp = client.post("/api/simulator/movement", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        assert data["enabled"] is False

    def test_simulator_enabled_via_env(self, client):
        """With LOCATION_SIMULATOR_ENABLED=True, valid request must succeed."""
        import os
        os.environ["LOCATION_SIMULATOR_ENABLED"] = "true"
        try:
            resp = client.post("/api/simulator/movement", json={
                "asset_id": "A001",
                "latitude": 28.6,
                "longitude": 77.2
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["success"] is True
            assert data["simulated"] is True
        finally:
            os.environ.pop("LOCATION_SIMULATOR_ENABLED", None)

    def test_simulator_sets_source_to_simulator(self, client):
        """Simulator endpoint must always record source='simulator'."""
        import os
        os.environ["LOCATION_SIMULATOR_ENABLED"] = "true"
        try:
            client.post("/api/simulator/movement", json={
                "asset_id": "A001",
                "latitude": 10.0,
                "longitude": 20.0
            })
            resp = client.get("/api/locations/latest")
            a001 = next(r for r in resp.get_json()["data"] if r["asset_id"] == "A001")
            assert a001["source"] == "simulator"
        finally:
            os.environ.pop("LOCATION_SIMULATOR_ENABLED", None)


class TestLocationDoesNotAffectGateLogic:
    """
    Safety tests: adding location records must never change anomaly
    status, authorization, or gate logic.
    """

    def test_adding_location_does_not_change_authorization(self, client):
        """POST /api/locations must not modify authorization records."""
        # Check A002 is not authorized (seeded as 0)
        before = client.get("/api/authorization/A002").get_json()
        before_auth = before["authorized_exit"]

        # Record a location
        client.post("/api/locations", json={
            "asset_id": "A002",
            "latitude": 10.0,
            "longitude": 20.0
        })

        after = client.get("/api/authorization/A002").get_json()
        assert after["authorized_exit"] == before_auth, \
            "Location insert must not change gate authorization"

    def test_adding_location_does_not_affect_event_status(self, client):
        """Recording a location must not create any RFID scan events."""
        before = client.get("/api/events").get_json()
        before_count = before["data"]["total_count"]

        client.post("/api/locations", json={
            "asset_id": "A001",
            "latitude": 10.0,
            "longitude": 20.0
        })

        after = client.get("/api/events").get_json()
        after_count = after["data"]["total_count"]
        assert after_count == before_count, \
            "Recording a location must not insert new RFID events"
