# IoT-Based Smart Asset Tracking and Anomaly Detection System

A complete college capstone IoT project integrating physical/simulated asset detection, AWS IoT Core MQTT message broker, Flask backend with an intelligent anomaly detection engine, SQLite persistence, and a real-time React web dashboard.

---

## 1. Project Overview

In facilities such as corporate offices, warehouses, research labs, and hospital wings, critical assets must stay within designated storage zones. Misplaced items cause search delays, undetected missing items pose loss risks, and unauthorized removals through perimeter exit gates present security threats.

This system provides:
1. **Asset Registration & Storage Zone Mapping:** Register assets and assign expected zones (`SHELF_01`, `SHELF_02`, `SHELF_03`).
2. **Misplaced Asset Detection:** Flags assets detected in valid internal zones that differ from their expected zones.
3. **Scheduled Inventory Audits:** Distinguishes temporary signal absence from theft. Assets absent during formal audits are marked `MISSING_INVESTIGATION_REQUIRED`.
4. **Perimeter Gate Security & Authorization Verification:** Scans at `MAIN_GATE` are verified against database exit permits. Unauthorized attempts generate high/critical security alerts.
5. **Unknown Asset Detection:** Unrecognized RFIDs/tags trigger anomaly alerts.
6. **Hardware & Cloud Simulation Support:** Supports both Wokwi ESP32 firmware over AWS IoT Core and a web-based Demo Simulator for demonstration without hardware.

---

## 2. Technology Stack

- **Frontend:** React.js, Vite, JavaScript, Axios, Recharts, CSS.
- **Backend:** Python 3.11+, Flask, Flask-CORS, Paho-MQTT, python-dotenv, SQLite (`sqlite3`).
- **IoT & Cloud:** Wokwi ESP32 Simulator (Arduino C++), AWS IoT Core (MQTT over TLS v1.2, port 8883, X.509 mutual authentication).
- **Testing:** pytest for API, Anomaly Engine, and MQTT payload validation; Python unittest for historical test cases.

---

## 3. Project Directory Structure

```text
Asset  Tracking system/
├── .gitignore                  # Excludes node_modules, Python cache, certificates, and secrets
├── README.md                   # Main project overview and getting-started guide
├── Phase1/                     # Preserved original Phase 1 & 2 prototype scripts
├── backend/
│   ├── .env.example            # Environment variables template
│   ├── config.py               # Configuration constants and absolute database paths
│   ├── database.py             # SQLite helper with parameterized queries & auto-initialization
│   ├── anomaly_engine.py       # Core anomaly detection rule processor
│   ├── mqtt_subscriber.py      # Background Paho-MQTT client for AWS IoT Core
│   ├── app.py                  # Flask REST API server
│   ├── seed_data.py            # Sample assets, zones, and authorization seeder
│   ├── requirements.txt        # Backend Python dependencies
│   ├── certificates/
│   │   ├── README.md           # Instructions on placing AWS IoT Core X.509 certs
│   │   └── .gitkeep
│   └── tests/
│       ├── conftest.py         # Pytest fixtures and test database setup
│       ├── test_anomaly_engine.py # Rule classification tests
│       ├── test_api.py         # Flask REST API endpoint tests
│       └── test_mqtt_payload.py# MQTT schema validation and deduplication tests
├── frontend/
│   ├── package.json            # Vite & React dependencies
│   ├── vite.config.js          # Vite config with backend proxy
│   ├── index.html
│   └── src/
│       ├── App.jsx             # Main dashboard shell
│       ├── main.jsx            # Entry point
│       ├── index.css           # Styling
│       ├── api.js              # Axios REST client
│       └── components/         # Modular dashboard views
├── wokwi/
│   ├── diagram.json            # ESP32 circuit definition
│   ├── esp32_firmware.ino      # ESP32 firmware publishing TLS MQTT messages
│   └── secrets.h.example       # Template for WiFi & AWS X.509 credentials
└── docs/
    ├── ARCHITECTURE.md         # End-to-end dataflow & Mermaid diagrams
    ├── DATA_MODEL.md           # SQLite table schemas & entity relationships
    ├── API_AND_MQTT_SPEC.md    # REST API endpoints, status codes & MQTT format
    └── AWS_IOT_CORE_SETUP.md   # Step-by-step AWS IoT Core setup guide
```

---

## 4. Sample Assets & Testing Baseline

| Asset ID | Asset Name | Expected Zone | Default Exit Auth | Testing Scenario |
|---|---|---|---|---|
| `A001` | Laptop | `SHELF_01` | Authorized (1) | Normal zone detection / Authorized gate exit |
| `A002` | Monitor | `SHELF_01` | Unauthorized (0) | Misplaced scan at `SHELF_03` / Unauthorized exit alert at `MAIN_GATE` |
| `A003` | Keyboard | `SHELF_02` | Authorized (1) | Normal shelf scan |
| `A004` | Projector | `SHELF_02` | Authorized (1) | Gate scan with valid exit authorization |
| `A005` | Scanner | `SHELF_03` | Unauthorized (0) | Missing during audit $\rightarrow$ Unauthorized removal at gate |

---

## 5. Documentation Links

- [System Architecture & Sequence Flow](docs/ARCHITECTURE.md)
- [Database Schema & Entity Relationship](docs/DATA_MODEL.md)
- [REST API Endpoints & MQTT Specification](docs/API_AND_MQTT_SPEC.md)
- [AWS IoT Core Console Setup Guide](docs/AWS_IOT_CORE_SETUP.md)
