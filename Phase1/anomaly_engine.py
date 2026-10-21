
# ==========================================
# ANOMALY DETECTION ENGINE
# ==========================================

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


# ==========================================
# 1. CHECK ASSET LOCATION
# ==========================================

def check_location(expected_zone, detected_zone):

    # No location was detected
    if detected_zone is None:
        return MISSING

    # Asset is in its expected zone
    if detected_zone == expected_zone:
        return NORMAL

    # Asset is in a different zone
    return MISPLACED


# ==========================================
# 2. CHECK GATE AUTHORIZATION
# ==========================================

def check_gate_authorization(authorized):

    if authorized:
        return AUTHORIZED_EXIT

    return UNAUTHORIZED_EXIT


# ==========================================
# 3. DETERMINE FINAL ASSET STATUS
# ==========================================

def determine_final_status(
    internal_status,
    gate_detected,
    authorized
):

    # Asset is not registered
    if internal_status == UNKNOWN_ASSET:
        return UNKNOWN_ASSET

    # Registered asset has permission to exit
    if gate_detected and authorized:
        return AUTHORIZED_EXIT

    # Missing asset reaches the gate without permission
    if (
        internal_status == MISSING
        and gate_detected
        and not authorized
    ):
        return UNAUTHORIZED_REMOVAL

    # Asset reaches the gate without permission
    if gate_detected and not authorized:
        return UNAUTHORIZED_EXIT

    # Asset is in the wrong location
    if internal_status == MISPLACED:
        return MISPLACED

    # Asset was not detected and needs investigation
    if internal_status == MISSING:
        return MISSING_INVESTIGATION

    # No anomaly detected
    return NORMAL
