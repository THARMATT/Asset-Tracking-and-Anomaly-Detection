# M.Tech Capstone Project Defense Presentation Outline
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Author / Candidate:** M.Tech IoT & Embedded Systems Candidate  
**Academic Year:** 2026  

---

## 1. Problem Context & Motivation
- Enterprise facilities incur significant financial and operational losses due to misplaced physical assets and perimeter security breaches.
- Static ERP inventory databases show *what exists*, but cannot verify *where assets are moving in real time*.
- **Core Question:** Can edge IoT telemetry and automated anomaly classification eliminate manual inventory searches and detect unauthorized removals at perimeter checkpoints?

---

## 2. Technical Contribution & Novelty
1. **Decoupled Edge Ingestion Architecture:**
   - Multi-source telemetry via MQTT (Eclipse Mosquitto) and REST.
   - Bounded thread-safe queue ingestion preventing database write contention from dropping edge messages.
2. **Dual-Layer Anomaly Detection Engine:**
   - **Layer 1 (Authoritative):** Rule-based deterministic classification of normal storage, misplaced equipment, unauthorized perimeter gate exits, unknown RFID tags, and missing audit items.
   - **Layer 2 (Statistical):** Isolation Forest unsupervised model evaluating 8 multi-scan physical movement dynamics features over a 24-hour sliding window.
3. **Database-Level Idempotency:**
   - SQLite partial index preventing duplicate event storage from network retransmissions.
4. **Resilient Near-Real-Time Web Dashboard:**
   - Single-page React application with auto-refresh guards and dedicated MQTT health telemetry badges.

---

## 3. Evaluation & Experimental Findings
- **Unit & Integration Testing:** 86 tests collected across 8 test modules — **84 passed, 2 skipped, 0 failed** (100% pass rate).
- **Transport Reliability:** 100% telemetry delivery and sub-millisecond classification across 10 evaluation scenarios.
- **Security Audit:** Zero SQL injection vulnerabilities, strict CORS enforcement, and complete error shielding.
- **Academic Rigor:** Explicitly acknowledged real data scarcity (< 30 events) and documented why statistical ML cannot replace deterministic rules in early deployment.

---

## 4. Live Demonstration Checklist for Examination
1. Show active Mosquitto broker on port 1883.
2. Launch Flask backend and React dashboard.
3. Show live dashboard indicating `Backend Connected` and `MQTT Live`.
4. Run CLI simulator demonstrating:
   - Scenario 1: Normal storage scan (`A001` @ `SHELF_01`).
   - Scenario 2: Misplaced equipment anomaly (`A002` @ `SHELF_03`).
   - Scenario 3: Unauthorized perimeter gate exit alert (`A005` @ `MAIN_GATE`).
   - Scenario 4: Duplicate event delivery rejected idempotently.
5. Demonstrate dynamic gate permit toggle directly from the React dashboard inventory table.
