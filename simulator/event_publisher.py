#!/usr/bin/env python3
"""
=============================================================================
IoT-Based Smart Asset Tracking and Anomaly Detection System
MQTT Event Publisher & Evaluation Scenario Simulator
=============================================================================

This simulator generates and publishes realistic RFID/IoT telemetry events
over MQTT to the local Mosquitto broker (topic: 'asset/events').
It supports 10 distinct operational scenarios spanning normal operations,
misplaced assets, perimeter security gate scans, duplicates, audits, and malformed inputs.

Usage examples (PowerShell):
  python simulator/event_publisher.py --scenario normal --count 5
  python simulator/event_publisher.py --scenario misplaced --count 2
  python simulator/event_publisher.py --scenario unauthorized_exit
  python simulator/event_publisher.py --scenario duplicate
  python simulator/event_publisher.py --scenario audit
  python simulator/event_publisher.py --scenario all
=============================================================================
"""

import argparse
import datetime
import json
import logging
import random
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print(
        "ERROR: 'paho-mqtt' is not installed in the current Python environment.\n"
        "Please install it using: pip install paho-mqtt\n"
        "Or use: backend\\venv\\Scripts\\python.exe simulator/event_publisher.py",
        file=sys.stderr,
    )
    sys.exit(1)


# =============================================================================
# DEFAULT CONFIGURATION & FACILITY CATALOG
# =============================================================================

DEFAULT_BROKER_HOST = "127.0.0.1"
DEFAULT_BROKER_PORT = 1883
DEFAULT_TOPIC = "asset/events"
DEFAULT_KEEPALIVE = 60

# Registered assets from the system database
KNOWN_ASSETS = {
    "A001": {"name": "Laptop", "expected_zone": "SHELF_01", "authorized_exit": True},
    "A002": {"name": "Monitor", "expected_zone": "SHELF_01", "authorized_exit": True},
    "A003": {"name": "Keyboard", "expected_zone": "SHELF_02", "authorized_exit": True},
    "A004": {"name": "Projector", "expected_zone": "SHELF_02", "authorized_exit": True},
    "A005": {"name": "Scanner", "expected_zone": "SHELF_03", "authorized_exit": False},
}

KNOWN_ZONES = ["SHELF_01", "SHELF_02", "SHELF_03", "MAIN_GATE"]
INTERNAL_STORAGE_ZONES = ["SHELF_01", "SHELF_02", "SHELF_03"]


def get_utc_iso_timestamp() -> str:
    """Generate ISO 8601 UTC timestamp format accepted by backend."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def generate_event_id() -> str:
    """Generate a unique event/message UUID."""
    return f"evt-{uuid.uuid4().hex[:12]}"


# =============================================================================
# SCENARIO BUILDERS
# =============================================================================

def build_normal_event(asset_id: Optional[str] = None) -> Dict[str, Any]:
    """Scenario 1: Normal scan at expected storage location."""
    aid = asset_id or random.choice(list(KNOWN_ASSETS.keys()))
    expected = KNOWN_ASSETS[aid]["expected_zone"]
    return {
        "message_id": generate_event_id(),
        "asset_id": aid,
        "location": expected,
        "event_type": "INTERNAL_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "1. Normal Scan (At Expected Location)",
        "_expected_backend_status": "NORMAL",
    }


def build_misplaced_event(asset_id: Optional[str] = None) -> Dict[str, Any]:
    """Scenario 2: Asset detected at a valid but wrong storage shelf."""
    aid = asset_id or random.choice(list(KNOWN_ASSETS.keys()))
    expected = KNOWN_ASSETS[aid]["expected_zone"]
    other_zones = [z for z in INTERNAL_STORAGE_ZONES if z != expected]
    wrong_zone = random.choice(other_zones)
    return {
        "message_id": generate_event_id(),
        "asset_id": aid,
        "location": wrong_zone,
        "event_type": "INTERNAL_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "2. Misplaced Asset (Wrong Shelf)",
        "_expected_backend_status": "MISPLACED",
    }


def build_unknown_asset_event() -> Dict[str, Any]:
    """Scenario 3: Unregistered asset detected in facility."""
    rand_id = f"ROGUE_{random.randint(100, 999)}"
    zone = random.choice(KNOWN_ZONES)
    return {
        "message_id": generate_event_id(),
        "asset_id": rand_id,
        "location": zone,
        "event_type": "GATE_SCAN" if zone == "MAIN_GATE" else "INTERNAL_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "3. Unknown Asset ID",
        "_expected_backend_status": "UNKNOWN_ASSET",
    }


def build_zone_movement_events(asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scenario 4: Asset moving consecutively through multiple valid zones."""
    aid = asset_id or "A001"
    zones = ["SHELF_01", "SHELF_02", "SHELF_03"]
    events = []
    for z in zones:
        events.append({
            "message_id": generate_event_id(),
            "asset_id": aid,
            "location": z,
            "event_type": "INTERNAL_SCAN",
            "timestamp": get_utc_iso_timestamp(),
            "_scenario": f"4. Asset Movement (Transition -> {z})",
            "_expected_backend_status": "NORMAL" if z == KNOWN_ASSETS[aid]["expected_zone"] else "MISPLACED",
        })
    return events


def build_authorized_exit_event() -> Dict[str, Any]:
    """Scenario 5: Asset with valid exit authorization scanned at MAIN_GATE."""
    # A001, A002, A003, A004 are authorized
    authorized_aids = [aid for aid, info in KNOWN_ASSETS.items() if info["authorized_exit"]]
    aid = random.choice(authorized_aids)
    return {
        "message_id": generate_event_id(),
        "asset_id": aid,
        "location": "MAIN_GATE",
        "event_type": "GATE_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "5. Authorized Gate Exit",
        "_expected_backend_status": "AUTHORIZED_EXIT",
    }


def build_unauthorized_exit_event() -> Dict[str, Any]:
    """Scenario 6: Asset WITHOUT exit authorization scanned at MAIN_GATE."""
    # A005 is strictly internal (authorized_exit = 0)
    aid = "A005"
    return {
        "message_id": generate_event_id(),
        "asset_id": aid,
        "location": "MAIN_GATE",
        "event_type": "GATE_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "6. SECURITY ALERT: Unauthorized Gate Exit",
        "_expected_backend_status": "UNAUTHORIZED_EXIT",
    }


def build_duplicate_events() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Scenario 7: Duplicate delivery with identical message_id to test idempotency."""
    shared_id = generate_event_id()
    aid = "A002"
    first = {
        "message_id": shared_id,
        "asset_id": aid,
        "location": "SHELF_01",
        "event_type": "INTERNAL_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "7A. Initial Event Delivery",
        "_expected_backend_status": "NORMAL",
    }
    second = {
        "message_id": shared_id,
        "asset_id": aid,
        "location": "SHELF_01",
        "event_type": "INTERNAL_SCAN",
        "timestamp": get_utc_iso_timestamp(),
        "_scenario": "7B. Duplicate Event Delivery (Idempotency Check)",
        "_expected_backend_status": "DUPLICATE_IGNORED",
    }
    return first, second


def build_malformed_event(case: str = "invalid_json") -> Any:
    """Scenario 8: Deliberate negative tests."""
    if case == "invalid_json":
        return "{MALFORMED_JSON_STRING: NOT_KEY_VAL, missing_bracket"
    elif case == "missing_location":
        return {
            "message_id": generate_event_id(),
            "asset_id": "A001",
            "timestamp": get_utc_iso_timestamp(),
            "_scenario": "8. Malformed Event (Missing Location)",
            "_expected_backend_status": "INVALID_EVENT",
        }
    elif case == "unrecognized_zone":
        return {
            "message_id": generate_event_id(),
            "asset_id": "A001",
            "location": "PARKING_LOT_OUTSIDE",
            "event_type": "INTERNAL_SCAN",
            "timestamp": get_utc_iso_timestamp(),
            "_scenario": "8. Malformed Event (Unrecognized Zone)",
            "_expected_backend_status": "INVALID_EVENT",
        }
    else:
        return {
            "message_id": generate_event_id(),
            "location": "SHELF_01",
            "timestamp": get_utc_iso_timestamp(),
            "_scenario": "8. Malformed Event (Missing asset_id)",
            "_expected_backend_status": "INVALID_EVENT",
        }


def build_audit_cycle_events(missing_aid: str = "A004") -> List[Dict[str, Any]]:
    """
    Scenario 9: Simulated inventory scan cycle where one expected asset
    is omitted to demonstrate missing-asset audit conditions.
    """
    present_aids = [aid for aid in KNOWN_ASSETS.keys() if aid != missing_aid]
    events = []
    for aid in present_aids:
        events.append({
            "message_id": generate_event_id(),
            "asset_id": aid,
            "location": KNOWN_ASSETS[aid]["expected_zone"],
            "event_type": "INTERNAL_SCAN",
            "timestamp": get_utc_iso_timestamp(),
            "_scenario": f"9. Inventory Audit Scan (Present: {aid}, Missing: {missing_aid})",
            "_expected_backend_status": "NORMAL",
        })
    return events


# =============================================================================
# MQTT PUBLISHER RUNNER
# =============================================================================

class EventPublisher:
    """Manages connection, formatting, and publication of events to Mosquitto."""

    def __init__(
        self,
        host: str = DEFAULT_BROKER_HOST,
        port: int = DEFAULT_BROKER_PORT,
        topic: str = DEFAULT_TOPIC,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = DEFAULT_KEEPALIVE,
    ):
        self.host = host
        self.port = port
        self.topic = topic
        self.client_id = client_id or f"simulator_pub_{uuid.uuid4().hex[:8]}"
        self.username = username
        self.password = password
        self.keepalive = keepalive

        self._connected = False
        self._client = self._init_client()

    def _init_client(self) -> mqtt.Client:
        # Compatibility with paho-mqtt v1 and v2
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
            )
        else:
            client = mqtt.Client(client_id=self.client_id)

        if self.username and self.password:
            client.username_pw_set(self.username, self.password)

        def on_connect(cli, userdata, flags, rc, properties=None):
            if rc == 0:
                self._connected = True
                print(f"[PUBLISHER] Successfully connected to MQTT Broker {self.host}:{self.port}")
            else:
                print(f"[PUBLISHER] Connection failed with return code: {rc}", file=sys.stderr)

        def on_disconnect(cli, userdata, *args):
            self._connected = False
            print("[PUBLISHER] Disconnected from MQTT Broker.")

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        return client

    def connect(self, timeout: float = 5.0) -> bool:
        """Connect to broker and start the network loop."""
        try:
            print(f"[PUBLISHER] Connecting to {self.host}:{self.port} (Client ID: {self.client_id})...")
            self._client.connect(self.host, self.port, keepalive=self.keepalive)
            self._client.loop_start()

            start_t = time.time()
            while not self._connected and (time.time() - start_t) < timeout:
                time.sleep(0.05)

            if not self._connected:
                print(f"[PUBLISHER ERROR] Could not connect to {self.host}:{self.port} within {timeout}s", file=sys.stderr)
                return False
            return True
        except Exception as exc:
            print(f"[PUBLISHER ERROR] Connection exception: {exc}", file=sys.stderr)
            return False

    def publish_payload(self, payload: Any, qos: int = 1) -> bool:
        """Publish a JSON or raw payload to the configured topic."""
        if not self._connected:
            print("[PUBLISHER ERROR] Cannot publish: Broker is not connected.", file=sys.stderr)
            return False

        scenario_name = "Custom Payload"
        expected_status = "N/A"
        clean_payload: Any = payload

        if isinstance(payload, dict):
            # Extract internal simulator tracking metadata before publishing
            scenario_name = payload.pop("_scenario", scenario_name)
            expected_status = payload.pop("_expected_backend_status", expected_status)
            payload_str = json.dumps(payload)
        else:
            payload_str = str(payload)

        try:
            msg_info = self._client.publish(self.topic, payload_str, qos=qos)
            msg_info.wait_for_publish(timeout=3.0)

            print("=" * 70)
            print(f"SCENARIO      : {scenario_name}")
            print(f"TOPIC         : {self.topic} (QoS {qos})")
            print(f"EXPECTED EVAL : {expected_status}")
            print(f"PAYLOAD       : {payload_str}")
            print(f"STATUS        : Published successfully (MID: {msg_info.mid})")
            print("=" * 70)
            return True
        except Exception as exc:
            print(f"[PUBLISHER ERROR] Publish failed: {exc}", file=sys.stderr)
            return False

    def close(self):
        """Disconnect cleanly and stop loop."""
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass


# =============================================================================
# CLI PARSER AND EXECUTION
# =============================================================================

AVAILABLE_SCENARIOS = [
    "normal",
    "misplaced",
    "unknown",
    "movement",
    "authorized_exit",
    "unauthorized_exit",
    "duplicate",
    "malformed",
    "audit",
    "mixed",
    "all",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MQTT Event Publisher & Anomaly Scenario Simulator for IoT Asset Tracking",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--broker", default=DEFAULT_BROKER_HOST, help="MQTT Broker host")
    parser.add_argument("--port", type=int, default=DEFAULT_BROKER_PORT, help="MQTT Broker port")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="MQTT topic to publish to")
    parser.add_argument(
        "--scenario",
        choices=AVAILABLE_SCENARIOS,
        default="normal",
        help="Scenario to simulate",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of events to publish (for repeating scenarios)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between consecutive events",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for deterministic demo runs",
    )
    parser.add_argument(
        "--malformed-case",
        choices=["invalid_json", "missing_location", "unrecognized_zone", "missing_asset_id"],
        default="unrecognized_zone",
        help="Type of malformed event to send (used only when --scenario malformed)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if args.seed is not None:
        random.seed(args.seed)
        print(f"[PUBLISHER] Set random seed to {args.seed}")

    publisher = EventPublisher(
        host=args.broker,
        port=args.port,
        topic=args.topic,
    )

    if not publisher.connect(timeout=5.0):
        print(f"Failed to connect to MQTT Broker at {args.broker}:{args.port}. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[PUBLISHER] Running scenario: '{args.scenario.upper()}' (Target Count: {args.count})\n")

    try:
        if args.scenario == "normal":
            for i in range(args.count):
                event = build_normal_event()
                publisher.publish_payload(event)
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "misplaced":
            for i in range(args.count):
                event = build_misplaced_event()
                publisher.publish_payload(event)
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "unknown":
            for i in range(args.count):
                event = build_unknown_asset_event()
                publisher.publish_payload(event)
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "movement":
            for _ in range(args.count):
                events = build_zone_movement_events()
                for i, ev in enumerate(events):
                    publisher.publish_payload(ev)
                    if i < len(events) - 1:
                        time.sleep(args.delay)

        elif args.scenario == "authorized_exit":
            for i in range(args.count):
                event = build_authorized_exit_event()
                publisher.publish_payload(event)
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "unauthorized_exit":
            for i in range(args.count):
                event = build_unauthorized_exit_event()
                publisher.publish_payload(event)
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "duplicate":
            ev1, ev2 = build_duplicate_events()
            print("[INFO] Sending first delivery:")
            publisher.publish_payload(ev1)
            time.sleep(args.delay)
            print("[INFO] Sending second delivery with same message_id:")
            publisher.publish_payload(ev2)

        elif args.scenario == "malformed":
            for i in range(args.count):
                event = build_malformed_event(args.malformed_case)
                publisher.publish_payload(event)
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "audit":
            for _ in range(args.count):
                events = build_audit_cycle_events(missing_aid="A004")
                for i, ev in enumerate(events):
                    publisher.publish_payload(ev)
                    if i < len(events) - 1:
                        time.sleep(args.delay)

        elif args.scenario == "mixed":
            # Round-robin mixture of real scenarios
            mix = [
                build_normal_event,
                build_misplaced_event,
                build_authorized_exit_event,
                build_unauthorized_exit_event,
                build_unknown_asset_event,
            ]
            for i in range(args.count):
                fn = mix[i % len(mix)]
                publisher.publish_payload(fn())
                if i < args.count - 1:
                    time.sleep(args.delay)

        elif args.scenario == "all":
            print(">>> Executing Full Demonstration of All Operational Scenarios <<<")
            all_steps = [
                ("1. Normal Scan", build_normal_event),
                ("2. Misplaced Asset", build_misplaced_event),
                ("3. Unknown Asset", build_unknown_asset_event),
                ("5. Authorized Exit", build_authorized_exit_event),
                ("6. Unauthorized Exit", build_unauthorized_exit_event),
            ]
            for name, fn in all_steps:
                print(f"\n--- Running: {name} ---")
                publisher.publish_payload(fn())
                time.sleep(args.delay)

            print("\n--- Running: 7. Duplicate Delivery Test ---")
            d1, d2 = build_duplicate_events()
            publisher.publish_payload(d1)
            time.sleep(args.delay)
            publisher.publish_payload(d2)
            time.sleep(args.delay)

            print("\n--- Running: 8. Malformed Payload Test (Unrecognized Zone) ---")
            publisher.publish_payload(build_malformed_event("unrecognized_zone"))

        print("\n[PUBLISHER] Scenario simulation finished.")
    except KeyboardInterrupt:
        print("\n[PUBLISHER] Interrupted by user. Exiting gracefully.")
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
