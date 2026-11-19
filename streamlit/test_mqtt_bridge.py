import tempfile
import unittest
from pathlib import Path

import pandas as pd

import mqtt_bridge
from asset_tracker import run_simulation


class MQTTBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(self.temp_dir.name)
        mqtt_bridge.DATA_DIR = data_dir
        mqtt_bridge.LATEST_FILE = data_dir / "latest_assets.csv"
        mqtt_bridge.TELEMETRY_FILE = data_dir / "telemetry.csv"
        mqtt_bridge.ANOMALY_FILE = data_dir / "anomaly_log.csv"
        mqtt_bridge.TEMPERATURE_CACHE.clear()
        mqtt_bridge.FILE_LOCK = __import__("threading").Lock()
        # Seed original CSV files, as the dashboard does on first launch.
        run_simulation(iterations=1, interval=0, output_dir=data_dir, seed=11)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mqtt_reading_updates_existing_asset_and_keeps_csv_schema(self):
        mqtt_bridge.process_telemetry({
            "asset_id": "ASSET_001", "latitude": 28.613909,
            "longitude": 77.209015, "speed": 24.0, "battery": 85,
        })
        latest = pd.read_csv(mqtt_bridge.LATEST_FILE)
        telemetry = pd.read_csv(mqtt_bridge.TELEMETRY_FILE)
        row = latest.loc[latest["asset_id"] == "ASSET_001"].iloc[0]
        self.assertEqual(len(latest), 9)
        self.assertEqual(row["telemetry_source"], "ESP32_MQTT")
        self.assertEqual(row["geofence_status"], "INSIDE")
        self.assertEqual(len(telemetry), 10)
        self.assertIn("temperature_c", telemetry.columns)

    def test_geofence_exit_is_logged_once_while_asset_stays_outside(self):
        payload = {
            "asset_id": "ASSET_001", "latitude": 28.616909,
            "longitude": 77.209015, "speed": 24.0, "battery": 85,
        }
        mqtt_bridge.process_telemetry(payload)
        mqtt_bridge.process_telemetry(payload)
        anomalies = pd.read_csv(mqtt_bridge.ANOMALY_FILE)
        exits = anomalies[
            (anomalies["asset_id"] == "ASSET_001") &
            (anomalies["metric"] == "geofence_distance_m")
        ]
        self.assertEqual(len(exits), 1)
        latest = pd.read_csv(mqtt_bridge.LATEST_FILE)
        row = latest.loc[latest["asset_id"] == "ASSET_001"].iloc[0]
        self.assertEqual(row["geofence_status"], "OUTSIDE")
        self.assertEqual(row["status"], "ALERT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
