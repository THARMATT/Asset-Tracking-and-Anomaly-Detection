# IoT Asset Tracking & Anomaly Detection — Complete MQTT Project

This project supports two modes:
1. **ESP32 via MQTT** — Wokwi ESP32 sends latitude, longitude, speed and battery; Python receives the messages, simulates temperature, applies geofencing/anomaly rules and updates the dashboard CSV files.
2. **Built-in simulation** — the original local simulator remains available as a fallback.

## Project contents

- `asset_tracker.py` — asset definitions, telemetry simulation, geofence distance, anomaly rules and CSV schemas.
- `asset_movement.py` — local simulated asset movement.
- `dashboard.py` — Streamlit dashboard with map, blue dashed geofence circles, pulsing markers, telemetry history and alert panel.
- `mqtt_bridge.py` — MQTT subscriber and backend processor.
- `test_asset_tracker.py` — automated unit tests.
- `wokwi/` — ESP32 PlatformIO source and Wokwi circuit diagram.

## A. One-time setup in VS Code (Windows)

Open the `iot_asset_tracker_week2` folder in VS Code. Open Terminal → New Terminal and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this once in that terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## B. Configure the MQTT topic

The default topic prefix is:

`iot-asset-tracker-demo/nsut-asset-7f31a9`

It is already identical in:
- `mqtt_bridge.py` → `TOPIC_PREFIX`
- `wokwi/src/main.cpp` → `TOPIC_PREFIX`

If you change it, change both values exactly. A public broker is shared, so using a unique prefix is important.

Demo broker:
- Host: `broker.hivemq.com`
- Port: `1883`
- MQTT TCP (unencrypted)

This public broker is for a university demonstration only. Do not publish personal, confidential or production data. For a real deployment, use a private broker with authentication and TLS. The bridge supports environment overrides `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, and `MQTT_TOPIC_PREFIX`.

## C. Start the dashboard and initialize the CSV data

In Terminal 1:

```powershell
streamlit run dashboard.py
```

The dashboard opens in your browser. Choose **ESP32 via MQTT** in the sidebar. The initial sample data is only a fallback to populate the dashboard; live ESP32 data will replace the `ASSET_001` latest row when the first MQTT message arrives.

Leave this terminal running.

## D. Start the MQTT bridge

Open Terminal 2 in the same project folder. Activate the same virtual environment and run:

```powershell
.\.venv\Scripts\Activate.ps1
python mqtt_bridge.py
```

Expected output includes:
```text
IoT Asset Tracker MQTT bridge
Broker: broker.hivemq.com:1883
Topic:  iot-asset-tracker-demo/nsut-asset-7f31a9/+/telemetry
Connected to MQTT broker broker.hivemq.com:1883
Subscribed: ...
Temperature source: Python backend simulation (DHT22 not used)
```

Leave this terminal running.

## E. Run the Wokwi ESP32

Open the `wokwi` folder as a PlatformIO project in VS Code, or copy these into your existing Wokwi project:
- `wokwi/src/main.cpp` → your project's `src/main.cpp`
- `wokwi/diagram.json` → your project's `diagram.json`
- `wokwi/platformio.ini` → project PlatformIO configuration

PlatformIO dependencies are declared in `platformio.ini`:
- PubSubClient
- ArduinoJson

Start the Wokwi simulation. Open the Serial Monitor at **115200 baud**.

Expected serial output:
```text
=== IoT Asset Tracker / ESP32 MQTT ===
DHT22 is intentionally not used; backend simulates temperature.
Wi-Fi connected.
Connecting to MQTT broker... connected.
MQTT published: {"asset_id":"ASSET_001", ...}
```

The Python bridge terminal should print one new reading every 2 seconds. The Streamlit dashboard refreshes every 3 seconds by default.

## F. Wokwi controls

The Wokwi diagram uses two potentiometers and one LED:

| Component | ESP32 pin | Purpose |
|---|---:|---|
| Battery potentiometer | GPIO34 | Changes battery percentage from 0–100% |
| Geofence potentiometer | GPIO35 | Turn above approximately 80% to move GPS outside the 150 m geofence |
| Red LED | GPIO2 | Blinks after each telemetry publish |

The geofence override moves the simulated GPS point about 333 metres north of the configured ASSET_001 home point. The dashboard should display the out-of-boundary alert and red marker.

**Temperature:** DHT22 is deliberately removed from this integration. The backend generates a slowly varying temperature value. This avoids the Wokwi DHT22 communication failure previously encountered.

**GPS and speed:** Simulated by the ESP32 firmware; no physical GPS sensor is needed for the software-only project.

## G. Test the project

### Automated tests

From the project folder:
```powershell
python -m unittest -v
```

### Live integration

1. Start Streamlit.
2. Start `python mqtt_bridge.py`.
3. Start Wokwi.
4. Confirm the bridge terminal prints messages every 2 seconds.
5. Turn the battery potentiometer down below 15% to trigger a low-battery anomaly.
6. Turn the geofence potentiometer above 80% to trigger `ASSET_001` out-of-boundary.
7. Return the geofence potentiometer below 80% to simulate re-entry.

## H. Troubleshooting

**Bridge cannot connect**
- Confirm the PC has internet access.
- Confirm broker host and port are correct.
- Try again after a short wait; public brokers can be temporarily unavailable.

**Wokwi says Wi-Fi is not connected**
- Confirm the SSID is exactly `Wokwi-GUEST` and password is empty.
- Run the simulation in Wokwi's cloud simulator with internet access.

**Bridge connects but receives no messages**
- Confirm Wokwi Serial Monitor says MQTT connected.
- Confirm the topic prefix in `main.cpp` and `mqtt_bridge.py` is identical.
- Confirm the topic ends in `/ASSET_001/telemetry`.
- Confirm no other project is publishing on your chosen topic.

**Dashboard shows no ESP32 packets**
- Keep the bridge terminal running.
- Keep Wokwi simulation running.
- Keep the dashboard in ESP32 via MQTT mode and wait for the next refresh.

**Use built-in simulation**
- Select Built-in simulation in the dashboard sidebar. This mode remains available and does not require MQTT.

## I. Architecture

`ESP32 (Wokwi) → Wi-Fi → MQTT broker → mqtt_bridge.py → CSV files → Streamlit dashboard`

The MQTT bridge uses the original project's `ASSET_001` asset definition and CSV schemas. It updates the latest row for that asset without removing the other demo assets. It logs a geofence EXIT/ENTRY only when the asset crosses the boundary, avoiding duplicate boundary events on every MQTT packet.

## J. Limitations

- HiveMQ public broker is a shared demonstration broker, not production infrastructure.
- ESP32 GPS, speed and battery are simulated in Wokwi.
- Temperature is generated by the Python backend.
- This is a software prototype, not a certified tracking or safety system.
