# Event Payload Schema & API Specification
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Version:** 2.0.0  
**Updated:** 2026-10-24  

---

## 1. MQTT Event Telemetry Payload Specification

All edge devices (Wokwi ESP32, Python CLI publisher, external RFID gateways) publish JSON payloads to topic `asset/events`.

### 1.1 JSON Schema

```json
{
  "message_id": "evt-3b10a0a410e3",
  "asset_id": "A001",
  "location": "SHELF_01",
  "event_type": "INTERNAL_SCAN",
  "timestamp": "2026-10-23T18:29:02.635297+00:00"
}
```

### 1.2 Field Dictionary

| Field | Type | Mandatory? | Allowed Values | Description |
|:---|:---:|:---:|:---|:---|
| `message_id` | String | Recommended | Unique string (UUID or timestamp) | Used for database deduplication. Must not exceed 128 characters. |
| `asset_id` | String | **Yes** | Alphanumeric (e.g. `A001`-`A005`) | Physical tag identifier attached to the asset. Max 128 chars. |
| `location` | String | **Yes** | `SHELF_01`, `SHELF_02`, `SHELF_03`, `MAIN_GATE` | The detected facility zone where the scan occurred. |
| `event_type` | String | Optional | `INTERNAL_SCAN`, `GATE_SCAN`, `AUDIT_SCAN`, `MANUAL_SIMULATION` | Purpose of scan. Auto-inferred if omitted (`GATE_SCAN` at `MAIN_GATE`). |
| `timestamp` | String | Optional | ISO 8601 UTC string | Scan timestamp. Defaults to server UTC now if omitted. |

---

## 2. REST API Specification

Base URL: `http://127.0.0.1:5000/api`

### 2.1 System Endpoints
- `GET /health`: System diagnostics (`database_status`, `mqtt_status`, `service`, `timestamp`).
- `GET /summary`: Aggregated counts for assets, zone distribution, and anomaly counts.
- `GET /mqtt/status`: MQTT subscriber metrics (received, processed, dropped, duplicates).

### 2.2 Asset Endpoints
- `GET /assets`: List all assets. Query params: `active_only=true|false`.
- `GET /assets/<asset_id>`: Retrieve single asset metadata and authorization status.
- `PUT /assets/<asset_id>`: Update asset expected zone or active status.

### 2.3 Gate Authorization Endpoints
- `GET /authorization`: List all registered assets with their gate permits and audit trails.
- `GET /authorization/<asset_id>`: Check exit authorization record for an asset.
- `PUT /authorization/<asset_id>`: Update exit authorization.
  - Payload:
    ```json
    {
      "authorized_exit": 1,
      "valid_until": "2026-10-31T23:59:59Z",
      "requested_by": "Dr. Sharma",
      "approved_by": "Security Officer #4",
      "notes": "Approved field demo loan"
    }
    ```

### 2.4 Event & Audit Endpoints
- `GET /events`: Paginated events. Params: `limit` (max 200), `offset`, `status`, `zone`, `asset_id`.
- `POST /events`: Submit scan directly via REST (identical processing to MQTT).
- `GET /audits`: Paginated audit history records.
- `POST /audits`: Trigger inventory reconciliation audit. Payload: `{"scanned_asset_ids": ["A001", "A002"], "notes": "..."}`.
- `GET /zones`: Predefined and custom facility zones.
