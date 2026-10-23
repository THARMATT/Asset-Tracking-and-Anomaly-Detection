"""
Unit tests for the CLI MQTT event publisher.
Verifies payload structures, scenario generators, argument handling, and idempotency logic.
"""

import json
import pytest
from simulator.event_publisher import (
    build_normal_event,
    build_misplaced_event,
    build_unknown_asset_event,
    build_zone_movement_events,
    build_authorized_exit_event,
    build_unauthorized_exit_event,
    build_duplicate_events,
    build_malformed_event,
    build_audit_cycle_events,
    KNOWN_ASSETS,
    KNOWN_ZONES,
)


def test_build_normal_event_schema():
    event = build_normal_event("A001")
    assert event["asset_id"] == "A001"
    assert event["location"] == "SHELF_01"
    assert event["event_type"] == "INTERNAL_SCAN"
    assert event["message_id"].startswith("evt-")
    assert "timestamp" in event
    assert event["_expected_backend_status"] == "NORMAL"


def test_build_misplaced_event_schema():
    event = build_misplaced_event("A001")
    assert event["asset_id"] == "A001"
    assert event["location"] in ["SHELF_02", "SHELF_03"]
    assert event["location"] != "SHELF_01"
    assert event["_expected_backend_status"] == "MISPLACED"


def test_build_unknown_asset_event_schema():
    event = build_unknown_asset_event()
    assert event["asset_id"].startswith("ROGUE_")
    assert event["location"] in KNOWN_ZONES
    assert event["_expected_backend_status"] == "UNKNOWN_ASSET"


def test_build_zone_movement_events():
    events = build_zone_movement_events("A003")
    assert len(events) == 3
    assert [e["location"] for e in events] == ["SHELF_01", "SHELF_02", "SHELF_03"]
    # For A003, expected zone is SHELF_02
    assert events[0]["_expected_backend_status"] == "MISPLACED"
    assert events[1]["_expected_backend_status"] == "NORMAL"
    assert events[2]["_expected_backend_status"] == "MISPLACED"


def test_build_authorized_exit_event():
    event = build_authorized_exit_event()
    assert event["location"] == "MAIN_GATE"
    assert event["event_type"] == "GATE_SCAN"
    assert KNOWN_ASSETS[event["asset_id"]]["authorized_exit"] is True
    assert event["_expected_backend_status"] == "AUTHORIZED_EXIT"


def test_build_unauthorized_exit_event():
    event = build_unauthorized_exit_event()
    assert event["asset_id"] == "A005"
    assert event["location"] == "MAIN_GATE"
    assert event["event_type"] == "GATE_SCAN"
    assert event["_expected_backend_status"] == "UNAUTHORIZED_EXIT"


def test_build_duplicate_events():
    ev1, ev2 = build_duplicate_events()
    assert ev1["message_id"] == ev2["message_id"]
    assert ev1["asset_id"] == ev2["asset_id"]
    assert ev1["_expected_backend_status"] == "NORMAL"
    assert ev2["_expected_backend_status"] == "DUPLICATE_IGNORED"


def test_build_malformed_event_negative_cases():
    raw_invalid = build_malformed_event("invalid_json")
    assert isinstance(raw_invalid, str)
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw_invalid)

    bad_zone = build_malformed_event("unrecognized_zone")
    assert bad_zone["location"] == "PARKING_LOT_OUTSIDE"

    no_loc = build_malformed_event("missing_location")
    assert "location" not in no_loc


def test_build_audit_cycle_events():
    events = build_audit_cycle_events(missing_aid="A004")
    assert len(events) == len(KNOWN_ASSETS) - 1
    aids = [e["asset_id"] for e in events]
    assert "A004" not in aids
    assert "A001" in aids
