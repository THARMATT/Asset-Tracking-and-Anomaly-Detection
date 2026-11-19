import csv
import tempfile
import unittest
from pathlib import Path

from asset_tracker import (
    ASSETS, GEOFENCE_RADIUS_M, calculate_distance_m, detect_anomalies,
    evaluate_geofence, generate_reading, make_geofence_event, run_simulation,
)
from asset_movement import advance_position


class AssetTrackerTests(unittest.TestCase):
    def test_normal_reading_has_no_anomalies(self):
        reading = {
            "timestamp": "2026-10-15T00:00:00+00:00", "asset_id": "AST-TEST",
            "zone": "Test Zone", "temperature_c": 25.0, "battery_pct": 80.0,
            "speed_kmh": 30.0,
        }
        self.assertEqual(detect_anomalies(reading), [])

    def test_detects_each_rule(self):
        cases = [
            ({"temperature_c": 50, "battery_pct": 80, "speed_kmh": 20}, "temperature_c"),
            ({"temperature_c": -6, "battery_pct": 80, "speed_kmh": 20}, "temperature_c"),
            ({"temperature_c": 25, "battery_pct": 10, "speed_kmh": 20}, "battery_pct"),
            ({"temperature_c": 25, "battery_pct": 80, "speed_kmh": 90}, "speed_kmh"),
        ]
        for values, expected_metric in cases:
            reading = {"timestamp": "t", "asset_id": "AST-TEST", "zone": "Test", **values}
            with self.subTest(values=values):
                events = detect_anomalies(reading)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["metric"], expected_metric)

    def test_simulator_writes_expected_files_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_simulation(iterations=2, interval=0, output_dir=tmp, seed=7)
            out = Path(tmp)
            self.assertTrue((out / "telemetry.csv").exists())
            self.assertTrue((out / "anomaly_log.csv").exists())
            self.assertTrue((out / "latest_assets.csv").exists())
            with (out / "telemetry.csv").open(newline="", encoding="utf-8") as f:
                telemetry = list(csv.DictReader(f))
            with (out / "latest_assets.csv").open(newline="", encoding="utf-8") as f:
                latest = list(csv.DictReader(f))
            self.assertEqual(len(telemetry), 2 * len(ASSETS))
            self.assertEqual(len(latest), len(ASSETS))
            self.assertGreater(summary["anomalies_detected_this_run"], 0)

    def test_asset_position_advances_along_simulated_route(self):
        asset = ASSETS[0]
        first_position = advance_position(asset.asset_id, asset.latitude, asset.longitude)
        second_position = advance_position(asset.asset_id, *first_position)
        self.assertNotEqual(first_position, (asset.latitude, asset.longitude))
        self.assertNotEqual(second_position, first_position)
        # The simulated route should stay local to the asset's configured home zone.
        self.assertLess(abs(second_position[0] - asset.latitude), 0.002)
        self.assertLess(abs(second_position[1] - asset.longitude), 0.003)

    def test_geofence_distance_and_inside_outside_detection(self):
        asset = ASSETS[0]
        self.assertAlmostEqual(
            calculate_distance_m(asset.latitude, asset.longitude, asset.latitude, asset.longitude),
            0.0,
            places=3,
        )
        state, distance = evaluate_geofence(asset.asset_id, asset.latitude, asset.longitude)
        self.assertEqual(state, "INSIDE")
        self.assertEqual(distance, 0.0)
        outside_lat = asset.latitude + 0.003
        state, distance = evaluate_geofence(asset.asset_id, outside_lat, asset.longitude)
        self.assertEqual(state, "OUTSIDE")
        self.assertGreater(distance, GEOFENCE_RADIUS_M)

    def test_geofence_exit_event_message(self):
        reading = {
            "timestamp": "2026-10-29T00:00:00+00:00",
            "asset_id": "AST-001",
            "zone": "Warehouse A",
        }
        event = make_geofence_event(reading, 330.0, "EXIT")
        self.assertEqual(event["metric"], "geofence_distance_m")
        self.assertEqual(event["severity"], "HIGH")
        self.assertIn("outside", event["message"])
        self.assertEqual(event["observed_value"], 330.0)

    def test_invalid_iterations_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_simulation(iterations=0, interval=0, output_dir=tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
