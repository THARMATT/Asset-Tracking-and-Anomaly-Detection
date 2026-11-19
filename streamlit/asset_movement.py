"""Deterministic route movement helpers for simulated IoT asset coordinates."""
from __future__ import annotations

from math import atan2, cos, radians, sin

from asset_tracker import ASSETS


def advance_position(asset_id: str, latitude: float, longitude: float) -> tuple[float, float]:
    """Advance an asset along a small circular route near its configured home zone.

    This function generates simulated coordinates only; it is not a GPS feed.
    It takes the previous position so the path progresses across dashboard reruns.
    """
    asset_index = next((i for i, asset in enumerate(ASSETS) if asset.asset_id == asset_id), 0)
    asset = next((item for item in ASSETS if item.asset_id == asset_id), ASSETS[0])
    longitude_scale = max(cos(radians(asset.latitude)), 0.1)
    x = (float(longitude) - asset.longitude) * longitude_scale
    y = float(latitude) - asset.latitude
    angle = atan2(y, x)
    if abs(x) + abs(y) < 0.00005:
        angle = asset_index * 0.79
    angle += 0.14 if asset_index % 2 == 0 else -0.14
    # Let the simulated route expand and contract so it can cross the 150 m
    # geofence boundary during a live demo, rather than staying on one circle.
    radius = (
        0.0010
        + (asset_index % 4) * 0.00012
        + 0.0004 * (0.5 + 0.5 * sin(angle * 2 + asset_index))
    )
    new_latitude = asset.latitude + radius * sin(angle)
    new_longitude = asset.longitude + (radius * cos(angle)) / longitude_scale
    return round(new_latitude, 6), round(new_longitude, 6)
