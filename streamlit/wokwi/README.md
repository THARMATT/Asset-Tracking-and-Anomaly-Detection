# Wokwi ESP32 device

Open this folder as a PlatformIO project in VS Code, or copy `src/main.cpp`
and `diagram.json` into your existing Wokwi project.

## Controls
- Potentiometer connected to GPIO34: battery percentage (0–100%).
- Potentiometer connected to GPIO35: geofence override. Turn above 80% to
  move the simulated GPS point about 333 m north, outside the 150 m boundary.
- Red LED on GPIO2 blinks on each successful telemetry publish.
- Serial Monitor: 115200 baud.

The DHT22 is intentionally omitted. Temperature is simulated in Python.
