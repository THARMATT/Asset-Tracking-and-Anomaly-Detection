# ==========================================
# SYSTEM CONFIGURATION
# IoT-Based Smart Asset Tracking System
# ==========================================

import os
from pathlib import Path

# Try to load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    ENV_PATH = Path(__file__).resolve().parent / ".env"
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)
except ImportError:
    pass

# Stable absolute directory paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Database configuration
# Always resolves to an absolute path, defaulting inside the backend directory
_configured_db = os.environ.get("DATABASE_PATH")
if _configured_db:
    _configured_path = Path(_configured_db)
    if _configured_path.is_absolute():
        DATABASE_PATH = str(_configured_path)
    else:
        DATABASE_PATH = str((BACKEND_DIR / _configured_path).resolve())
else:
    DATABASE_PATH = str((BACKEND_DIR / "asset_tracking.db").resolve())

# Server configuration
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:5173")

# Predefined Zone Identifiers
MAIN_GATE = "MAIN_GATE"
SHELF_01 = "SHELF_01"
SHELF_02 = "SHELF_02"
SHELF_03 = "SHELF_03"

DEFAULT_ZONES = [
    (SHELF_01, "Storage Shelf 1 - IT Equipment", "STORAGE", "Designated rack for high-value laptops and monitors"),
    (SHELF_02, "Storage Shelf 2 - AV & Accessories", "STORAGE", "Designated rack for projectors and peripherals"),
    (SHELF_03, "Storage Shelf 3 - Warehouse Scanners", "STORAGE", "Designated rack for barcode scanners and handhelds"),
    (MAIN_GATE, "Main Perimeter Gate", "GATE", "Primary facility entrance and exit security checkpoint"),
]

# Consistent Asset Tracking & Anomaly Statuses
NORMAL = "NORMAL"
MISPLACED = "MISPLACED"
MISSING = "MISSING"
AUTHORIZED_EXIT = "AUTHORIZED_EXIT"
UNAUTHORIZED_EXIT = "UNAUTHORIZED_EXIT"
UNAUTHORIZED_REMOVAL = "UNAUTHORIZED_REMOVAL"
UNKNOWN_ASSET = "UNKNOWN_ASSET"
MISSING_INVESTIGATION = "MISSING_INVESTIGATION_REQUIRED"
INVALID_EVENT = "INVALID_EVENT"

# Predefined Recognized Zone Codes
RECOGNIZED_ZONES = {SHELF_01, SHELF_02, SHELF_03, MAIN_GATE}

# Standard Event Types
EVENT_TYPE_INTERNAL = "INTERNAL_SCAN"
EVENT_TYPE_GATE = "GATE_SCAN"
EVENT_TYPE_AUDIT = "AUDIT_SCAN"
EVENT_TYPE_MANUAL = "MANUAL_SIMULATION"
ALLOWED_EVENT_TYPES = {
    EVENT_TYPE_INTERNAL,
    EVENT_TYPE_GATE,
    EVENT_TYPE_AUDIT,
    EVENT_TYPE_MANUAL
}

# MQTT Broker Configuration (Local Mosquitto Default)
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "127.0.0.1")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", 1883))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "asset/events")
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "asset_tracking_subscriber")
MQTT_USERNAME = os.environ.get("MQTT_USERNAME") or None
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD") or None
MQTT_KEEPALIVE = int(os.environ.get("MQTT_KEEPALIVE", 60))
MQTT_QUEUE_MAXSIZE = int(os.environ.get("MQTT_QUEUE_MAXSIZE", 1000))
