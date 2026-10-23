# Wokwi ESP32 IoT Asset Tracking Simulation Guide

## Overview

This directory contains the firmware and virtual hardware design to simulate an ESP32 edge asset scanner node in the [Wokwi Arduino & ESP32 Simulator](https://wokwi.com).

The node simulates:
- An internal storage shelf scanner (`SHELF_01`, `SHELF_02`, `SHELF_03`).
- A perimeter security checkpoint scanner (`MAIN_GATE`).
- Real-time event publishing over MQTT topic `asset/events` using the canonical JSON schema.

---

## Files in this Directory

| File | Description |
|:---|:---|
| `esp32_firmware.ino` | ESP32 Arduino sketch using `WiFi.h`, `PubSubClient`, and `ArduinoJson` |
| `diagram.json` | Virtual breadboard wiring: ESP32-DevKit-C, 2 pushbuttons, 2 LEDs, current-limiting resistors |
| `libraries.txt` | Wokwi library manifest (`PubSubClient@2.8`, `ArduinoJson@7.0.4`) |
| `secrets.h` | Local Wi-Fi and MQTT broker configuration (ignored by Git) |
| `secrets.h.example` | Template configuration for public repository |

---

## Hardware Layout (in `diagram.json`)

```
[ Pushbutton 1 ] (GPIO 18, Green) ---> Simulates Normal Shelf Scan (A001 @ SHELF_01)
[ Pushbutton 2 ] (GPIO 19, Red)   ---> Simulates Unauthorized Gate Scan (A005 @ MAIN_GATE)
[ Status LED 1 ] (GPIO 22, Green) ---> Flash on Normal scan / successful publish
[ Status LED 2 ] (GPIO 23, Red)   ---> Flash on Anomaly alert / disconnect
```

---

## Crucial Note: Wokwi Cloud vs. Local Host Networking

When running a simulation inside the web browser on `wokwi.com`:

1. **`127.0.0.1` inside Wokwi refers to the Wokwi sandbox container, NOT your Windows laptop.**
2. To allow Wokwi in the browser to reach your local Eclipse Mosquitto broker:

### Method 1: Wokwi IoT Gateway / Wokwi Bridge (Recommended by Wokwi)
Wokwi provides a desktop utility called **Wokwi Bridge** that establishes a secure tunnel between the browser simulator and your local network.
- Download Wokwi Bridge: https://docs.wokwi.com/guides/wokwi-bridge
- Run in PowerShell:
  ```powershell
  wokwi-bridge
  ```
- In `secrets.h`, keep `MQTT_BROKER = "10.0.0.1"` or your local bridge IP.

### Method 2: Public or Test Broker
For zero-setup demonstrations without running Wokwi Bridge:
- Change `MQTT_BROKER` in `secrets.h` to `test.mosquitto.org` (port `1883`).
- Run your local backend subscriber or Python publisher connected to the same test broker.

### Method 3: Local Network IP (When using private Mosquitto on LAN)
- Ensure Mosquitto listens on all interfaces by updating `mosquitto/mosquitto.conf`:
  ```
  listener 1883 0.0.0.0
  allow_anonymous true
  ```
- Set `MQTT_BROKER` in `secrets.h` to your laptop's Wi-Fi IPv4 address (e.g. `10.191.223.188`).

> **Security Note:** Never expose an unauthenticated broker to the public internet. The local IP configuration is strictly for trusted home/lab LAN subnets.

---

## How to Run in Wokwi (Web Browser)

1. Navigate to [https://wokwi.com/projects/new/esp32](https://wokwi.com/projects/new/esp32).
2. Paste the contents of `esp32_firmware.ino` into the code editor tab.
3. Click the **diagram.json** tab and replace its contents with `wokwi/diagram.json`.
4. Click the **+** (New File) icon in the tab bar, create `secrets.h`, and paste the contents of `wokwi/secrets.h`.
5. Create `libraries.txt` and add:
   ```
   PubSubClient@2.8
   ArduinoJson@7.0.4
   ```
6. Click the green **Start Simulation** button (`Play` icon).
7. In the Serial Monitor, observe:
   - Wi-Fi connection to `Wokwi-GUEST`.
   - MQTT connection status.
8. Click the **Green Button** or type `1` in the Serial Monitor to trigger a normal scan.
9. Click the **Red Button** or type `5` to trigger an unauthorized gate alarm scan.

---

## Local Verification Alternative

If Wokwi Bridge is not installed or internet access to `wokwi.com` is restricted, use the project's native Python CLI event simulator:
```powershell
backend\venv\Scripts\python.exe simulator\event_publisher.py --scenario all
```
This runs the exact same schema and test cases directly against your local Mosquitto broker on `127.0.0.1:1883`.
