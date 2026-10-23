# Security, Reliability & Error Recovery Architecture
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Version:** 1.0.0  
**Date:** 2026-10-23  

---

## 1. Security Analysis & Controls

### 1.1 SQL Injection Protection
- **Mechanism:** All database operations utilize SQLite parameterized queries (`?` placeholders).
- **Verification:** Unit tests in `backend/tests/test_security_reliability.py` execute standard SQL injection payloads (e.g. `' OR '1'='1`) against endpoints `/api/assets/<id>` and query filters `/api/events?status=...`. In all cases, inputs are treated as literal strings and produce safe HTTP 404 or zero matches without leaking data.

### 1.2 Data Integrity & Foreign Key Enforcement
- **Mechanism:** Foreign keys are explicitly enabled on every SQLite connection via `PRAGMA foreign_keys = ON;`.
- **Validation:** Deleting an asset cascades cleanly to remove child records in `authorization`. Attempting to register assets in non-existent zones raises an immediate `sqlite3.IntegrityError`.

### 1.3 Error Shielding & Information Disclosure Prevention
- **Mechanism:** Global Flask error handlers intercept HTTP 400, 404, and 500.
- **Protection:** Stack traces, internal operating system file paths, and local drive structures are masked from API responses. The `/api/health` endpoint sanitizes internal paths and verifies database health without printing file system paths.

### 1.4 Network Transport Security & CORS
- **CORS Policy:** Flask-CORS strictly restricts origins to the configured frontend origin (default: `http://localhost:5173` and `http://127.0.0.1:5173`).
- **MQTT Network Binding:** The local development broker (`mosquitto.conf`) binds to `127.0.0.1:1883` to prevent unauthenticated exposure across public interfaces.

### 1.5 Prototype Security Limitations
- **Current Limitation:** In this academic demonstration prototype, API endpoints (such as `PUT /api/authorization/<id>`) do not implement JWT/OAuth2 role-based authentication.
- **Production Recommendation:** Before enterprise deployment, deploy an API Gateway or Reverse Proxy (e.g. Nginx/Kong) enforcing mutual TLS (mTLS) for edge scanners and OAuth2/OIDC bearer tokens for administrative dashboard operations.

---

## 2. Reliability & Error Recovery

### 2.1 MQTT Connection Resilience & Exponential Backoff
- **Disconnection Handling:** `backend/mqtt_service.py` implements threaded network loops (`loop_start()`). Upon broker disconnects, Paho automatically schedules reconnection attempts with exponential backoff (1s to 60s).
- **Graceful Shutdown:** Subscriptions and network loops cleanly stop during application teardown, releasing sockets and worker threads.

### 2.2 Event Ingestion Queue & Decoupling
- **Architecture:** Incoming MQTT network callbacks place raw messages into a bounded thread-safe queue (`queue.Queue(maxsize=1000)`). A dedicated background worker thread pulls items from the queue and executes database persistence.
- **Benefit:** Network callbacks return in sub-millisecond time, preventing broker heartbeat timeouts during database write contention.

### 2.3 Idempotency & Deduplication Persistence
- **Mechanism:** A unique partial index (`idx_events_message_id`) exists on SQLite table `events(message_id)`.
- **Behavior:** If a network blip causes Mosquitto or an edge scanner to retransmit a QoS 1 message, the backend identifies the duplicate message ID, discards duplicate row insertion, and logs an idempotent deduplication event.

---

## 3. Database Management & Disaster Recovery

### 3.1 Database Location & Multi-Instance Elimination
- **Active Database Path:** Explicitly locked to `backend/asset_tracking.db`.
- **Cleanup Strategy:** The stale 28 KB historical root database `asset_tracking.db` from Phase 1 has been identified and scheduled for deprecation to avoid operator confusion.

### 3.2 Safe Backup Procedures
- Prior to schema migrations, automatic backups are generated:
  - `backend/asset_tracking.db.backup_stage03`
  - `backend/asset_tracking.db.backup_stage06`
- **PowerShell Backup Command:**
  ```powershell
  Copy-Item "backend/asset_tracking.db" "backend/asset_tracking.db.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
  ```
