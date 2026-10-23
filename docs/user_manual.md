# User Manual & Operator Guide
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Version:** 1.0.0  
**Audience:** Warehouse Supervisors, Security Personnel, Academic Evaluators  

---

## 1. Navigating the Dashboard

Open your web browser and navigate to `http://localhost:5173`. The application header displays:
- **System Title:** Smart Asset Tracking & Anomaly Detection.
- **Operating Mode:** `LOCAL DEMO (SIMULATION)`.
- **Backend Status:** `Backend Connected` (Green).
- **MQTT Status:** `MQTT Live` (Green) when Mosquitto is active.
- **Auto-Refresh Selector:** Configurable between 5s, 10s (default), 30s, or Off.
- **Last Updated:** Live clock timestamp of the most recent data fetch.

---

## 2. Dashboard Sections & Workflows

### 2.1 System Overview Tab
- **Metric Cards:**
  - **Total Registered Assets:** Monitored physical items (`A001`-`A005`).
  - **Normal Scans:** Items verified in their designated storage shelves.
  - **Misplaced Assets:** Items flagged in incorrect internal racks.
  - **Gate Security Alerts:** Unauthorized removals detected at `MAIN_GATE`.
- **Security & Anomaly Alerts Banner:** Surfaces recent warning and critical security events with explanatory reasons.
- **Visual Analytics:** Real-time donut and bar charts showing status distributions and zone occupancy.

### 2.2 Asset Inventory Tab
- Search physical assets by name, ID, or category.
- **Gate Exit Permits:**
  - View whether an asset is authorized to pass through `MAIN_GATE`.
  - Click **Revoke** / **Grant** to dynamically toggle exit permits with immediate database synchronization.

### 2.3 Event History & Filter Tab
- Comprehensive audit trail of all historical telemetry scans.
- Filter by:
  - **Status:** `NORMAL`, `MISPLACED`, `AUTHORIZED_EXIT`, `UNAUTHORIZED_EXIT`, `UNKNOWN_ASSET`, `MISSING_INVESTIGATION_REQUIRED`.
  - **Zone:** `SHELF_01`, `SHELF_02`, `SHELF_03`, `MAIN_GATE`.
  - **Asset ID:** Search by tag ID.
- Pagination controls with total count indicators.

### 2.4 Event Simulator Tab
- Execute ad-hoc test scans directly from the browser:
  - Select any registered asset from the dropdown.
  - Select detected facility zone.
  - Click **Submit Scan Event** to trigger backend processing and view the immediate anomaly classification.

### 2.5 Inventory Audits Tab
- Review scheduled physical inventory reconciliation reports.
- View total expected assets vs. detected assets and inspect the list of missing items flagged for security investigation.
