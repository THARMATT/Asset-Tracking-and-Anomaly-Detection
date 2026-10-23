# System Architecture & Component Specification
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Version:** 2.0.0  
**Updated:** 2026-10-24  
**Classification:** M.Tech Capstone Project Architecture  

---

## 1. System Overview & Problem Statement

In enterprise environments (e.g., healthcare equipment rooms, IT data centers, manufacturing warehouses), high-value mobile equipment is frequently moved between physical locations. Traditional barcode scanners or basic relational database inventory tables maintain static "last known location" fields. However, static inventory records cannot:
1. Prevent unauthorized exit through perimeter security gates.
2. Differentiate between expected physical relocations and misplaced assets.
3. Automatically correlate RFID reader scan streams with temporal exit permits in real-time.
4. Detect inventory shrinkage without labor-intensive manual physical audits.

This project implements an end-to-end, edge-to-dashboard solution combining **IoT telemetry transport (MQTT/Mosquitto)**, a **dual-layer anomaly detection engine**, an **idempotent transactional persistence store (SQLite)**, and an **interactive single-page dashboard (React/Vite)**.

---

## 2. Component Architecture Diagram

```text
[ Physical / Simulated Edge Tier ]
   ├── Wokwi ESP32 Node (WiFi + PubSubClient + pushbuttons + status LEDs)
   ├── Python CLI Event Simulator (simulator/event_publisher.py, 10 scenarios)
   └── In-Browser React Simulator (REST POST /api/events)
                   │
                   │ MQTT (QoS 1, topic: 'asset/events')
                   ▼
[ Message Transport Tier ]
   └── Eclipse Mosquitto Broker v2.0 (localhost:1883)
                   │
                   │ Paho MQTT Subscriber (Callback API v2)
                   ▼
[ Application Backend Tier (Flask 3.1 + Python 3.11) ]
   ├── MQTT Subscriber Service (backend/mqtt_service.py)
   │     └── Bounded Queue (maxsize=1000) -> Worker Thread
   ├── Dual-Layer Anomaly Engine:
   │     ├── Layer 1: Deterministic Security & Zone Rules (backend/anomaly_engine.py)
   │     │     ├── Normal Expected Zone Verification
   │     │     ├── Misplaced Asset Anomaly Detection
   │     │     ├── Perimeter Exit Permit Verification (Expired, Revoked, Missing)
   │     │     ├── Unregistered / Unknown RFID Tag Classification
   │     │     └── Scheduled Inventory Audit & Discrepancy Reconciliation
   │     └── Layer 2: Experimental Movement-Pattern Analysis (backend/ml_anomaly.py)
   │           └── Isolation Forest Unsupervised Model (8 movement dynamics features)
   ├── REST API Service (12 endpoints for assets, zones, events, authorizations, audits)
   └── Persistence Tier:
         └── SQLite 3.40 (backend/asset_tracking.db, WAL Mode, FK enforced, partial indexes)
                   │
                   │ HTTP / REST (JSON API, CORS restricted)
                   ▼
[ Presentation Tier (React 18 + Vite + Tailwind/CSS) ]
   ├── Near-Real-Time Auto-Polling (5s / 10s / 30s with request-overlap guard)
   ├── System Overview Dashboard (Summary cards, alert banners, distribution charts)
   ├── Physical Asset Inventory Table (Search, zone filters, gate permit toggles)
   ├── Event History & Telemetry Log (Pagination, status filters, zone filters)
   ├── Scheduled Inventory Audit Console (Trigger audits, view discrepancy reports)
   └── Interactive Scan Event Simulator (Trigger test scans directly from UI)
```

---

## 3. Communication Protocols and Boundaries

| Transport | Source | Destination | Protocol / Payload | Serialization | Security / Boundary |
|:---|:---|:---|:---|:---:|:---|
| Edge Telemetry | ESP32 / CLI Simulator | Mosquitto Broker | MQTT v3.1.1 (Port 1883) | JSON | Localhost / LAN subnet |
| Ingestion Bridge | Mosquitto Broker | Flask Subscriber | MQTT TCP Loopback | JSON | Local process boundary |
| Dashboard Data | React Frontend | Flask Backend | HTTP REST (Port 5000) | JSON | CORS restricted origin |
| Persistence | Flask App | SQLite File Store | C-ABI Native Bindings | Relational / WAL | Local file system |

---

## 4. Subsystem Details

### 4.1 Message Transport & Ingestion (MQTT)
- Topic: `asset/events`
- Broker: Eclipse Mosquitto v2.0.22
- Subscriber: Background worker thread decoupled from network socket callbacks using a `queue.Queue(maxsize=1000)` buffer.
- Resilience: Reconnects automatically using exponential backoff (1s to 60s).

### 4.2 Layer 1 Anomaly Engine
The deterministic rule precedence operates in strict order:
1. **Schema Validation:** Checks payload for `asset_id` and recognized facility zone (`location`).
2. **Catalog Verification:** If asset is not in database, flags `UNKNOWN_ASSET`.
3. **Perimeter Checkpoint (`MAIN_GATE`):**
   - Checks `authorization` table for matching asset.
   - If `authorized_exit = 0`, flags `UNAUTHORIZED_EXIT`.
   - If `revoked_at` is set, flags `UNAUTHORIZED_EXIT (revoked)`.
   - If `valid_until` is in the past, flags `UNAUTHORIZED_EXIT (expired)`.
   - If unrevoked, unexpired, and `authorized_exit = 1`, flags `AUTHORIZED_EXIT`.
4. **Internal Shelf Check (`SHELF_01`, `SHELF_02`, `SHELF_03`):**
   - If `location == expected_zone`, flags `NORMAL`.
   - If `location != expected_zone`, flags `MISPLACED`.

### 4.3 Database Storage & Idempotency
- Stored exclusively in `backend/asset_tracking.db`.
- Deduplication is guaranteed at the database engine level via a unique partial index:
  ```sql
  CREATE UNIQUE INDEX idx_events_message_id ON events(message_id) WHERE message_id IS NOT NULL;
  ```
- Any re-transmitted MQTT QoS 1 message with an identical `message_id` is silently deduplicated without inserting redundant rows.
