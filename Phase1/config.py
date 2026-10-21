
# ==========================================
# SYSTEM CONFIGURATION
# IoT ASSET TRACKING SYSTEM
# ==========================================

from pathlib import Path

# Always keep the database beside this Python file
PROJECT_FOLDER = Path(__file__).resolve().parent

DATABASE_NAME = str(PROJECT_FOLDER / "asset_tracking.db")

# Main exit gate
MAIN_GATE = "MAIN_GATE"

# Asset location statuses
NORMAL = "NORMAL"
MISPLACED = "MISPLACED"
MISSING = "MISSING"

# Gate statuses
AUTHORIZED_EXIT = "AUTHORIZED_EXIT"
UNAUTHORIZED_EXIT = "UNAUTHORIZED_EXIT"

# Security anomaly statuses
UNAUTHORIZED_REMOVAL = "UNAUTHORIZED_REMOVAL"
UNKNOWN_ASSET = "UNKNOWN_ASSET"
MISSING_INVESTIGATION = "MISSING_INVESTIGATION_REQUIRED"
