# ==========================================
# DATABASE INITIALIZATION SCRIPT
# IoT-Based Smart Asset Tracking System
# ==========================================

import sys
from pathlib import Path

# Add backend directory to module search path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATABASE_PATH
from database import initialize_database, retrieve_summary_counts, get_assets


def main():
    print("=" * 60)
    print("  INITIALIZING ASSET TRACKING DATABASE")
    print("=" * 60)
    print(f"Target Database: {DATABASE_PATH}\n")

    # Initialize tables and seed default data
    initialize_database(seed=True)

    summary = retrieve_summary_counts()
    assets = get_assets()

    print("Database tables and indexes created successfully.")
    print("Seeded Demo Assets:")
    print("-" * 60)
    print(f"{'Asset ID':<10} {'Name':<15} {'Zone':<12} {'Exit Auth':<10}")
    print("-" * 60)
    for a in assets:
        auth_status = "Authorized" if a["authorized_exit"] else "Unauthorized"
        print(f"{a['asset_id']:<10} {a['asset_name']:<15} {a['expected_zone']:<12} {auth_status:<10}")
    print("-" * 60)

    print(f"\nSummary:")
    print(f" - Total Registered Assets: {summary['total_assets']}")
    print(f" - Active Assets:           {summary['active_assets']}")
    print(f" - Exit Authorized:         {summary['authorized_exit_count']}")
    print(f" - Exit Unauthorized:       {summary['unauthorized_exit_count']}")
    print("\nInitialization Complete. Database is ready for use.")


if __name__ == "__main__":
    main()
