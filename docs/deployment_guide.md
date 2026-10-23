# Deployment Guide: Local Windows Setup & Execution
## IoT-Based Smart Asset Tracking and Anomaly Detection System

**Version:** 1.0.0  
**Target Environment:** Windows 10/11 x64 with PowerShell  

---

## 1. Prerequisites & Tooling

Before running the system, ensure the following software is installed on your Windows machine:
1. **Python 3.11+** (Verify via: `python --version`)
2. **Node.js v18+ & npm** (Verify via: `node --version` and `npm --version`)
3. **Eclipse Mosquitto MQTT Broker** (Verify via: `Test-NetConnection -ComputerName 127.0.0.1 -Port 1883`)

---

## 2. Directory Structure

```text
Asset  Tracking system/
├── backend/
│   ├── app.py                     # Flask application factory & REST routes
│   ├── anomaly_engine.py          # Layer 1 deterministic rules engine
│   ├── database.py                # SQLite transactional data access layer
│   ├── mqtt_service.py            # Paho MQTT subscriber background worker
│   ├── ml_anomaly.py              # Layer 2 experimental Isolation Forest
│   ├── config.py                  # Environment & system configurations
│   ├── asset_tracking.db          # Active production SQLite database
│   ├── requirements.txt           # Python dependency manifest
│   └── tests/                     # 8 pytest unit & integration test suites
├── frontend/
│   ├── src/                       # React 18 dashboard application
│   ├── package.json               # Node.js dependencies
│   └── dist/                      # Pre-compiled production bundle
├── simulator/
│   └── event_publisher.py         # Python CLI MQTT scenario publisher
├── wokwi/
│   ├── esp32_firmware.ino         # Virtual ESP32 C++ firmware
│   ├── diagram.json               # Breadboard wiring & components
│   └── README.md                  # Wokwi simulation guide
└── docs/                          # Comprehensive system documentation
```

---

## 3. Step-by-Step Service Startup Sequence

To run the entire system locally, open **three PowerShell windows**:

### Terminal 1: Mosquitto MQTT Broker
If Mosquitto is running as a Windows service (default), it is already listening on `127.0.0.1:1883`. To verify:
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 1883
```
If not running, start it:
```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c "mosquitto\mosquitto.conf" -v
```

### Terminal 2: Flask Application Backend
From the project root:
```powershell
$env:ENABLE_MQTT="True"
backend\venv\Scripts\python.exe backend\app.py
```
- Listens on `http://127.0.0.1:5000`.
- Automatically connects MQTT subscriber to Mosquitto on `127.0.0.1:1883`.

### Terminal 3: React Dashboard Frontend
From the project root:
```powershell
npm --prefix frontend run dev
```
- Available at `http://localhost:5173`.
- Auto-proxies `/api` requests to Flask port 5000.

---

## 4. Running Regression Tests

Execute all 8 backend test suites (86 tests total):
```powershell
$env:PYTHONPATH=".;backend;simulator"
backend\venv\Scripts\python.exe -m pytest backend\tests -v
```
Build the frontend production package:
```powershell
npm --prefix frontend run build
```
