# ==========================================
# MQTT SUBSCRIBER SERVICE
# IoT-Based Smart Asset Tracking System
# ==========================================

import json
import logging
import queue
import threading
import time
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Set

import paho.mqtt.client as mqtt

# Ensure backend root is importable if executed standalone
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC,
    MQTT_CLIENT_ID,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    MQTT_KEEPALIVE,
    MQTT_QUEUE_MAXSIZE,
    DATABASE_PATH,
    ALLOWED_EVENT_TYPES,
    MAIN_GATE,
    EVENT_TYPE_INTERNAL,
    EVENT_TYPE_GATE,
    INVALID_EVENT
)
from database import get_utc_now, get_recognized_zones
from anomaly_engine import process_and_save_scan_event

logger = logging.getLogger("MQTTSubscriber")


class MQTTSubscriber:
    """
    Robust, production-ready MQTT Subscriber Service.
    - Subscribes to asset tracking topics on the local or configured broker.
    - Decouples network I/O from database transactions using a bounded queue.
    - Performs strict schema and value validation on incoming JSON payloads.
    - Routes valid events through the shared anomaly detection and deduplication engine.
    - Implements graceful shutdown, reconnect handling, and thread safety.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        topic: Optional[str] = None,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: Optional[int] = None,
        db_path: Optional[str] = None,
        queue_maxsize: Optional[int] = None,
    ):
        self.host = host or MQTT_BROKER_HOST
        self.port = int(port or MQTT_BROKER_PORT)
        self.topic = topic or MQTT_TOPIC
        self.client_id = client_id or f"{MQTT_CLIENT_ID}_{uuid.uuid4().hex[:8]}"
        self.username = username or MQTT_USERNAME
        self.password = password or MQTT_PASSWORD
        self.keepalive = int(keepalive or MQTT_KEEPALIVE)
        self.db_path = db_path or DATABASE_PATH
        self.queue_maxsize = int(queue_maxsize or MQTT_QUEUE_MAXSIZE)

        # Bounded event queue to keep MQTT network callbacks lightweight
        self.event_queue: queue.Queue = queue.Queue(maxsize=self.queue_maxsize)

        # Threading and lifecycle management
        self._is_running = False
        self._is_connected = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._lifecycle_lock = threading.Lock()

        # Operational metrics
        self.metrics = {
            "events_received": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "validation_errors": 0,
            "duplicates_detected": 0,
            "last_event_time": None,
        }

        # Initialize Paho MQTT client with version-aware API
        self.client = self._create_mqtt_client()

    def _create_mqtt_client(self) -> mqtt.Client:
        """Create and configure the Paho MQTT client instance."""
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
                clean_session=True,
            )
        else:
            client = mqtt.Client(client_id=self.client_id, clean_session=True)

        if self.username:
            client.username_pw_set(self.username, self.password)

        # Attach callbacks
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.on_subscribe = self._on_subscribe

        # Reconnect backoff configuration
        client.reconnect_delay_set(min_delay=1, max_delay=60)
        return client

    # ==========================================
    # 1. MQTT NETWORK CALLBACKS
    # ==========================================

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Callback triggered upon establishing broker connection."""
        is_success = False
        if hasattr(reason_code, "is_failure"):
            is_success = not reason_code.is_failure
            rc_code = reason_code.value
        else:
            is_success = (reason_code == 0)
            rc_code = reason_code

        if is_success:
            self._is_connected = True
            logger.info(f"Connected to MQTT broker at {self.host}:{self.port} (RC={rc_code})")
            client.subscribe(self.topic, qos=1)
        else:
            self._is_connected = False
            logger.error(f"MQTT connection failed to {self.host}:{self.port} with code: {rc_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code=None, properties=None):
        """Callback triggered when disconnected from broker."""
        self._is_connected = False
        rc_info = reason_code if reason_code is not None else disconnect_flags
        if self._stop_event.is_set():
            logger.info("MQTT client disconnected cleanly during shutdown.")
        else:
            logger.warning(f"MQTT unexpected disconnection from broker (Reason: {rc_info}). Auto-reconnect active.")

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties=None):
        """Callback triggered when broker confirms topic subscription."""
        logger.info(f"Subscribed successfully to topic: '{self.topic}' (MID={mid})")

    def _on_message(self, client, userdata, message):
        """
        Lightweight message callback:
        Puts raw message tuple into bounded queue without blocking network loop.
        """
        self.metrics["events_received"] += 1
        try:
            self.event_queue.put_nowait((message.topic, message.payload))
        except queue.Full:
            self.metrics["events_dropped"] += 1
            logger.error(
                f"MQTT event queue overflow (capacity={self.queue_maxsize}). "
                "Dropping oldest/incoming event to prevent memory starvation."
            )

    # ==========================================
    # 2. SCHEMA & PAYLOAD VALIDATION
    # ==========================================

    def validate_payload(
        self, raw_payload: Any, custom_zones: Optional[Set[str]] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Strictly validate payload format, types, required fields, and values.
        Returns: (is_valid, error_reason, sanitized_payload)
        """
        # Step A: Parse raw bytes/string to JSON dictionary
        if isinstance(raw_payload, (bytes, bytearray)):
            try:
                decoded_str = raw_payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                return False, f"Payload is not valid UTF-8: {exc}", None
        elif isinstance(raw_payload, str):
            decoded_str = raw_payload
        elif isinstance(raw_payload, dict):
            decoded_str = None
            data = raw_payload
        else:
            return False, "Payload must be a JSON string, bytes, or dictionary", None

        if decoded_str is not None:
            try:
                data = json.loads(decoded_str)
            except json.JSONDecodeError as exc:
                return False, f"Malformed JSON syntax: {exc}", None

        if not isinstance(data, dict):
            return False, "Parsed JSON payload must be an object/dictionary", None

        # Step B: Required Asset ID validation
        raw_asset_id = data.get("asset_id")
        if raw_asset_id is None:
            return False, "Missing mandatory field: 'asset_id'", None

        asset_id_str = str(raw_asset_id).strip()
        if not asset_id_str:
            return False, "'asset_id' cannot be blank or empty whitespace", None

        if len(asset_id_str) > 128:
            return False, "'asset_id' exceeds maximum length of 128 characters", None

        # Step C: Location / Detected Zone validation
        raw_location = data.get("location") or data.get("detected_zone") or data.get("zone")
        if raw_location is None:
            return False, "Missing mandatory location field: 'location' or 'detected_zone'", None

        location_str = str(raw_location).strip()
        if not location_str:
            return False, "'location' cannot be blank or empty whitespace", None

        if len(location_str) > 64:
            return False, "'location' exceeds maximum length of 64 characters", None

        recognized_zones = custom_zones or get_recognized_zones(db_path=self.db_path)
        if location_str not in recognized_zones:
            return (
                False,
                f"Unrecognized zone '{location_str}'. Must be one of: {sorted(list(recognized_zones))}",
                None,
            )

        # Step D: Event Type validation
        raw_event_type = data.get("event_type")
        if raw_event_type is not None:
            event_type_str = str(raw_event_type).strip()
            if event_type_str not in ALLOWED_EVENT_TYPES:
                return (
                    False,
                    f"Unsupported event_type '{event_type_str}'. Allowed: {sorted(list(ALLOWED_EVENT_TYPES))}",
                    None,
                )
        else:
            event_type_str = EVENT_TYPE_GATE if location_str == MAIN_GATE else EVENT_TYPE_INTERNAL

        # Step E: Timestamp validation (ISO 8601)
        raw_timestamp = data.get("timestamp")
        if raw_timestamp is not None:
            timestamp_str = str(raw_timestamp).strip()
            try:
                # Accept ISO 8601 with Z or timezone offset
                iso_clean = timestamp_str.replace("Z", "+00:00")
                datetime.fromisoformat(iso_clean)
            except (ValueError, TypeError):
                return False, f"Invalid ISO 8601 timestamp: '{timestamp_str}'", None
        else:
            timestamp_str = get_utc_now()

        # Step F: Message ID (UUID for deduplication)
        raw_msg_id = data.get("message_id")
        message_id_str = str(raw_msg_id).strip() if raw_msg_id is not None else None

        sanitized = {
            "asset_id": asset_id_str,
            "location": location_str,
            "detected_zone": location_str,
            "event_type": event_type_str,
            "message_id": message_id_str,
            "timestamp": timestamp_str,
            "source": data.get("source", "MQTT_CLIENT"),
            "raw_payload": data,
        }

        return True, None, sanitized

    # ==========================================
    # 3. BACKGROUND WORKER & PROCESSING
    # ==========================================

    def _process_queue_worker(self):
        """Worker thread loop to consume events and execute database transactions."""
        logger.info("MQTT background worker thread started.")

        while not self._stop_event.is_set():
            try:
                topic, payload = self.event_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._handle_single_event(topic, payload)
            except Exception as exc:
                logger.error(f"Unexpected error processing MQTT message from {topic}: {exc}", exc_info=True)
            finally:
                self.event_queue.task_done()

        logger.info("MQTT background worker thread exited cleanly.")

    def _handle_single_event(self, topic: str, raw_payload: Any) -> Optional[Dict[str, Any]]:
        """Validate, process, and persist a single MQTT message."""
        is_valid, error_reason, sanitized = self.validate_payload(raw_payload)

        if not is_valid:
            self.metrics["validation_errors"] += 1
            logger.warning(f"MQTT message rejected on {topic}: {error_reason}")
            return {"status": INVALID_EVENT, "error": error_reason}

        # Process through shared anomaly engine and persist into database
        processed = process_and_save_scan_event(sanitized, db_path=self.db_path)
        self.metrics["events_processed"] += 1
        self.metrics["last_event_time"] = get_utc_now()

        persistence = processed.get("persistence", {})
        if persistence.get("duplicate"):
            self.metrics["duplicates_detected"] += 1
            logger.info(
                f"[MQTT DEDUP] Event '{sanitized.get('message_id')}' already recorded. "
                f"Skipped duplicate insert."
            )
        else:
            logger.info(
                f"[MQTT PROCESSED] Asset: {processed.get('asset_id')} | "
                f"Zone: {processed.get('detected_zone')} | "
                f"Status: {processed.get('status')} | "
                f"EventID: {persistence.get('event_id')}"
            )

        return processed

    def process_incoming_payload(self, raw_payload: Any) -> Optional[Dict[str, Any]]:
        """
        Public synchronous processing interface (ideal for unit testing and direct invocation).
        """
        return self._handle_single_event(self.topic, raw_payload)

    # ==========================================
    # 4. LIFECYCLE CONTROLS (START / STOP)
    # ==========================================

    def start(self, block: bool = False):
        """Start the background worker thread and connect the MQTT network client."""
        with self._lifecycle_lock:
            if self._is_running:
                logger.warning("MQTT Subscriber is already running.")
                return

            self._stop_event.clear()
            self._is_running = True

            # Start queue worker daemon thread
            self._worker_thread = threading.Thread(
                target=self._process_queue_worker,
                name="MQTT-Event-Worker",
                daemon=True,
            )
            self._worker_thread.start()

            # Connect network loop
            try:
                logger.info(f"Connecting to MQTT broker at {self.host}:{self.port}...")
                self.client.connect(self.host, self.port, keepalive=self.keepalive)
                self.client.loop_start()
            except Exception as exc:
                logger.error(f"Could not connect to MQTT broker ({self.host}:{self.port}): {exc}")
                # We do not crash the host process; auto-reconnect handles eventual connection

        if block:
            try:
                while self._is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received. Stopping subscriber...")
                self.stop()

    def stop(self, timeout: float = 5.0):
        """Gracefully stop MQTT loop, disconnect client, and terminate worker thread."""
        with self._lifecycle_lock:
            if not self._is_running:
                return

            logger.info("Shutting down MQTT Subscriber service...")
            self._stop_event.set()

            # Disconnect and stop Paho loop
            try:
                self.client.loop_stop()
                if self._is_connected:
                    self.client.disconnect()
            except Exception as exc:
                logger.error(f"Error during MQTT client disconnect: {exc}")

            self._is_connected = False

            # Wait for worker thread to finish processing in-flight queue items
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=timeout)
                self._worker_thread = None

            self._is_running = False
            logger.info("MQTT Subscriber service stopped.")

    @property
    def is_connected(self) -> bool:
        """Return True if currently connected to the broker."""
        return self._is_connected

    @property
    def is_running(self) -> bool:
        """Return True if the service worker thread is active."""
        return self._is_running

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# ==========================================
# 5. STANDALONE SERVICE EXECUTION
# ==========================================

def run_standalone_subscriber():
    """Run the subscriber as a standalone process with graceful termination handling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Initializing standalone Asset Tracking MQTT Subscriber...")
    subscriber = MQTTSubscriber()

    def handle_signal(sig, frame):
        logger.info("Signal caught, initiating graceful shutdown...")
        subscriber.stop()
        sys.exit(0)

    import signal
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    subscriber.start(block=True)


if __name__ == "__main__":
    run_standalone_subscriber()
