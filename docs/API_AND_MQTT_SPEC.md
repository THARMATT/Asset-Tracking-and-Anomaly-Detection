# API & MQTT Protocol Specification

**System:** IoT-Based Smart Asset Tracking and Anomaly Detection System  
**Protocol:** REST (HTTP/JSON) & MQTT (over TLS v1.2 / Port 8883)  

---

## 1. Event Statuses & Definitions

The system defines 8 standard, unambiguous status codes:

| Status Code | Meaning | Severity Level |
|---|---|---|
| `NORMAL` | The asset was detected in its registered expected zone. | INFO |
| `MISPLACED` | The asset was detected in a valid internal zone, but not its expected zone (e.g. `A002` expected at `SHELF_01` but scanned at `SHELF_03`). | WARNING |
| `MISSING` | The asset was not found during a routine scan cycle. (Not treated as theft). | WARNING |
| `AUTHORIZED_EXIT` | The asset was detected at the `MAIN_GATE` and verified to possess valid exit authorization. | INFO |
| `UNAUTHORIZED_EXIT` | A registered asset was detected at the `MAIN_GATE` without valid exit authorization. | HIGH ALERT |
| `UNAUTHORIZED_REMOVAL` | An asset previously flagged as missing is detected at the `MAIN_GATE` without authorization. | CRITICAL ALERT |
| `UNKNOWN_ASSET` | A detection event occurred with an asset ID not registered in the system database. | MEDIUM ALERT |
| `MISSING_INVESTIGATION_REQUIRED` | An asset was not detected during a formal scheduled inventory audit. Investigation opened. | MEDIUM ALERT |

---

## 2. MQTT Specification

### 2.1. Broker & Topic
- **Broker Endpoint:** `<your-prefix>-ats.iot.<region>.amazonaws.com`
- **Port:** `8883` (Mutual TLS with X.509 certificates)
- **Topic:** `assets/tracking/events`
- **QoS:** `1` (At least once delivery)

### 2.2. MQTT Payload Schema (JSON)

Every event published from Wokwi ESP32 or the Demo Simulator must conform to:

```json
{
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "A001",
  "location": "SHELF_01",
  "event_type": "INTERNAL_SCAN",
  "timestamp": "2026-10-21T07:45:00Z",
  "battery_pct": 98,
  "rssi": -62
}
```

#### Field Specifications:
- `message_id` (string, required): Unique UUID or monotonic string for message deduplication.
- `asset_id` (string, required): Target asset identifier (e.g., `A001`, `UNKNOWN_TAG_99`).
- `location` (string, required): Zone code where tag was detected (e.g., `SHELF_01`, `SHELF_02`, `SHELF_03`, `MAIN_GATE`).
- `event_type` (string, required): One of `INTERNAL_SCAN`, `GATE_SCAN`, `AUDIT_SCAN`, `MANUAL_SCAN`.
- `timestamp` (string, required): ISO 8601 UTC timestamp format (`YYYY-MM-DDTHH:MM:SSZ`).
- `battery_pct` (number, optional): Remaining device battery percentage.
- `rssi` (number, optional): Received Signal Strength Indicator in dBm.

### 2.3. Sample MQTT Payloads

#### Example 1: Normal Shelf Scan
```json
{
  "message_id": "msg-001-a1b2",
  "asset_id": "A001",
  "location": "SHELF_01",
  "event_type": "INTERNAL_SCAN",
  "timestamp": "2026-10-21T07:50:00Z"
}
```

#### Example 2: Gate Scan with Unauthorized Exit
```json
{
  "message_id": "msg-002-c3d4",
  "asset_id": "A002",
  "location": "MAIN_GATE",
  "event_type": "GATE_SCAN",
  "timestamp": "2026-10-21T07:52:30Z"
}
```

#### Example 3: Unregistered Tag Detected
```json
{
  "message_id": "msg-003-e5f6",
  "asset_id": "TAG_UNKNOWN_889",
  "location": "SHELF_02",
  "event_type": "INTERNAL_SCAN",
  "timestamp": "2026-10-21T07:55:00Z"
}
```

---

## 3. Planned REST API Endpoints

All REST APIs return JSON with standardized response structures:
`{ "success": true, "data": ..., "message": "..." }`

### 3.1. System & Health
- `GET /api/health` — Checks backend service health, SQLite connectivity, and timestamp.
- `GET /api/mqtt/status` — Returns MQTT broker connection status, endpoint, active topic, and last message time.
- `GET /api/dashboard/stats` — Summary metrics: total assets, normal, misplaced, missing, alerts open, broker status.

### 3.2. Asset Management
- `GET /api/assets` — Returns list of all registered assets with their expected zone, current status, and last seen location.
- `POST /api/assets` — Registers a new asset `{ asset_id, asset_name, expected_zone, category }`.
- `PUT /api/assets/<asset_id>` — Updates asset metadata or designated expected zone.
- `DELETE /api/assets/<asset_id>` — Deregisters an asset from monitoring.

### 3.3. Zone Management
- `GET /api/zones` — Returns list of facility zones (`SHELF_01`, `SHELF_02`, `SHELF_03`, `MAIN_GATE`).
- `POST /api/zones` — Adds a new storage or gate zone.

### 3.4. Gate Exit Authorization
- `GET /api/authorization` — Returns exit authorization status for all registered assets.
- `PUT /api/authorization/<asset_id>` — Updates exit authorization: `{ authorized_exit: 0|1, notes: "...", valid_until: "..." }`.

### 3.5. Event History & Audit Log
- `GET /api/events` — Query tracking events with filters:
  - Query params: `?asset_id=A001&status=MISPLACED&location=MAIN_GATE&limit=50&offset=0`
- `POST /api/events/clear` — Clears demo event history (leaves registered assets intact).

### 3.6. Security Alerts
- `GET /api/alerts` — Retrieves alerts filtered by `?status=OPEN&severity=HIGH`.
- `PUT /api/alerts/<alert_id>/status` — Acknowledges or resolves an alert `{ status: "ACKNOWLEDGED" | "RESOLVED" }`.

### 3.7. Scheduled Inventory Audit
- `POST /api/audit/run` — Executes an inventory audit against current or simulated zone scans. Flags missing assets with `MISSING_INVESTIGATION_REQUIRED`.
- `GET /api/audit/history` — Returns records of past audits, assets detected, and missing asset counts.

### 3.8. Event Simulator
- `POST /api/simulator/publish` — Injects a simulated scan event (Internal or Gate) directly through the Anomaly Engine for live testing without physical hardware.

---

## 4. Manual AWS Resources Configuration Checklist

The following AWS resources must be configured manually in your AWS Console:

1. **AWS IoT Core "Thing"**:
   - Name: `ESP32_Asset_Tracker` (for device) and `Flask_Asset_Backend` (for backend subscriber).
2. **Device Certificates (X.509)**:
   - One-click certificate creation in AWS IoT Core.
   - Download:
     - Certificate PEM (`xxxxxxxxxx-certificate.pem.crt`)
     - Private Key (`xxxxxxxxxx-private.pem.key`)
     - Amazon Root CA 1 (`AmazonRootCA1.pem`)
   - Activate the certificate in AWS IoT Core console.
3. **AWS IoT Policy**:
   - Create policy (e.g., `AssetTrackingPolicy`) granting:
     - `iot:Connect` (to clientId)
     - `iot:Publish` (to topic `assets/tracking/events`)
     - `iot:Subscribe` (to topic `assets/tracking/events`)
     - `iot:Receive` (from topic `assets/tracking/events`)
   - Attach policy to the certificate.
4. **AWS IoT Endpoint**:
   - Find under AWS IoT Core $\rightarrow$ Settings $\rightarrow$ Device data endpoint (`xxxxxxxxxxxxxx-ats.iot.<region>.amazonaws.com`).
