
# ==========================================
# PHASE 2: ANOMALY ENGINE TESTS
# ==========================================

import unittest

from anomaly_engine import (
    check_location,
    check_gate_authorization,
    determine_final_status
)

from config import (
    NORMAL,
    MISPLACED,
    MISSING,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNAUTHORIZED_REMOVAL,
    UNKNOWN_ASSET,
    MISSING_INVESTIGATION
)


class TestAnomalyEngine(unittest.TestCase):

    def test_correct_location(self):
        self.assertEqual(
            check_location("SHELF_01", "SHELF_01"),
            NORMAL
        )

    def test_misplaced_asset(self):
        self.assertEqual(
            check_location("SHELF_01", "SHELF_03"),
            MISPLACED
        )

    def test_missing_location(self):
        self.assertEqual(
            check_location("SHELF_01", None),
            MISSING
        )

    def test_authorized_exit(self):
        self.assertEqual(
            check_gate_authorization(True),
            AUTHORIZED_EXIT
        )

    def test_unauthorized_exit(self):
        self.assertEqual(
            check_gate_authorization(False),
            UNAUTHORIZED_EXIT
        )

    def test_missing_asset_needs_investigation(self):
        self.assertEqual(
            determine_final_status(MISSING, False, False),
            MISSING_INVESTIGATION
        )

    def test_unauthorized_removal(self):
        self.assertEqual(
            determine_final_status(MISSING, True, False),
            UNAUTHORIZED_REMOVAL
        )

    def test_authorized_asset_at_gate(self):
        self.assertEqual(
            determine_final_status(NORMAL, True, True),
            AUTHORIZED_EXIT
        )

    def test_unknown_asset(self):
        self.assertEqual(
            determine_final_status(UNKNOWN_ASSET, False, False),
            UNKNOWN_ASSET
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
