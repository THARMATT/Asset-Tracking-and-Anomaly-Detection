# ==========================================
# UNIT TESTS: MQTT SUBSCRIBER SERVICE
# ==========================================

import json
import pytest
from unittest.mock import MagicMock, patch

from mqtt_service import MQTTSubscriber
from database import get_events
from config import (
    NORMAL,
    MISPLACED,
    UNKNOWN_ASSET,
    INVALID_EVENT,
    SHELF_01,
    SHELF_02,
    SHELF_03,
    MAIN_GATE
)


@pytest.fixture
def subscriber(temp_db):
    """Provide a configured MQTTSubscriber instance targeting an isolated temp database."""
    sub = MQTTSubscriber(
        host="127.0.0.1",
        port=1883,
        topic="asset/events",
        db_path=temp_db,
        queue_maxsize=100,
    )
    yield sub
    sub.stop()


# ==========================================
# 1. PAYLOAD VALIDATION & PROCESSING TESTS
# ==========================================

def test_mqtt_valid_event_payload(subscriber, temp_db):
    """Verify that a valid JSON scan event is processed, classified as NORMAL, and persisted in SQLite."""
    payload = json.dumps({
        "asset_id": "A001",
        "location": SHELF_01,
        "message_id": "mqtt-msg-valid-001",
        "event_type": "INTERNAL_SCAN",
        "timestamp": "2026-10-23T12:00:00Z"
    })

    result = subscriber.process_incoming_payload(payload)

    assert result is not None
    assert result["status"] == NORMAL
    assert result["asset_id"] == "A001"
    assert result["detected_zone"] == SHELF_01
    assert result["persistence"]["duplicate"] is False

    # Check persistence in database
    events = get_events(asset_id="A001", db_path=temp_db)
    assert events["total_count"] == 1
    assert events["items"][0]["status"] == NORMAL
    assert events["items"][0]["message_id"] == "mqtt-msg-valid-001"


def test_mqtt_invalid_json(subscriber):
    """Malformed non-JSON strings or byte arrays must be rejected without raising exceptions."""
    # Test malformed string
    res1 = subscriber.process_incoming_payload("{corrupted json not closed")
    assert res1["status"] == INVALID_EVENT
    assert "Malformed JSON" in res1["error"]

    # Test raw non-UTF8 bytes
    res2 = subscriber.process_incoming_payload(b"\xff\xfe\x00\x00badbytes")
    assert res2["status"] == INVALID_EVENT
    assert "not valid UTF-8" in res2["error"]

    # Test non-dictionary JSON (e.g. JSON array or int)
    res3 = subscriber.process_incoming_payload(json.dumps(["not", "a", "dictionary"]))
    assert res3["status"] == INVALID_EVENT
    assert "must be an object/dictionary" in res3["error"]


def test_mqtt_missing_asset_id(subscriber):
    """Payloads without an asset_id or with blank whitespace must be rejected."""
    # Missing key completely
    res1 = subscriber.process_incoming_payload(json.dumps({"location": SHELF_01}))
    assert res1["status"] == INVALID_EVENT
    assert "Missing mandatory field: 'asset_id'" in res1["error"]

    # Empty whitespace
    res2 = subscriber.process_incoming_payload(json.dumps({"asset_id": "   ", "location": SHELF_01}))
    assert res2["status"] == INVALID_EVENT
    assert "'asset_id' cannot be blank" in res2["error"]


def test_mqtt_invalid_zone(subscriber):
    """Payloads referencing an unrecognized facility zone must be rejected."""
    payload = json.dumps({
        "asset_id": "A001",
        "location": "ROOFTOP_PARKING_ZONE",
        "message_id": "msg-bad-zone"
    })
    result = subscriber.process_incoming_payload(payload)
    assert result["status"] == INVALID_EVENT
    assert "Unrecognized zone 'ROOFTOP_PARKING_ZONE'" in result["error"]


def test_mqtt_invalid_event_type(subscriber):
    """Payloads specifying an unsupported event type must be rejected."""
    payload = json.dumps({
        "asset_id": "A001",
        "location": SHELF_01,
        "event_type": "UNSUPPORTED_DRONE_SCAN"
    })
    result = subscriber.process_incoming_payload(payload)
    assert result["status"] == INVALID_EVENT
    assert "Unsupported event_type 'UNSUPPORTED_DRONE_SCAN'" in result["error"]


def test_mqtt_unknown_asset(subscriber, temp_db):
    """Scans for uncataloged tags must be classified as UNKNOWN_ASSET and persisted cleanly."""
    payload = json.dumps({
        "asset_id": "UNKNOWN_TAG_777",
        "location": SHELF_02,
        "message_id": "mqtt-unknown-001"
    })
    result = subscriber.process_incoming_payload(payload)

    assert result["status"] == UNKNOWN_ASSET
    assert result["asset_id"] == "UNKNOWN_TAG_777"
    assert result["persistence"]["event_id"] is not None

    # Check database
    events = get_events(asset_id="UNKNOWN_TAG_777", db_path=temp_db)
    assert events["total_count"] == 1
    assert events["items"][0]["status"] == UNKNOWN_ASSET


def test_mqtt_duplicate_event_id_deduplication(subscriber, temp_db):
    """Repeated delivery of the same message_id must be handled idempotently without duplicate rows."""
    payload = json.dumps({
        "asset_id": "A002",
        "location": SHELF_03,
        "message_id": "dedup-uuid-exact-match"
    })

    # First delivery
    res1 = subscriber.process_incoming_payload(payload)
    assert res1["status"] == MISPLACED
    assert res1["persistence"]["duplicate"] is False
    first_event_id = res1["persistence"]["event_id"]

    # Duplicate delivery
    res2 = subscriber.process_incoming_payload(payload)
    assert res2["status"] == MISPLACED
    assert res2["persistence"]["duplicate"] is True
    assert res2["persistence"]["event_id"] == first_event_id

    # Verify SQLite row count remains 1
    events = get_events(asset_id="A002", db_path=temp_db)
    assert events["total_count"] == 1


def test_mqtt_timestamp_validation(subscriber):
    """Valid ISO timestamps are preserved; malformed timestamps are safely rejected."""
    # Valid ISO timestamp
    valid_res = subscriber.process_incoming_payload(json.dumps({
        "asset_id": "A001",
        "location": SHELF_01,
        "timestamp": "2026-10-23T15:30:00+00:00"
    }))
    assert valid_res["status"] == NORMAL

    # Malformed timestamp
    bad_res = subscriber.process_incoming_payload(json.dumps({
        "asset_id": "A001",
        "location": SHELF_01,
        "timestamp": "yesterday afternoon at 3pm"
    }))
    assert bad_res["status"] == INVALID_EVENT
    assert "Invalid ISO 8601 timestamp" in bad_res["error"]


# ==========================================
# 2. QUEUE & NETWORK LIFECYCLE TESTS (MOCKED)
# ==========================================

def test_on_message_queuing_and_worker_consumption(subscriber, temp_db):
    """Verify that _on_message enqueues raw data and the background worker processes it asynchronously."""
    # Start the worker thread without real broker network connection
    subscriber._stop_event.clear()
    subscriber._is_running = True
    import threading
    worker = threading.Thread(target=subscriber._process_queue_worker, daemon=True)
    worker.start()

    # Simulate Paho message object
    mock_msg = MagicMock()
    mock_msg.topic = "asset/events"
    mock_msg.payload = json.dumps({
        "asset_id": "A003",
        "location": SHELF_02,
        "message_id": "worker-queue-test-msg"
    }).encode("utf-8")

    subscriber._on_message(subscriber.client, None, mock_msg)

    # Wait for queue to drain
    subscriber.event_queue.join()
    subscriber._stop_event.set()
    worker.join(timeout=2.0)

    # Verify event was persisted in database by the worker
    events = get_events(asset_id="A003", db_path=temp_db)
    assert events["total_count"] == 1
    assert events["items"][0]["status"] == NORMAL


def test_broker_disconnect_and_reconnect_simulation(subscriber):
    """Verify that on_connect and on_disconnect correctly update connection state without crashing."""
    assert subscriber.is_connected is False

    # Simulate successful on_connect callback (Paho 2.x reason_code 0)
    mock_rc = MagicMock()
    mock_rc.is_failure = False
    mock_rc.value = 0
    subscriber._on_connect(subscriber.client, None, {}, mock_rc)
    assert subscriber.is_connected is True

    # Simulate unexpected disconnection
    subscriber._on_disconnect(subscriber.client, None, {}, 1)
    assert subscriber.is_connected is False


def test_lifecycle_start_and_graceful_stop(subscriber):
    """Verify start() and stop() methods manage worker thread and client gracefully."""
    with patch.object(subscriber.client, "connect"):
        with patch.object(subscriber.client, "loop_start"):
            with patch.object(subscriber.client, "loop_stop"):
                subscriber.start()
                assert subscriber.is_running is True

                subscriber.stop()
                assert subscriber.is_running is False
