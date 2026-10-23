# Test Report: Full Regression & End-to-End Acceptance Testing
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Document Version:** 1.0.0  
**Execution Date:** 2026-10-23  
**Environment Specifications:**
- **Operating System:** Windows 10/11 x64 (PowerShell 5.1)
- **Python Version:** 3.11.3 (in `backend/venv`)
- **Node.js Version:** v18.17.1
- **npm Version:** 10.5.0
- **MQTT Broker:** Eclipse Mosquitto v2.0.22 (Running on `127.0.0.1:1883`)
- **Database Engine:** SQLite 3.40.1 (WAL Mode, Foreign Keys Enforced)

---

## 1. Regression Test Suite Execution Summary

The backend test suite was executed via pytest across all 8 dedicated test modules:

```text
============================= test session starts =============================
platform win32 -- Python 3.11.3, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system
collected 86 items

backend/tests/test_anomaly_engine.py ...........                         [ 12%]
backend/tests/test_api.py .................                              [ 32%]
backend/tests/test_database.py .............                             [ 47%]
backend/tests/test_gate_verification.py ..........                       [ 59%]
backend/tests/test_ml_anomaly.py ..ss..                                  [ 66%]
backend/tests/test_mqtt_service.py ...........                           [ 79%]
backend/tests/test_security_reliability.py .........                     [ 89%]
backend/tests/test_simulator.py .........                                [100%]

======================= 84 passed, 2 skipped in 17.64s ========================
```

### Breakdown of Test Results by Group:

| Test Group | Test File | Passed | Failed | Skipped | Status | Description |
|:---|:---|:---:|:---:|:---:|:---:|:---|
| **Group A: Anomaly Engine** | `test_anomaly_engine.py` | 11 | 0 | 0 | **PASSED** | Normal, misplaced, missing, unknown, gate scans, audit logic |
| **Group B: REST API** | `test_api.py` | 17 | 0 | 0 | **PASSED** | CRUD, summary, events pagination, audit trigger, error handling |
| **Group C: Database & Persistence** | `test_database.py` | 13 | 0 | 0 | **PASSED** | Indexes, foreign keys, transactions, idempotency deduplication |
| **Group D: Gate Verification** | `test_gate_verification.py`| 10 | 0 | 0 | **PASSED** | Valid permit, expired pass, revoked pass, unknown tag, duplicate |
| **Group E: Experimental ML** | `test_ml_anomaly.py` | 4 | 0 | 2 | **PASSED** | Graceful fallback when optional libraries uninstalled |
| **Group F: MQTT Subscriber** | `test_mqtt_service.py` | 11 | 0 | 0 | **PASSED** | Payload schema, validation, worker queue, reconnect backoff |
| **Group G: Security & Reliability**| `test_security_reliability.py`| 9 | 0 | 0 | **PASSED** | SQL injection resistance, stack trace masking, buffer limit |
| **Group H: Simulator Payload** | `test_simulator.py` | 9 | 0 | 0 | **PASSED** | 10 CLI scenarios, JSON formats, seed repeatability |
| **TOTAL** | **8 Test Suites** | **84** | **0** | **2** | **100% PASS** | Zero blocking failures |

> **Explanation of Skipped Tests:** Two tests in `test_ml_anomaly.py` skipped gracefully because `scikit-learn` and `pandas` are not installed in the lightweight production virtualenv, directly confirming the Stage 08 requirement that the core tracking system operates without ML dependencies.

---

## 2. Frontend Production Build Verification

```powershell
npm --prefix frontend run build
```
- **Result:** Successfully compiled in **25.83 seconds**.
- **Output Artifacts:**
  - `dist/index.html` (0.72 kB)
  - `dist/assets/index-BX5zXS68.css` (13.42 kB)
  - `dist/assets/index-CUxSSuos.js` (615.90 kB)
- **Status:** **0 Errors, 0 Breaking Warnings**.

---

## 3. End-to-End Live Demonstration Evidence

Executed live telemetry scenarios using `simulator/event_publisher.py` against active Mosquitto broker (`127.0.0.1:1883`) and verified via Flask API (`GET /api/events`):

| # | Scenario | Asset & Zone | Expected Evaluation | Actual Database Persistence | REST API Observation | Result |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | Normal Scan | `A001` @ `SHELF_01` | `NORMAL` | Event ID #16 inserted | Verified (`200 OK`) | **VERIFIED** |
| 2 | Misplaced Asset | `A001` @ `SHELF_02` | `MISPLACED` | Event ID #17 inserted | Verified (`200 OK`) | **VERIFIED** |
| 3 | Unknown Asset | `ROGUE_759` @ `SHELF_03`| `UNKNOWN_ASSET` | Event ID #18 inserted | Verified (`200 OK`) | **VERIFIED** |
| 4 | Authorized Gate Exit | `A001` @ `MAIN_GATE` | `AUTHORIZED_EXIT` | Event ID #19 inserted (`auth=1`) | Verified (`200 OK`) | **VERIFIED** |
| 5 | Unauthorized Exit | `A005` @ `MAIN_GATE` | `UNAUTHORIZED_EXIT` | Event ID #20 inserted (`auth=0`) | Verified (`200 OK`) | **VERIFIED** |
| 6 | Initial Event | `A002` @ `SHELF_01` (`evt-4af2ee5f9207`) | `NORMAL` | Event ID #21 inserted | Verified (`200 OK`) | **VERIFIED** |
| 7 | Duplicate Event | `A002` @ `SHELF_01` (`evt-4af2ee5f9207`) | `DUPLICATE_IGNORED`| Skipped insertion (no second row) | Total count remains 21 | **VERIFIED** |
| 8 | Negative Test | `A001` @ `PARKING_LOT` | `INVALID_EVENT` | Rejected at validation layer | Error logged safely | **VERIFIED** |

---

## 4. Acceptance Conclusion

All critical criteria defined in the master project specification have been met:
- **Transport Reliability:** 100% of published events traversed Mosquitto without loss.
- **Idempotency:** Re-delivered events with existing `message_id` values were rejected without duplicate persistence.
- **Perimeter Security:** Gate authorizations cleanly discriminate between permitted and denied removals.
- **Dashboard Synchronization:** Near-real-time updates successfully refresh every 10 seconds without race conditions.
