
# ==========================================
# SMART ASSET TRACKING SYSTEM
# PHASE 2: SOFTWARE PROTOTYPE
# ==========================================

from datetime import datetime

from database import (
    get_asset,
    get_all_assets,
    check_authorization,
    record_event,
    get_all_events,
    clear_events
)

from anomaly_engine import (
    check_location,
    check_gate_authorization,
    determine_final_status
)

from config import (
    MAIN_GATE,
    UNKNOWN_ASSET,
    NORMAL,
    MISSING,
    MISPLACED,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNAUTHORIZED_REMOVAL,
    MISSING_INVESTIGATION
)


# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================

def get_timestamp():
    """Return the current date and time."""

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_heading(title):
    """Print a formatted section heading."""

    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


# ==========================================
# 2. START THE SYSTEM
# ==========================================

print_heading("SMART ASSET TRACKING AND SECURITY SYSTEM")

print("Mode: SIMULATED EVENTS")
print("Hardware: Not connected in Phase 2")

# Start each demo with a fresh event history.
# Registered assets and permissions remain in the database.
clear_events()

assets = get_all_assets()

if not assets:
    print("\nNo assets found.")
    print("Please run: python setup_database.py")
    raise SystemExit


# ==========================================
# 3. SIMULATED INTERNAL SCANS
# ==========================================
# Format: (asset_id, detected_zone)
#
# A001: Correct location
# A002: Wrong location
# A004: Correct location
#
# A003 and A005 will not be detected internally.

internal_events = [
    ("A001", "SHELF_01"),
    ("A002", "SHELF_03"),
    ("A004", "SHELF_02")
]


# ==========================================
# 4. SIMULATED MAIN-GATE SCANS
# ==========================================
# A004: Authorized exit
# A005: Exit without authorization

gate_events = [
    "A004",
    "A005"
]


# Store results while processing
internal_results = {}
detected_locations = {}
gate_results = {}


# ==========================================
# 5. PROCESS INTERNAL SCANS
# ==========================================

print_heading("INTERNAL ASSET TRACKING")

for asset_id, detected_zone in internal_events:

    asset = get_asset(asset_id)

    if asset is None:

        status = UNKNOWN_ASSET

    else:

        expected_zone = asset[2]

        status = check_location(
            expected_zone,
            detected_zone
        )

    internal_results[asset_id] = status
    detected_locations[asset_id] = detected_zone

    record_event(
        asset_id,
        "INTERNAL_SCAN",
        detected_zone,
        get_timestamp(),
        status
    )

    print(
        f"Asset: {asset_id} | "
        f"Zone: {detected_zone} | "
        f"Status: {status}"
    )


# ==========================================
# 6. FIND ASSETS NOT DETECTED
# ==========================================

print_heading("MISSING ASSET CHECK")

for asset in assets:

    asset_id = asset[0]

    if asset_id not in internal_results:

        internal_results[asset_id] = MISSING
        detected_locations[asset_id] = "NOT_DETECTED"

        record_event(
            asset_id,
            "MISSING_CHECK",
            "NOT_DETECTED",
            get_timestamp(),
            MISSING
        )

        print(
            f"Asset: {asset_id} | "
            f"Status: {MISSING}"
        )


# ==========================================
# 7. PROCESS MAIN-GATE SCANS
# ==========================================

print_heading("MAIN GATE SECURITY CHECK")

for asset_id in gate_events:

    asset = get_asset(asset_id)

    if asset is None:

        gate_status = UNKNOWN_ASSET

    else:

        authorized = check_authorization(asset_id)

        gate_status = check_gate_authorization(
            authorized
        )

    gate_results[asset_id] = gate_status

    record_event(
        asset_id,
        "GATE_SCAN",
        MAIN_GATE,
        get_timestamp(),
        gate_status
    )

    print(
        f"Asset: {asset_id} | "
        f"Location: {MAIN_GATE} | "
        f"Gate status: {gate_status}"
    )


# ==========================================
# 8. GENERATE FINAL ASSET REPORT
# ==========================================

print_heading("FINAL ASSET REPORT")

print(
    f"{'ID':<8}"
    f"{'ASSET':<15}"
    f"{'EXPECTED ZONE':<17}"
    f"{'DETECTED AT':<18}"
    f"FINAL STATUS"
)

print("-" * 95)

final_report = []

for asset in assets:

    asset_id = asset[0]
    asset_name = asset[1]
    expected_zone = asset[2]

    internal_status = internal_results.get(
        asset_id,
        MISSING
    )

    gate_detected = asset_id in gate_results

    authorized = check_authorization(asset_id)

    final_status = determine_final_status(
        internal_status,
        gate_detected,
        authorized
    )

    # Show the gate if the asset was detected there.
    # Otherwise show its last simulated internal location.
    if gate_detected:
        detected_location = MAIN_GATE
    else:
        detected_location = detected_locations.get(
            asset_id,
            "NOT_DETECTED"
        )

    final_report.append({
        "asset_id": asset_id,
        "asset_name": asset_name,
        "expected_zone": expected_zone,
        "detected_location": detected_location,
        "final_status": final_status
    })

    print(
        f"{asset_id:<8}"
        f"{asset_name:<15}"
        f"{expected_zone:<17}"
        f"{detected_location:<18}"
        f"{final_status}"
    )


# ==========================================
# 9. DISPLAY SECURITY ALERTS
# ==========================================

print_heading("SECURITY ALERTS AND ANOMALIES")

anomaly_statuses = {
    MISPLACED,
    MISSING_INVESTIGATION,
    UNAUTHORIZED_EXIT,
    UNAUTHORIZED_REMOVAL,
    UNKNOWN_ASSET
}

anomalies = [
    item for item in final_report
    if item["final_status"] in anomaly_statuses
]

if anomalies:

    for item in anomalies:

        print(
            f"ALERT: {item['asset_id']} | "
            f"{item['asset_name']} | "
            f"{item['final_status']}"
        )

else:

    print("No anomalies detected.")

# Also show unknown assets detected at the gate.
for asset_id, gate_status in gate_results.items():

    if gate_status == UNKNOWN_ASSET:

        print(
            f"ALERT: Unregistered asset {asset_id} "
            f"detected at {MAIN_GATE}"
        )


# ==========================================
# 10. DISPLAY EVENT HISTORY
# ==========================================

print_heading("DATABASE EVENT HISTORY")

events = get_all_events()

if events:

    for event in events:

        (
            event_id,
            asset_id,
            event_type,
            location,
            timestamp,
            status
        ) = event

        print(
            f"Event: {event_id} | "
            f"Asset: {asset_id} | "
            f"Type: {event_type} | "
            f"Location: {location} | "
            f"Time: {timestamp} | "
            f"Status: {status}"
        )

else:

    print("No events recorded.")


# ==========================================
# 11. SYSTEM SUMMARY
# ==========================================

print_heading("SYSTEM SUMMARY")

print(f"Total registered assets: {len(final_report)}")

summary_statuses = [
    NORMAL,
    MISPLACED,
    MISSING_INVESTIGATION,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNAUTHORIZED_REMOVAL,
    UNKNOWN_ASSET
]

for status in summary_statuses:

    count = sum(
        item["final_status"] == status
        for item in final_report
    )

    print(f"{status}: {count}")


print_heading("PHASE 2 EXECUTION COMPLETED")
