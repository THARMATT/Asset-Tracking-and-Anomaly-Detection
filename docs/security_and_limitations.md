# Security Model, Residual Risks & Operational Limitations
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Version:** 1.0.0  
**Updated:** 2026-10-24  

---

## 1. Security Architecture & Threat Model

| Asset / Boundary | Threat Scenario | Mitigation Implemented | Residual Risk / Limitation |
|:---|:---|:---|:---|
| **SQLite Database** | SQL Injection via URL parameters or query filters | 100% of queries use SQLite parameter bindings (`?`). Verified via unit tests. | Direct filesystem access to `.db` file must be restricted by OS permissions. |
| **Database Transactions** | Concurrent write race conditions or lockouts | SQLite WAL (Write-Ahead Logging) mode enabled; busy timeouts set to 20.0s. | SQLite does not support distributed high-concurrency multi-node writing. |
| **MQTT Telemetry** | Malformed JSON payloads or payload overflow | Subscriber decodes with try-except, validates lengths (<128 chars), and checks zone white-lists. | Local broker runs without TLS/mTLS in local development mode. |
| **MQTT Network** | Unauthorized message eavesdropping or injection | Broker binds strictly to loopback interface `127.0.0.1:1883` in `mosquitto.conf`. | Local users on the same host can publish to `asset/events`. |
| **REST API** | Cross-Origin Request Forgery / CORS leaks | Flask-CORS explicitly restricts origins to `http://localhost:5173`. | Endpoints currently lack JWT/OAuth2 user session authentication. |
| **API Error Handling** | Information disclosure / stack trace leakage | Global 400/404/500 handlers intercept tracebacks and return sanitized JSON messages. | Internal log files (`*.log`) should be protected on disk. |

---

## 2. Identified Prototype Limitations

1. **Authentication & Role-Based Access Control (RBAC):**
   - In this academic prototype, the `/api/authorization` PUT endpoint allows toggling exit permits without verifying administrative passwords.
   - *Production Requirement:* Integrate an identity provider (e.g. Keycloak, Okta) or JWT bearer tokens with separate "Operator" and "Security Officer" roles.

2. **Machine Learning Layer Generalizability:**
   - Layer 2 (Isolation Forest) was validated against a synthetic distribution ($N=500$) due to having only 15 real events in SQLite.
   - *Limitation:* Performance on synthetic patterns does **not** predict real-world accuracy. Real operations require collecting ≥ 500 events over several weeks before enabling autonomous alerting.

3. **Wokwi Cloud Simulation vs. Host Localhost:**
   - Wokwi runs in a remote browser sandbox container where `127.0.0.1` refers to the container itself.
   - Direct connection to host Windows Mosquitto requires either the **Wokwi Bridge** desktop utility or binding Mosquitto to host LAN IPv4 with router permissions.
   - To avoid security risks, the project provides a native Python CLI publisher (`simulator/event_publisher.py`) that operates directly against `127.0.0.1:1883`.
