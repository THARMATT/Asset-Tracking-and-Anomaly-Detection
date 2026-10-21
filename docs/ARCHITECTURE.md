# System Architecture & Technical Specification

**Project:** IoT-Based Smart Asset Tracking and Anomaly Detection System  
**Level:** Senior College / Capstone IoT Project  
**Date:** October 2026  

---

## 1. High-Level System Architecture

The system provides continuous visibility, physical location verification, and anomaly detection for critical physical assets across predefined facility zones.

```mermaid
flowchart TD
    subgraph IoT_Layer ["1. IoT Edge Simulation Layer"]
        WOKWI["Wokwi ESP32 Simulator<br/>(Arduino C++ / WiFiClientSecure)"]
        TAGS["Simulated Asset Tags / Events<br/>(RFID / BLE Emulation)"]
        TAGS -->|Generate Scans| WOKWI
    end

    subgraph Cloud_Broker ["2. Cloud Message Broker"]
        AWS_IOT["AWS IoT Core Message Broker<br/>(MQTT over TLS / Port 8883 / X.509)"]
        TOPIC["Topic: assets/tracking/events"]
        AWS_IOT --- TOPIC
    end

    subgraph Backend_Layer ["3. Backend Processing & Analytics Layer"]
        SUBSCRIBER["Flask Paho-MQTT Subscriber<br/>(Background Thread / Client mTLS)"]
        DEDUP["Message Deduplication & Validator<br/>(message_id check + ISO 8601 validation)"]
        ENGINE["Anomaly Detection Engine<br/>- Misplaced Asset Check<br/>- Gate Exit Authorization<br/>- Scheduled Inventory Audit<br/>- Unknown Asset Detection"]
        DB[(SQLite Database<br/>Thread-Safe / Parameterized SQL)]
        REST_API["Flask REST API<br/>(/api/assets, /api/events, /api/alerts, /api/audit)"]
        SIMULATOR["Demo Event Simulator<br/>(Physical Hardware Bypass Mode)"]
    end

    subgraph Frontend_Layer ["4. Presentation & Operations Layer"]
        REACT["React.js + Vite Web Dashboard"]
        COMPONENTS["Dashboard Widgets<br/>- Real-time Status Cards<br/>- Zone Visualization & Charts<br/>- Exit Authorization Switcher<br/>- Searchable Event History<br/>- Security Alert Resolution<br/>- Audit Execution Controls"]
        REACT --- COMPONENTS
    end

    %% Data Flow Connections
    WOKWI -->|MQTT Publish via TLS/X.509| AWS_IOT
    TOPIC -->|MQTT Subscribe via TLS/X.509| SUBSCRIBER
    SUBSCRIBER --> DEDUP
    SIMULATOR -->|Direct Test Event| DEDUP
    DEDUP --> ENGINE
    ENGINE -->|Store Events & Alerts| DB
    REST_API -->|Read/Write Operations| DB
    REACT -->|Axios REST Calls (Polling/Refresh)| REST_API
```

---

## 2. End-to-End Data Flow Stages

### Stage 1: Asset Detection at Edge (Wokwi ESP32)
1. Physical asset tags (simulated RFID / BLE) are detected at reader checkpoints (e.g. `SHELF_01`, `SHELF_02`, `SHELF_03`, or `MAIN_GATE`).
2. ESP32 microcontroller establishes a secure TLS connection to AWS IoT Core using mutual X.509 certificates.
3. The microcontroller formats a JSON detection payload with a unique `message_id`, `asset_id`, `location`, `timestamp`, and `event_type`.
4. It publishes the event to topic `assets/tracking/events` with MQTT QoS 1.

### Stage 2: Ingestion & Cloud Broker (AWS IoT Core)
1. AWS IoT Core validates the client certificate against its registered Thing and attached IoT Policy.
2. The broker routes messages published on `assets/tracking/events` to all subscribed clients.

### Stage 3: Ingestion & Deduplication (Flask Backend)
1. A persistent Paho-MQTT subscriber running on a background daemon thread maintains a TLS connection to AWS IoT Core.
2. When a payload arrives:
   - Payload is validated against JSON schema rules (type checks, mandatory fields). Malformed payloads are logged and discarded without crashing the service.
   - Idempotency check: Backend verifies `message_id` against previously processed messages in SQLite. Duplicate packets (e.g. caused by MQTT QoS 1 re-transmissions) are safely ignored.

### Stage 4: Anomaly Detection Engine
The validated scan event is evaluated against operational and security rules:
- **Misplaced Asset Detection:** If `location != expected_zone` (for internal zones), status is flagged as `MISPLACED`.
- **Main Gate Authorization:** If `location == MAIN_GATE`, the system queries the `authorization` table for the asset's exit permission:
  - If authorized $\rightarrow$ Status: `AUTHORIZED_EXIT`.
  - If unauthorized $\rightarrow$ Status: `UNAUTHORIZED_EXIT`, generating a `HIGH` severity alert.
  - If the asset was previously marked missing and arrives at the gate unauthorized $\rightarrow$ Status: `UNAUTHORIZED_REMOVAL`, generating a `CRITICAL` severity alert.
- **Unknown Asset Detection:** If an `asset_id` is received that does not exist in the database $\rightarrow$ Status: `UNKNOWN_ASSET`, generating a `MEDIUM` severity alert.
- **Scheduled Inventory Audit:** Missing items are **never** declared stolen based on a single absent scan. When an automated or manual inventory audit runs:
  - Registered assets not detected within the audit window are marked `MISSING_INVESTIGATION_REQUIRED`.
  - An investigative alert is opened for warehouse staff verification.

### Stage 5: Persistent Storage (SQLite)
All events, alert notifications, asset records, and audit logs are stored in SQLite using parameterized queries to eliminate SQL injection vulnerabilities.

### Stage 6: React Web Dashboard
1. The React frontend fetches real-time state, metrics, and alerts via Axios from Flask REST API endpoints.
2. Operators can monitor assets on charts, view misplaced alerts, toggle exit authorizations, trigger scheduled audits, and use the built-in simulator for demonstration.

---

## 3. Anomaly Decision Matrix

| Detection Location | Registered? | Expected Zone Match | Exit Authorized? | Previous Status | Evaluated Status | Alert Generated? |
|---|---|---|---|---|---|---|
| Internal Zone (`SHELF_01`, etc.) | Yes | Yes | N/A | Any | `NORMAL` | No |
| Internal Zone (`SHELF_03`) | Yes | No (`SHELF_01`) | N/A | Any | `MISPLACED` | Yes (Low/Medium) |
| `MAIN_GATE` | Yes | N/A | Yes | Any | `AUTHORIZED_EXIT` | No |
| `MAIN_GATE` | Yes | N/A | No | `NORMAL` / `MISPLACED` | `UNAUTHORIZED_EXIT` | Yes (High) |
| `MAIN_GATE` | Yes | N/A | No | `MISSING` | `UNAUTHORIZED_REMOVAL` | Yes (Critical) |
| Any Location | No | N/A | N/A | N/A | `UNKNOWN_ASSET` | Yes (Medium) |
| Audit (Not Detected) | Yes | N/A | N/A | Any | `MISSING_INVESTIGATION_REQUIRED`| Yes (Medium) |

---

## 4. Fault Tolerance & Reliability Design

1. **Broker Isolation & Loose Coupling:** The Flask application does not depend on immediate ESP32 availability. The demo simulator allows comprehensive testing when AWS credentials or physical networks are unavailable.
2. **Crash-Resilient MQTT Consumer:** The MQTT subscriber handles connection drops with automatic exponential backoff reconnection.
3. **Graceful Malformed Payload Handling:** Try-except wrappers around JSON deserialization and schema validation ensure corrupted packets are logged without terminating the worker thread.
4. **Idempotency via `message_id`:** Network retries from IoT edge devices will not duplicate event records or create false duplicate alerts.
