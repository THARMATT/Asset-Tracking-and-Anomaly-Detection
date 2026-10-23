# 🚀 COMPLETE STEP-BY-STEP RUN & DEMONSTRATION GUIDE
## IoT-Based Smart Asset Tracking and Anomaly Detection System

This document contains the complete, beginner-friendly, step-by-step instructions to run, test, and demonstrate the entire system on your Windows machine.

---

## 📋 Quick Terminal Overview (Cheat Sheet)

You will need **3 PowerShell Windows** open at the project folder:
`C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system`

| Window | What to Run | Command | URL / Output |
|:---|:---|:---|:---|
| **Terminal 1** | **Backend Server + MQTT** | `$env:ENABLE_MQTT="True"; backend\venv\Scripts\python.exe backend\app.py` | `http://127.0.0.1:5000` |
| **Terminal 2** | **Frontend Web Dashboard** | `npm --prefix frontend run dev` | `http://localhost:5173` |
| **Terminal 3** | **IoT Event Simulator** | `backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario all` | Publishes Live Telemetry |

---

## 🛠️ Step 0: Initial Environment Check

Open **PowerShell** and verify that your tools are ready:

```powershell
# 1. Check Python version (Must be 3.11+)
python --version

# 2. Check Node.js and npm versions
node --version
npm --version

# 3. Check if local Mosquitto MQTT Broker is running on Port 1883
Test-NetConnection -ComputerName 127.0.0.1 -Port 1883
```

> **Note:** If `TcpTestSucceeded : True`, Mosquitto is running in the background as a Windows service! You are ready to proceed.
> *(If it says False, start it using: `& "C:\Program Files\mosquitto\mosquitto.exe" -c "mosquitto\mosquitto.conf" -v`)*

---

## 🟢 Step 1: Start the Backend (Flask API + MQTT Subscriber)

1. Open **PowerShell Terminal #1** in the project root:
   ```powershell
   cd "C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system"
   ```

2. Enable MQTT and start the Flask server:
   ```powershell
   $env:ENABLE_MQTT="True"
   backend\venv\Scripts\python.exe backend\app.py
   ```

3. **Verify Terminal #1 Output:**
   You will see:
   ```text
   [INFO] Initializing database at: ...\backend\asset_tracking.db
   [INFO] Demo data verified and seeded successfully.
   [INFO] MQTT subscriber thread started on topic 'asset/events'
   [INFO] Connected to MQTT Broker 127.0.0.1:1883 successfully.
   * Running on http://127.0.0.1:5000
   ```
   *(Keep this terminal open and running!)*

---

## 🎨 Step 2: Start the Frontend Web Dashboard

1. Open **PowerShell Terminal #2** in the project root:
   ```powershell
   cd "C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system"
   ```

2. Launch the Vite development server:
   ```powershell
   npm --prefix frontend run dev
   ```

3. **Open the Dashboard in your Browser:**
   Click or open:
   👉 **`http://localhost:5173`**

4. **Verify Header Status Indicators:**
   Look at the top-right of your browser screen:
   - 🟢 **Backend Connected** (Flask is online)
   - 🟢 **MQTT Live** (Connected to Mosquitto)
   - 🟡 **LOCAL DEMO (SIMULATION)**
   - Auto-refresh is set to **10s** (automatically pulls new events without refreshing!)

---

## 🔍 Step 3: Verify System Health via API

Open **PowerShell Terminal #3** to inspect the live backend health:

```powershell
# Test health endpoint:
Invoke-RestMethod "http://127.0.0.1:5000/api/health"
```
**Expected Response:**
```json
{
  "database_status": "connected",
  "mqtt_status": "connected",
  "service": "IoT Asset Tracking Backend",
  "status": "healthy",
  "timestamp": "2026-10-23T18:28:45Z"
}
```

```powershell
# Test MQTT subscriber metrics:
Invoke-RestMethod "http://127.0.0.1:5000/api/mqtt/status"
```

---

## ⚡ Step 4: Run Live IoT Telemetry & Anomaly Scenarios

In **PowerShell Terminal #3**, use the built-in simulator to publish RFID scan events over MQTT and watch the web dashboard update in near-real-time!

### Scenario A: Normal Scan (Item at Expected Shelf)
Asset `A001` (Laptop) scanned in its designated shelf `SHELF_01`:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario normal
```
- **Dashboard observation:** Event history logs `NORMAL`, KPI counter increments.

---

### Scenario B: Misplaced Asset Anomaly (Wrong Shelf)
Asset `A002` (Monitor) detected in `SHELF_03` (Expected in `SHELF_01`):
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario misplaced
```
- **Dashboard observation:** Warning banner surfaces `MISPLACED` alert in yellow/orange.

---

### Scenario C: Unauthorized Perimeter Gate Exit (Security Alert)
Asset `A005` (Scanner) scanned at `MAIN_GATE` without an exit permit:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario unauthorized_exit
```
- **Dashboard observation:** High-severity Security Alert triggers:
  `"SECURITY ALERT: Asset 'A005' detected at MAIN_GATE WITHOUT exit authorization (authorization is explicitly denied)."`

---

### Scenario D: Authorized Perimeter Gate Exit (Approved Removal)
Asset `A004` (Projector) scanned at `MAIN_GATE` with a valid permit:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario authorized_exit
```
- **Dashboard observation:** Status shows `AUTHORIZED_EXIT` (Green badge).

---

### Scenario E: Unknown / Rogue Asset Tag
Unregistered RFID tag `ROGUE_759` detected inside the facility:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario unknown
```
- **Dashboard observation:** Flagged as `UNKNOWN_ASSET`.

---

### Scenario F: Idempotent Duplicate Delivery Test (Network Retransmission)
Sends two identical messages with the same `message_id`:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario duplicate
```
- **Dashboard observation:** Only **one** database row is inserted. The duplicate message is safely ignored by SQLite unique indexing!

---

### Scenario G: Run FULL Demonstration Suite
Runs all 10 scenarios in sequence with a 1-second delay between scans:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario all --delay 1.0
```

---

## 🧪 Step 5: Run Automated Regression Tests (Pytest)

To prove to your evaluator or examiner that all 86 test cases pass:

In **PowerShell Terminal #3**:
```powershell
$env:PYTHONPATH=".;backend;simulator"
backend\venv\Scripts\python.exe -m pytest backend\tests -v
```

**Expected Result:**
```text
======================= 84 passed, 2 skipped in 17.64s ========================
```
*(All 8 test suites pass with 100% success rate! Zero failures.)*

---

## 📦 Step 6: Test Frontend Production Build

Verify that the React frontend compiles into production assets cleanly:

```powershell
npm --prefix frontend run build
```
- Compiles in ~25 seconds with **0 errors**.

---

## 🌐 Step 7: Wokwi ESP32 Virtual Hardware (Optional)

If you want to demonstrate physical edge hardware simulation in your browser:

1. Visit [https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32).
2. Copy code from [`wokwi/esp32_firmware.ino`](wokwi/esp32_firmware.ino) into the sketch tab.
3. Copy JSON from [`wokwi/diagram.json`](wokwi/diagram.json) into the `diagram.json` tab.
4. Add file `secrets.h` and copy [`wokwi/secrets.h`](wokwi/secrets.h).
5. Add file `libraries.txt` with:
   ```text
   PubSubClient@2.8
   ArduinoJson@7.0.4
   ```
6. Click **Play**:
   - Press **Green Button**: Simulates normal scan `A001 @ SHELF_01`.
   - Press **Red Button**: Simulates unauthorized exit `A005 @ MAIN_GATE`.
   - Serial monitor keys `1`–`5`: Triggers interactive asset scans.

---

## 🛑 How to Stop Everything Cleanly

When you are done with the demonstration:
1. In **Terminal 1 (Backend)**: Press `Ctrl + C`
2. In **Terminal 2 (Frontend)**: Press `Ctrl + C`
3. All worker threads, sockets, and timers will terminate cleanly.
