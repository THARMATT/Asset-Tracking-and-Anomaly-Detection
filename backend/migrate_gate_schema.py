#!/usr/bin/env python3
# ==========================================
# GATE SCHEMA MIGRATION SCRIPT
# IoT-Based Smart Asset Tracking System
# ==========================================
# Adds new authorization columns introduced in Stage 06 (Main-Gate Verification).
# Safe to run multiple times (idempotent).

import sqlite3
import logging
import sys
from pathlib import Path

# Ensure backend root is importable
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from config import DATABASE_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("GateSchemaMigration")

# New columns to add to the authorization table
NEW_COLUMNS = [
    ("requested_by", "TEXT"),
    ("approved_by", "TEXT"),
    ("revoked_at", "TEXT"),
    ("revocation_reason", "TEXT"),
]


def run_migration(db_path: str = None) -> None:
    """
    Add new columns to the authorization table if they don't already exist.
    Uses PRAGMA table_info to detect existing columns before attempting ALTER TABLE.
    """
    target_db = db_path or DATABASE_PATH
    logger.info(f"Running gate schema migration on: {target_db}")

    conn = sqlite3.connect(target_db)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check which columns already exist
        cursor.execute("PRAGMA table_info(authorization);")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        logger.info(f"Existing columns in 'authorization': {sorted(existing_cols)}")

        added = []
        for col_name, col_type in NEW_COLUMNS:
            if col_name not in existing_cols:
                logger.info(f"Adding column '{col_name}' ({col_type}) to authorization table...")
                cursor.execute(f"ALTER TABLE authorization ADD COLUMN {col_name} {col_type};")
                added.append(col_name)
                logger.info(f"  ✓ Column '{col_name}' added successfully.")
            else:
                logger.info(f"  ✓ Column '{col_name}' already exists — skipping.")

        conn.commit()

        if added:
            logger.info(f"Migration complete. Added columns: {added}")
        else:
            logger.info("Migration complete. No changes needed (all columns already present).")

        # Verify final schema
        cursor.execute("PRAGMA table_info(authorization);")
        final_cols = [row["name"] for row in cursor.fetchall()]
        logger.info(f"Final 'authorization' columns: {final_cols}")

    finally:
        conn.close()


if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_migration(db_path=db_arg)
