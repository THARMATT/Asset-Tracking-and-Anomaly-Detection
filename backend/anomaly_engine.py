# ==========================================
# ANOMALY DETECTION ENGINE
# IoT-Based Smart Asset Tracking System
# ==========================================

import logging
from typing import Optional, Dict, Any, List, Set, Collection, Tuple

from config import (
    NORMAL,
    MISPLACED,
    AUTHORIZED_EXIT,
    UNAUTHORIZED_EXIT,
    UNKNOWN_ASSET,
    MISSING_INVESTIGATION,
    INVALID_EVENT,
    MAIN_GATE,
    EVENT_TYPE_INTERNAL,
    EVENT_TYPE_GATE,
    EVENT_TYPE_AUDIT,
    RECOGNIZED_ZONES
)
from database import (
    get_asset,
    get_assets,
    check_exit_authorization,
    get_recognized_zones,
    save_event,
    save_audit_record,
    get_utc_now
)

logger = logging.getLogger(__name__)


# ==========================================
# 1. PAYLOAD VALIDATION
# ==========================================

def validate_event_payload(
    event_data: Any,
    allowed_zones: Optional[Set[str]] = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate that incoming event payload is well-formed, contains mandatory
    fields (asset_id and location), and references a recognized facility zone.
    Returns: (is_valid, error_reason, sanitized_payload)
    """
    if not isinstance(event_data, dict):
        return False, "Payload must be a JSON dictionary object", None

    # Check asset_id
    asset_id = event_data.get("asset_id")
    if asset_id is None or not str(asset_id).strip():
        return False, "Missing or empty required field: 'asset_id'", None

    # Check location / detected_zone
    location = event_data.get("location") or event_data.get("detected_zone")
    if location is None or not str(location).strip():
        return False, "Missing or empty required field: 'location'", None

    clean_asset_id = str(asset_id).strip()
    clean_location = str(location).strip()

    # Check against recognized facility zones
    valid_zones = allowed_zones if allowed_zones is not None else RECOGNIZED_ZONES
    if clean_location not in valid_zones:
        return (
            False,
            f"Unrecognized zone: '{clean_location}'. Must be one of: {sorted(list(valid_zones))}",
            None
        )

    sanitized = {
        "asset_id": clean_asset_id,
        "location": clean_location,
        "event_type": event_data.get("event_type"),
        "message_id": event_data.get("message_id"),
        "timestamp": event_data.get("timestamp") or get_utc_now(),
        "raw_payload": event_data
    }

    return True, None, sanitized


# ==========================================
# 2. SCAN EVENT EVALUATION
# ==========================================

def evaluate_scan_event(
    event_data: Any,
    db_path: Optional[str] = None,
    custom_recognized_zones: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """
    Evaluate an asset scan event against facility and security rules.
    Decoupled from Flask and database persistence.
    Returns a consistent structured dictionary.
    """
    # Determine recognized zones (combining default + DB dynamic zones)
    allowed_zones = custom_recognized_zones or get_recognized_zones(db_path=db_path)

    # Step 1: Validate payload format and required fields
    is_valid, error_msg, sanitized = validate_event_payload(event_data, allowed_zones)

    if not is_valid:
        raw_asset_id = event_data.get("asset_id") if isinstance(event_data, dict) else None
        raw_location = (
            event_data.get("location") or event_data.get("detected_zone")
            if isinstance(event_data, dict) else None
        )
        return {
            "status": INVALID_EVENT,
            "asset_id": str(raw_asset_id) if raw_asset_id else None,
            "detected_zone": str(raw_location) if raw_location else None,
            "expected_zone": None,
            "message": f"Malformed or invalid event: {error_msg}",
            "event_metadata": {
                "event_type": event_data.get("event_type") if isinstance(event_data, dict) else None,
                "message_id": event_data.get("message_id") if isinstance(event_data, dict) else None,
                "timestamp": get_utc_now(),
                "authorized": None,
                "is_anomaly": True,
                "severity": "WARNING"
            }
        }

    asset_id = sanitized["asset_id"]
    detected_zone = sanitized["location"]
    message_id = sanitized["message_id"]
    timestamp = sanitized["timestamp"]
    event_type = sanitized["event_type"] or (
        EVENT_TYPE_GATE if detected_zone == MAIN_GATE else EVENT_TYPE_INTERNAL
    )

    # Step 2: Check Asset Identity
    asset = get_asset(asset_id, db_path=db_path)

    if asset is None:
        return {
            "status": UNKNOWN_ASSET,
            "asset_id": asset_id,
            "detected_zone": detected_zone,
            "expected_zone": None,
            "message": f"Asset '{asset_id}' is not registered in the system (detected at {detected_zone}).",
            "event_metadata": {
                "event_type": event_type,
                "message_id": message_id,
                "timestamp": timestamp,
                "authorized": None,
                "is_anomaly": True,
                "severity": "WARNING"
            }
        }

    expected_zone = asset["expected_zone"]
    asset_name = asset["asset_name"]

    # Step 3: Location and Perimeter Gate Evaluation
    if detected_zone == MAIN_GATE:
        # Consult database exit authorization records
        is_authorized = check_exit_authorization(asset_id, db_path=db_path)

        if is_authorized:
            return {
                "status": AUTHORIZED_EXIT,
                "asset_id": asset_id,
                "detected_zone": MAIN_GATE,
                "expected_zone": expected_zone,
                "message": f"Asset '{asset_id}' ({asset_name}) detected at {MAIN_GATE} with valid exit authorization.",
                "event_metadata": {
                    "event_type": event_type,
                    "message_id": message_id,
                    "timestamp": timestamp,
                    "authorized": 1,
                    "is_anomaly": False,
                    "severity": "INFO"
                }
            }
        else:
            return {
                "status": UNAUTHORIZED_EXIT,
                "asset_id": asset_id,
                "detected_zone": MAIN_GATE,
                "expected_zone": expected_zone,
                "message": f"SECURITY ALERT: Asset '{asset_id}' ({asset_name}) detected at {MAIN_GATE} WITHOUT exit authorization.",
                "event_metadata": {
                    "event_type": event_type,
                    "message_id": message_id,
                    "timestamp": timestamp,
                    "authorized": 0,
                    "is_anomaly": True,
                    "severity": "HIGH"
                }
            }

    # Step 4: Internal Zone Evaluation
    if detected_zone == expected_zone:
        return {
            "status": NORMAL,
            "asset_id": asset_id,
            "detected_zone": detected_zone,
            "expected_zone": expected_zone,
            "message": f"Asset '{asset_id}' ({asset_name}) verified in expected zone '{expected_zone}'.",
            "event_metadata": {
                "event_type": event_type,
                "message_id": message_id,
                "timestamp": timestamp,
                "authorized": None,
                "is_anomaly": False,
                "severity": "NONE"
            }
        }
    else:
        return {
            "status": MISPLACED,
            "asset_id": asset_id,
            "detected_zone": detected_zone,
            "expected_zone": expected_zone,
            "message": f"Asset '{asset_id}' ({asset_name}) is misplaced in zone '{detected_zone}' (expected '{expected_zone}').",
            "event_metadata": {
                "event_type": event_type,
                "message_id": message_id,
                "timestamp": timestamp,
                "authorized": None,
                "is_anomaly": True,
                "severity": "WARNING"
            }
        }


# ==========================================
# 3. SCHEDULED INVENTORY AUDIT EVALUATION
# ==========================================

def evaluate_inventory_audit(
    scanned_asset_ids: Collection[str],
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform a formal inventory audit.
    Missing asset status is ONLY determined by this audit workflow.
    Assets not present in scanned_asset_ids are flagged with MISSING_INVESTIGATION_REQUIRED.
    """
    registered_assets = get_assets(active_only=True, db_path=db_path)
    scanned_set = {str(aid).strip() for aid in scanned_asset_ids if aid}

    audit_timestamp = get_utc_now()
    detected_assets: List[Dict[str, Any]] = []
    missing_evaluations: List[Dict[str, Any]] = []

    for asset in registered_assets:
        aid = asset["asset_id"]
        if aid in scanned_set:
            detected_assets.append(asset)
        else:
            missing_evaluations.append({
                "status": MISSING_INVESTIGATION,
                "asset_id": aid,
                "detected_zone": None,
                "expected_zone": asset["expected_zone"],
                "message": (
                    f"Inventory audit completed: Expected asset '{aid}' ({asset['asset_name']}) "
                    f"was not detected in '{asset['expected_zone']}'. Investigation required."
                ),
                "event_metadata": {
                    "event_type": EVENT_TYPE_AUDIT,
                    "message_id": None,
                    "timestamp": audit_timestamp,
                    "authorized": None,
                    "is_anomaly": True,
                    "severity": "MEDIUM"
                }
            })

    return {
        "audit_timestamp": audit_timestamp,
        "total_expected": len(registered_assets),
        "total_detected": len(detected_assets),
        "total_missing": len(missing_evaluations),
        "detected_asset_ids": [a["asset_id"] for a in detected_assets],
        "missing_asset_ids": [m["asset_id"] for m in missing_evaluations],
        "missing_evaluations": missing_evaluations,
        "all_assets_present": len(missing_evaluations) == 0
    }


# ==========================================
# 4. PERSISTENT INTEGRATION WRAPPERS
# ==========================================

def process_and_save_scan_event(
    event_data: Any,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate scan event and persist valid or anomaly tracking events into SQLite.
    Prevents duplicate event persistence via message_id.
    """
    evaluation = evaluate_scan_event(event_data, db_path=db_path)
    metadata = evaluation["event_metadata"]

    persisted = save_event(
        asset_id=evaluation["asset_id"],
        detected_zone=evaluation["detected_zone"] or "UNKNOWN_ZONE",
        event_type=metadata.get("event_type") or EVENT_TYPE_INTERNAL,
        status=evaluation["status"],
        message=evaluation["message"],
        authorized=metadata.get("authorized"),
        message_id=metadata.get("message_id"),
        raw_payload=event_data if isinstance(event_data, dict) else {"raw": str(event_data)},
        timestamp=metadata.get("timestamp"),
        db_path=db_path
    )

    evaluation["persistence"] = persisted
    return evaluation


def run_and_save_inventory_audit(
    scanned_asset_ids: Collection[str],
    notes: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute formal inventory audit, record individual MISSING_INVESTIGATION events,
    and save audit summary log.
    """
    audit_report = evaluate_inventory_audit(scanned_asset_ids, db_path=db_path)

    # Persist audit summary record
    audit_id = save_audit_record(
        total_expected=audit_report["total_expected"],
        detected_count=audit_report["total_detected"],
        missing_count=audit_report["total_missing"],
        missing_asset_ids=audit_report["missing_asset_ids"],
        notes=notes,
        timestamp=audit_report["audit_timestamp"],
        db_path=db_path
    )
    audit_report["audit_id"] = audit_id

    # Record individual audit events for each missing item
    for missing_eval in audit_report["missing_evaluations"]:
        save_event(
            asset_id=missing_eval["asset_id"],
            detected_zone="NOT_DETECTED",
            event_type=EVENT_TYPE_AUDIT,
            status=missing_eval["status"],
            message=missing_eval["message"],
            authorized=None,
            raw_payload={"audit_id": audit_id, "notes": notes},
            timestamp=audit_report["audit_timestamp"],
            db_path=db_path
        )

    return audit_report
