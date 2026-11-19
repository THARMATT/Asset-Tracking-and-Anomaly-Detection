"""Interactive Streamlit dashboard for the IoT asset tracker.

Supports built-in simulation and live ESP32 telemetry written by mqtt_bridge.py.
Temperature is simulated in the Python backend for the Wokwi demonstration.
"""
from __future__ import annotations

from pathlib import Path
import json
import random

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from asset_movement import advance_position
from asset_tracker import (
    ANOMALY_FIELDS,
    ASSETS,
    LATEST_FIELDS,
    TELEMETRY_FIELDS,
    GEOFENCE_RADIUS_M,
    detect_anomalies,
    evaluate_geofence,
    make_geofence_event,
    run_simulation,
    utc_timestamp,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TELEMETRY_FILE = DATA_DIR / "telemetry.csv"
ANOMALY_FILE = DATA_DIR / "anomaly_log.csv"
LATEST_FILE = DATA_DIR / "latest_assets.csv"
STATUS_COLORS = {"NORMAL": "#16a34a", "ALERT": "#dc2626", "UNKNOWN": "#64748b"}

st.set_page_config(
    page_title="IoT Asset Tracker",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
      div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25); padding: 12px 14px; border-radius: 12px;}
      .subtle {color: #7c8798; font-size: .92rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
        return pd.DataFrame()


def ensure_data_exists() -> None:
    """Create initial sample data so the dashboard is populated on first launch."""
    if not LATEST_FILE.exists() or not TELEMETRY_FILE.exists():
        run_simulation(
            iterations=1, interval=0, output_dir=DATA_DIR, seed=None,
            demo_anomalies=True,
        )


def generate_cycle() -> None:
    """Append a telemetry cycle, move assets, and detect geofence transitions."""
    st.session_state["map_pulse_phase"] = 1 - int(st.session_state.get("map_pulse_phase", 0))
    first_cycle = not TELEMETRY_FILE.exists() or TELEMETRY_FILE.stat().st_size == 0
    previous = read_csv_or_empty(LATEST_FILE)
    previous_positions = {}
    previous_geofence_states = {}
    if not previous.empty and {"asset_id", "latitude", "longitude"}.issubset(previous.columns):
        for _, row in previous.iterrows():
            asset_id = str(row["asset_id"])
            try:
                old_lat, old_lon = float(row["latitude"]), float(row["longitude"])
                previous_positions[asset_id] = (old_lat, old_lon)
                stored_state = str(row.get("geofence_status", "")).upper()
                if stored_state in {"INSIDE", "OUTSIDE"}:
                    previous_geofence_states[asset_id] = stored_state
                else:
                    previous_geofence_states[asset_id] = evaluate_geofence(
                        asset_id, old_lat, old_lon, GEOFENCE_RADIUS_M
                    )[0]
            except (TypeError, ValueError):
                continue

    run_simulation(
        iterations=1,
        interval=0,
        output_dir=DATA_DIR,
        seed=random.SystemRandom().randint(0, 2**31 - 1),
        demo_anomalies=first_cycle,
    )

    # Keep snapshot and newest telemetry batch aligned with the moving map markers.
    latest = read_csv_or_empty(LATEST_FILE)
    telemetry = read_csv_or_empty(TELEMETRY_FILE)
    if latest.empty or telemetry.empty:
        return
    # CSV files from older runs may contain these columns as strings. Normalize
    # them before assigning floating-point distances/radii below.
    if "geofence_status" not in latest.columns:
        latest["geofence_status"] = ""
    for numeric_column in ("geofence_distance_m", "geofence_radius_m"):
        if numeric_column not in latest.columns:
            latest[numeric_column] = float("nan")
        latest[numeric_column] = pd.to_numeric(
            latest[numeric_column], errors="coerce"
        ).astype(float)
    new_positions = {}
    for _, row in latest.iterrows():
        asset_id = str(row["asset_id"])
        try:
            old_lat, old_lon = previous_positions.get(
                asset_id, (float(row["latitude"]), float(row["longitude"]))
            )
            new_positions[asset_id] = advance_position(asset_id, old_lat, old_lon)
        except (TypeError, ValueError, KeyError):
            continue

    for index, row in latest.iterrows():
        asset_id = str(row["asset_id"])
        if asset_id in new_positions:
            latest.loc[index, ["latitude", "longitude"]] = new_positions[asset_id]

    geofence_events = []
    for index, row in latest.iterrows():
        asset_id = str(row["asset_id"])
        try:
            state, distance_m = evaluate_geofence(
                asset_id, float(row["latitude"]), float(row["longitude"]), GEOFENCE_RADIUS_M
            )
        except (TypeError, ValueError):
            continue
        previous_state = previous_geofence_states.get(asset_id, "INSIDE")
        if state != previous_state:
            event_type = "EXIT" if state == "OUTSIDE" else "ENTRY"
            geofence_events.append(make_geofence_event(row.to_dict(), distance_m, event_type))

        try:
            sensor_anomalies = int(float(row.get("anomalies", 0) or 0))
        except (TypeError, ValueError):
            sensor_anomalies = 0
        latest.loc[index, "geofence_status"] = state
        latest.loc[index, "geofence_distance_m"] = distance_m
        latest.loc[index, "geofence_radius_m"] = GEOFENCE_RADIUS_M
        latest.loc[index, "status"] = "ALERT" if state == "OUTSIDE" or sensor_anomalies > 0 else "NORMAL"
        latest.loc[index, "anomalies"] = sensor_anomalies + (1 if state == "OUTSIDE" else 0)

    # Update the current telemetry batch with the same coordinates and geofence state.
    batch_size = len(ASSETS)
    batch_indices = telemetry.tail(batch_size).index
    latest_by_id = latest.set_index(latest["asset_id"].astype(str))
    for index in batch_indices:
        asset_id = str(telemetry.loc[index, "asset_id"])
        if asset_id in new_positions and asset_id in latest_by_id.index:
            telemetry.loc[index, ["latitude", "longitude"]] = new_positions[asset_id]
        if asset_id in latest_by_id.index:
            for column in ("geofence_status", "geofence_distance_m", "geofence_radius_m", "status", "anomalies"):
                telemetry.loc[index, column] = latest_by_id.loc[asset_id, column]

    latest.to_csv(LATEST_FILE, index=False)
    telemetry.to_csv(TELEMETRY_FILE, index=False)
    if geofence_events:
        pd.DataFrame(geofence_events, columns=ANOMALY_FIELDS).to_csv(
            ANOMALY_FILE, mode="a", header=not ANOMALY_FILE.exists() or ANOMALY_FILE.stat().st_size == 0,
            index=False,
        )


def inject_test_alert(asset_id: str, alert_type: str) -> str:
    """Create a clearly labelled synthetic alert for a live demonstration."""
    latest = read_csv_or_empty(LATEST_FILE)
    if latest.empty or asset_id not in latest["asset_id"].astype(str).values:
        raise ValueError("Choose a valid asset before triggering a test alert.")

    row = latest.loc[latest["asset_id"].astype(str) == asset_id].iloc[0].to_dict()
    row["timestamp"] = utc_timestamp()
    if alert_type == "High temperature":
        row["temperature_c"] = 58.0
    elif alert_type == "Low battery":
        row["battery_pct"] = 8.0
    elif alert_type == "Overspeed":
        row["speed_kmh"] = 105.0
    elif alert_type == "Asset out of boundary":
        asset = next(item for item in ASSETS if item.asset_id == asset_id)
        # Move the simulated asset about 330 metres north of its home centre.
        row["latitude"] = round(asset.latitude + 0.003, 6)
        row["longitude"] = asset.longitude
        state, distance_m = evaluate_geofence(asset_id, row["latitude"], row["longitude"])
        row["geofence_status"] = state
        row["geofence_distance_m"] = distance_m
        row["geofence_radius_m"] = GEOFENCE_RADIUS_M
    else:
        raise ValueError("Unsupported test alert type.")

    events = detect_anomalies(row)
    if alert_type == "Asset out of boundary":
        events.append(make_geofence_event(row, float(row["geofence_distance_m"]), "EXIT"))
    row["anomalies"] = len(events)
    row["status"] = "ALERT"
    row["demo_event"] = True

    telemetry_row = {field: row.get(field, "") for field in TELEMETRY_FIELDS}
    telemetry_row.update({
        "geofence_status": row.get("geofence_status", ""),
        "geofence_distance_m": row.get("geofence_distance_m", ""),
        "geofence_radius_m": row.get("geofence_radius_m", GEOFENCE_RADIUS_M),
    })
    anomaly_rows = [{field: event.get(field, "") for field in ANOMALY_FIELDS} for event in events]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([telemetry_row]).to_csv(
        TELEMETRY_FILE, mode="a", header=not TELEMETRY_FILE.exists() or TELEMETRY_FILE.stat().st_size == 0,
        index=False,
    )
    if anomaly_rows:
        pd.DataFrame(anomaly_rows, columns=ANOMALY_FIELDS).to_csv(
            ANOMALY_FILE, mode="a", header=not ANOMALY_FILE.exists() or ANOMALY_FILE.stat().st_size == 0,
            index=False,
        )
    # Keep only canonical latest columns plus the geofence state fields.
    if "geofence_status" not in latest.columns:
        latest["geofence_status"] = ""
    for numeric_column in ("geofence_distance_m", "geofence_radius_m"):
        if numeric_column not in latest.columns:
            latest[numeric_column] = float("nan")
        latest[numeric_column] = pd.to_numeric(
            latest[numeric_column], errors="coerce"
        ).astype(float)
    latest.loc[latest["asset_id"].astype(str) == asset_id, LATEST_FIELDS] = [row.get(c, "") for c in LATEST_FIELDS]
    for column in ("geofence_status", "geofence_distance_m", "geofence_radius_m"):
        latest.loc[latest["asset_id"].astype(str) == asset_id, column] = row.get(column, "")
    latest.to_csv(LATEST_FILE, index=False)
    return f"Test alert created for {asset_id}: {alert_type}."


ensure_data_exists()

st.title("📡 IoT Asset Tracking & Anomaly Detection")
st.caption("ESP32/Wokwi telemetry over MQTT + backend-simulated temperature · Rule-based anomaly detection")

with st.sidebar:
    st.header("Live controls")
    data_source = st.radio(
        "Telemetry source",
        ["ESP32 via MQTT", "Built-in simulation"],
        index=0,
        help="ESP32 mode reads telemetry written by mqtt_bridge.py. Built-in simulation generates local demo data.",
    )
    mqtt_mode = data_source == "ESP32 via MQTT"
    auto_live = st.toggle(
        "Enable dashboard refresh", value=True,
        help="Refresh the dashboard to display the latest CSV data.",
    )
    refresh_seconds = st.slider(
        "Update interval (seconds)", min_value=2, max_value=15, value=3,
        step=1, disabled=not auto_live,
    )
    if auto_live:
        tick = st_autorefresh(interval=refresh_seconds * 1000, key="iot_live_refresh")
        if mqtt_mode:
            st.success("ESP32/MQTT mode · waiting for device telemetry")
        else:
            st.success(f"Simulation mode · refreshing every {refresh_seconds}s")
            if "last_live_tick" not in st.session_state:
                st.session_state.last_live_tick = tick
            elif tick != st.session_state.last_live_tick:
                generate_cycle()
                st.session_state.last_live_tick = tick
    else:
        st.info("Dashboard auto-refresh is paused.")
    if st.button(
        "🔄 Generate new readings", type="primary", use_container_width=True,
        disabled=mqtt_mode,
    ):
        generate_cycle()
        st.rerun()
    if mqtt_mode:
        st.caption(
            "Start `python mqtt_bridge.py` in a separate terminal, then run Wokwi. "
            "The ESP32 publishes every 2 seconds; this dashboard reads the bridge's CSV updates."
        )

    st.divider()
    st.subheader("Demo an alert")
    st.caption("Inject a synthetic abnormal reading to demonstrate alert handling. This is test data.")
    demo_asset = st.selectbox("Asset", [asset.asset_id for asset in ASSETS], key="demo_asset")
    demo_alert_type = st.selectbox("Alert scenario", ["High temperature", "Low battery", "Overspeed", "Asset out of boundary"], key="demo_alert_type")
    if st.button("🚨 Trigger test alert", use_container_width=True):
        st.session_state.demo_alert_message = inject_test_alert(demo_asset, demo_alert_type)
        st.rerun()
    if st.session_state.get("demo_alert_message"):
        st.caption(st.session_state.demo_alert_message)

    st.divider()
    st.subheader("Detection thresholds")
    st.write("Temperature high: **> 45 °C**")
    st.write("Temperature low: **< -5 °C**")
    st.write("Battery low: **< 15%**")
    st.write("Speed high: **> 80 km/h**")
    st.write(f"Geofence: **outside {GEOFENCE_RADIUS_M:.0f} m from each asset home point**")
    st.caption("Example thresholds for a university prototype, not certified safety limits.")
    if st.button("🧹 Reset demo data", use_container_width=True):
        for path in (TELEMETRY_FILE, ANOMALY_FILE, LATEST_FILE):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                st.error(f"Could not remove {path.name}: {exc}")
        st.session_state.pop("demo_alert_message", None)
        st.rerun()

latest = read_csv_or_empty(LATEST_FILE)
telemetry = read_csv_or_empty(TELEMETRY_FILE)
anomalies = read_csv_or_empty(ANOMALY_FILE)
if latest.empty:
    st.warning("No latest asset data found. Click Generate new readings.")
    st.stop()

if mqtt_mode:
    mqtt_rows = (
        latest.loc[latest.get("telemetry_source", pd.Series(index=latest.index, dtype=str))
                   .astype(str).eq("ESP32_MQTT")]
        if "telemetry_source" in latest.columns else pd.DataFrame()
    )
    if mqtt_rows.empty:
        st.warning(
            "No ESP32 MQTT packet has been received yet. Start `python mqtt_bridge.py`, "
            "then start the Wokwi simulation. The dashboard will refresh automatically."
        )
    else:
        newest_device_time = str(mqtt_rows["timestamp"].max())
        st.success(
            f"ESP32 MQTT connected · latest ASSET_001 telemetry: {newest_device_time}"
        )

for frame, columns in (
    (latest, ("temperature_c", "battery_pct", "speed_kmh", "latitude", "longitude", "anomalies")),
    (telemetry, ("temperature_c", "battery_pct", "speed_kmh", "latitude", "longitude")),
    (anomalies, ("observed_value", "threshold")),
):
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
# Add geofence columns to existing CSVs created by earlier versions of the project.
if "geofence_status" not in latest.columns:
    latest["geofence_status"] = ""
for numeric_column in ("geofence_distance_m", "geofence_radius_m"):
    if numeric_column not in latest.columns:
        latest[numeric_column] = float("nan")
    latest[numeric_column] = pd.to_numeric(
        latest[numeric_column], errors="coerce"
    ).astype(float)
if "geofence_status" in latest.columns:
    migration_events = []
    for index, row in latest.iterrows():
        status_value = str(row.get("geofence_status", "")).upper()
        if status_value not in {"INSIDE", "OUTSIDE"}:
            try:
                state, distance_m = evaluate_geofence(
                    str(row["asset_id"]), float(row["latitude"]), float(row["longitude"]), GEOFENCE_RADIUS_M
                )
            except (KeyError, TypeError, ValueError):
                continue
            latest.loc[index, "geofence_status"] = state
            latest.loc[index, "geofence_distance_m"] = distance_m
            latest.loc[index, "geofence_radius_m"] = GEOFENCE_RADIUS_M
            try:
                count = int(float(row.get("anomalies", 0) or 0))
            except (TypeError, ValueError):
                count = 0
            latest.loc[index, "anomalies"] = count + (1 if state == "OUTSIDE" else 0)
            if state == "OUTSIDE":
                latest.loc[index, "status"] = "ALERT"
                migration_events.append(make_geofence_event(row.to_dict(), distance_m, "EXIT"))
    latest.to_csv(LATEST_FILE, index=False)
    if migration_events:
        pd.DataFrame(migration_events, columns=ANOMALY_FIELDS).to_csv(
            ANOMALY_FILE, mode="a", header=not ANOMALY_FILE.exists() or ANOMALY_FILE.stat().st_size == 0,
            index=False,
        )
        anomalies = pd.concat([anomalies, pd.DataFrame(migration_events)], ignore_index=True)

if "timestamp" in telemetry.columns:
    telemetry["timestamp"] = pd.to_datetime(telemetry["timestamp"], errors="coerce", utc=True)
if "timestamp" in anomalies.columns:
    anomalies["timestamp"] = pd.to_datetime(anomalies["timestamp"], errors="coerce", utc=True)

asset_count = int(latest["asset_id"].nunique()) if "asset_id" in latest else len(latest)
alert_count = int((latest["status"].astype(str).str.upper() == "ALERT").sum()) if "status" in latest else 0
normal_count = max(asset_count - alert_count, 0)
event_count = len(anomalies)
latest_time = str(latest["timestamp"].max()) if "timestamp" in latest and not latest.empty else "Not available"

metric_cols = st.columns(4)
metric_cols[0].metric("Tracked assets", asset_count)
metric_cols[1].metric("Normal assets", normal_count)
metric_cols[2].metric("Assets in alert", alert_count, delta=f"{alert_count} need attention" if alert_count else "All clear", delta_color="inverse")
metric_cols[3].metric("Logged anomaly events", event_count)
st.caption(f"Latest telemetry update: {latest_time} · Total telemetry records: {len(telemetry)}")

if alert_count:
    active_alerts = latest.loc[latest["status"].astype(str).str.upper() == "ALERT"]
    alert_text = ", ".join(active_alerts["asset_id"].astype(str).tolist())
    st.error(f"⚠️ Active alert on {alert_text}. Review the current asset status and anomaly log below.")
else:
    st.success("✅ All assets are currently within the configured limits.")

if "geofence_status" in latest.columns:
    outside_assets = latest.loc[latest["geofence_status"].astype(str).str.upper() == "OUTSIDE"]
    if not outside_assets.empty:
        outside_details = ", ".join(
            f"{row['asset_id']} ({float(row.get('geofence_distance_m', 0)):.0f} m from home)"
            for _, row in outside_assets.iterrows()
        )
        st.error(f"🚨 ASSET OUT OF BOUNDARY: {outside_details}")

with st.expander("🧰 Proposed sensors and low-power communication", expanded=False):
    st.caption("ESP32 telemetry is received through MQTT in device mode. Temperature is simulated by the Python backend because the Wokwi DHT22 was unreliable; the remaining listed sensors are proposed real-world options.")
    sensor_cols = st.columns(4)
    with sensor_cols[0]:
        st.markdown("**🌡️ Temperature**")
        st.markdown("**DS18B20** digital temperature probe")
        st.caption("Measures ambient or equipment temperature; a waterproof probe is available.")
    with sensor_cols[1]:
        st.markdown("**🔋 Battery level**")
        st.markdown("**MAX17048** fuel gauge")
        st.caption("Estimates state of charge for a compatible single-cell lithium battery. A voltage divider is a simpler alternative.")
    with sensor_cols[2]:
        st.markdown("**🧠 Controller**")
        st.markdown("**ESP32** microcontroller")
        st.caption("Reads sensor data, prepares telemetry and manages low-power operation.")
    with sensor_cols[3]:
        st.markdown("**📡 Communication**")
        st.markdown("**LoRa / BLE**")
        st.caption("LoRa suits longer-range, small messages; BLE suits nearby assets and normally uses a gateway.")
    st.info("Current demo data path: ESP32/Wokwi → Wi-Fi → MQTT broker → Python bridge (temperature simulation + geofence + anomaly rules) → CSV data → Streamlit dashboard. GPS, speed and battery are simulated by the Wokwi device; no physical sensor is required.")

st.divider()
left, right = st.columns([1.15, 1])
selected_map_asset = None
with left:
    st.subheader("🗺️ Live asset map")
    st.caption(f"Markers show the latest device/simulator coordinates. Blue dashed circles show each asset’s {GEOFENCE_RADIUS_M:.0f} m permitted zone; red markers indicate an active alert, including an out-of-boundary asset.")
    if {"latitude", "longitude"}.issubset(latest.columns):
        map_df = latest.dropna(subset=["latitude", "longitude"]).copy()
        if not map_df.empty:
            map_df["Map status"] = map_df["status"].fillna("UNKNOWN")
            assets_for_map = []
            for _, row in map_df.iterrows():
                assets_for_map.append({
                    "asset_id": str(row.get("asset_id", "Unknown")),
                    "lat": float(row["latitude"]), "lon": float(row["longitude"]),
                    "status": str(row.get("Map status", "UNKNOWN")).upper(),
                    "asset_type": str(row.get("asset_type", "Unknown")),
                    "zone": str(row.get("zone", "Unknown")),
                    "temperature": float(row.get("temperature_c", 0) or 0),
                    "battery": float(row.get("battery_pct", 0) or 0),
                    "speed": float(row.get("speed_kmh", 0) or 0),
                    "geofence_status": str(row.get("geofence_status", "INSIDE")).upper(),
                    "geofence_distance_m": float(row.get("geofence_distance_m", 0) or 0),
                    "geofence_radius_m": float(row.get("geofence_radius_m", GEOFENCE_RADIUS_M) or GEOFENCE_RADIUS_M),
                    "home_lat": next(item.latitude for item in ASSETS if item.asset_id == str(row.get("asset_id"))),
                    "home_lon": next(item.longitude for item in ASSETS if item.asset_id == str(row.get("asset_id"))),
                })
            trails_for_map = {}
            if not telemetry.empty and {"asset_id", "latitude", "longitude"}.issubset(telemetry.columns):
                trail_data = telemetry.dropna(subset=["latitude", "longitude"]).copy()
                if "timestamp" in trail_data.columns:
                    trail_data["timestamp"] = pd.to_datetime(trail_data["timestamp"], errors="coerce", utc=True)
                    trail_data = trail_data.dropna(subset=["timestamp"]).sort_values("timestamp")
                for asset_id, trail in trail_data.groupby("asset_id"):
                    trails_for_map[str(asset_id)] = [
                        [float(r["latitude"]), float(r["longitude"])]
                        for _, r in trail.tail(12).iterrows()
                    ]
            # Leaflet markers use CSS keyframe animation, so the pulse continues
            # between Streamlit refreshes rather than changing only on reruns.
            map_html = r'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body,#map{height:100%;width:100%;margin:0;padding:0} .leaflet-container{font:13px sans-serif}
.asset-dot{position:relative;width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 1px 5px #3338;}
.asset-dot:before{content:"";position:absolute;left:-7px;top:-7px;width:24px;height:24px;border-radius:50%;background:inherit;opacity:.65;animation:assetPulse 1.6s ease-out infinite;}
.asset-dot.alert:before{animation-duration:1s}
@keyframes assetPulse{0%{transform:scale(.55);opacity:.75}70%{transform:scale(1.7);opacity:.18}100%{transform:scale(2.1);opacity:0}}
.legend{background:white;padding:7px 10px;border-radius:5px;box-shadow:0 1px 5px #7778;line-height:1.7}.legend span{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
</style></head><body><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const assets = __ASSETS__;
const trails = __TRAILS__;
const map = L.map('map').setView([assets.reduce((s,a)=>s+a.lat,0)/assets.length,assets.reduce((s,a)=>s+a.lon,0)/assets.length],12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
const colors={NORMAL:'#16a34a',ALERT:'#dc2626',UNKNOWN:'#64748b'};
const fenceLayers=[];
// Draw a high-contrast circle around each configured home coordinate.
// Leaflet's radius is in metres; its center is [latitude, longitude].
assets.forEach(a=>{
 const center=[Number(a.home_lat),Number(a.home_lon)];
 const radius=Math.max(1,Number(a.geofence_radius_m)||150);
 const fence=L.circle(center,{radius:radius,color:'#0047AB',weight:4,opacity:1,dashArray:'10 7',fillColor:'#3B82F6',fillOpacity:0.12,interactive:true}).addTo(map);
 fence.bindTooltip(`${a.asset_id} boundary · radius ${radius.toFixed(0)} m · center ${a.home_lat.toFixed(6)}, ${a.home_lon.toFixed(6)}`,{sticky:true});
 // Visible center pin makes the exact reference coordinates unambiguous.
 const centerPin=L.circleMarker(center,{radius:5,color:'#FFFFFF',weight:2,fillColor:'#0047AB',fillOpacity:1}).addTo(map);
 centerPin.bindPopup(`<b>${a.asset_id} geofence center</b><br>Center latitude: ${a.home_lat.toFixed(6)}<br>Center longitude: ${a.home_lon.toFixed(6)}<br>Radius: ${radius.toFixed(0)} m`);
 fenceLayers.push(fence);
});
Object.entries(trails).forEach(([id,coords])=>{if(coords.length>1)L.polyline(coords,{color:'#64748b',weight:3,opacity:.55}).addTo(map)});
// Bring the geofence outlines back above trails so they remain easy to see.
fenceLayers.forEach(f=>f.bringToFront());
assets.forEach(a=>{
 const outside=a.geofence_status==='OUTSIDE';
 const color=outside?'#dc2626':(colors[a.status]||colors.UNKNOWN);
 if(outside){L.polyline([[a.home_lat,a.home_lon],[a.lat,a.lon]],{color:'#dc2626',weight:2,dashArray:'4 5',opacity:.9}).addTo(map);}
 const icon=L.divIcon({className:'',html:`<div class="asset-dot ${a.status==='ALERT'||outside?'alert':''}" style="background:${color};${outside?'outline:3px solid #fecaca;':''}"></div>`,iconSize:[18,18],iconAnchor:[9,9]});
 L.marker([a.lat,a.lon],{icon}).addTo(map).bindPopup(`<b>${a.asset_id}</b><br>Status: ${a.status}<br>Type: ${a.asset_type}<br>Zone: ${a.zone}<br>Temperature: ${a.temperature.toFixed(1)} °C<br>Battery: ${a.battery.toFixed(1)}%<br>Speed: ${a.speed.toFixed(1)} km/h<br>Geofence: ${a.geofence_status}<br>Distance from center: ${a.geofence_distance_m.toFixed(1)} m<br>Boundary radius: ${a.geofence_radius_m.toFixed(0)} m<br>Center latitude: ${a.home_lat.toFixed(6)}<br>Center longitude: ${a.home_lon.toFixed(6)}`);
});
L.control({position:'bottomleft'}).onAdd=function(){const d=L.DomUtil.create('div','legend');d.innerHTML='<div><span style="background:#16a34a"></span>Normal asset</div><div><span style="background:#dc2626"></span>Alert / outside boundary</div><div style="border-top:3px dashed #0047ab;margin:4px 0;padding-top:3px">Blue dashed circle = permitted geofence</div><div><span style="background:#0047ab"></span>Circle center (click for coordinates)</div><div style="color:#dc2626">Red dashed line = outside asset to center</div>';return d}.addTo(map);
const allBounds=L.latLngBounds([]);
assets.forEach(a=>{allBounds.extend([a.lat,a.lon]);allBounds.extend([a.home_lat,a.home_lon]);});
fenceLayers.forEach(f=>allBounds.extend(f.getBounds()));
if(allBounds.isValid())map.fitBounds(allBounds.pad(.15),{maxZoom:15});
</script></body></html>'''
            map_html = map_html.replace("__ASSETS__", json.dumps(assets_for_map)).replace("__TRAILS__", json.dumps(trails_for_map))
            components.html(map_html, height=460, scrolling=False)
            st.caption("Blue dashed circles show the 150 m permitted geofence around each asset's configured home point. Click the blue center dot for the exact center latitude/longitude; click an asset for its distance from that center. Outside assets are red, with a red dashed line back to the center.")
            center_rows = [{"Asset": a["asset_id"], "Center latitude": f'{a["home_lat"]:.6f}', "Center longitude": f'{a["home_lon"]:.6f}', "Radius (m)": round(a["geofence_radius_m"])} for a in assets_for_map]
            with st.expander("Geofence centers and coordinates", expanded=True):
                st.dataframe(pd.DataFrame(center_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No valid coordinates available for the current asset snapshot.")
    else:
        st.info("Location fields are not present in the latest data.")

with right:
    st.subheader("Current asset status")
    status_df = latest.copy()
    display_columns = [c for c in ["asset_id", "asset_type", "zone", "status", "geofence_status", "geofence_distance_m", "anomalies"] if c in status_df]
    if "status" in status_df:
        status_df = status_df.sort_values("status", ascending=True)
    st.dataframe(status_df[display_columns], use_container_width=True, hide_index=True, height=390)

# Streamlit Plotly selection lets users click a marker; the dropdown is a reliable fallback.
st.subheader("🔎 Inspect an asset")
asset_ids = sorted(latest["asset_id"].dropna().astype(str).unique().tolist())
default_asset_index = asset_ids.index(selected_map_asset) if selected_map_asset in asset_ids else 0
inspected_asset = st.selectbox(
    "Selected from map (or choose here)", asset_ids, index=default_asset_index, key="inspected_asset"
)
asset_row = latest.loc[latest["asset_id"].astype(str) == inspected_asset].iloc[0]
detail_cols = st.columns(5)
detail_cols[0].metric("Status", str(asset_row.get("status", "UNKNOWN")))
detail_cols[1].metric("Speed", f"{float(asset_row.get('speed_kmh', 0)):.1f} km/h")
detail_cols[2].metric("Temperature", f"{float(asset_row.get('temperature_c', 0)):.1f} °C")
detail_cols[3].metric("Battery", f"{float(asset_row.get('battery_pct', 0)):.1f}%")
detail_cols[4].metric("Zone", str(asset_row.get("zone", "Unknown")))
st.caption(f"Coordinates: {float(asset_row.get('latitude', 0)):.5f}, {float(asset_row.get('longitude', 0)):.5f} · {inspected_asset}")

st.divider()
st.subheader("📈 Live telemetry history")
selected_history_asset = st.selectbox("Inspect asset history", ["All assets"] + asset_ids)
if not telemetry.empty and "timestamp" in telemetry.columns:
    history = telemetry.dropna(subset=["timestamp"]).sort_values("timestamp").tail(800).copy()
    if selected_history_asset != "All assets":
        history = history[history["asset_id"].astype(str) == selected_history_asset]
    if not history.empty:
        history_metric = st.selectbox("Telemetry to plot", ["temperature_c", "battery_pct", "speed_kmh"], format_func=lambda value: {
            "temperature_c": "Temperature (°C)", "battery_pct": "Battery (%)", "speed_kmh": "Speed (km/h)"
        }[value])
        labels = {"temperature_c": "Temperature (°C)", "battery_pct": "Battery (%)", "speed_kmh": "Speed (km/h)"}
        fig_history = px.line(history, x="timestamp", y=history_metric, color="asset_id" if selected_history_asset == "All assets" else None,
                              markers=True, labels={"timestamp": "Time", history_metric: labels[history_metric], "asset_id": "Asset"})
        if history_metric == "temperature_c":
            fig_history.add_hline(y=45, line_dash="dash", annotation_text="High threshold")
            fig_history.add_hline(y=-5, line_dash="dash", annotation_text="Low threshold")
        elif history_metric == "battery_pct":
            fig_history.add_hline(y=15, line_dash="dash", annotation_text="Low threshold")
        elif history_metric == "speed_kmh":
            fig_history.add_hline(y=80, line_dash="dash", annotation_text="High threshold")
        fig_history.update_layout(height=360, margin=dict(l=5, r=5, t=15, b=5))
        st.plotly_chart(fig_history, use_container_width=True)
        st.caption("History is built from saved simulation cycles. Enable Live mode to watch it grow automatically.")
    else:
        st.info("No history is available for this asset yet.")
else:
    st.info("Telemetry history will appear after the first simulator cycle.")

st.divider()
st.subheader("Current readings by asset")
chart_left, chart_mid, chart_right = st.columns(3)
with chart_left:
    st.markdown("**Temperature (°C)**")
    fig_temp = px.bar(latest, x="asset_id", y="temperature_c", color="status", color_discrete_map=STATUS_COLORS)
    fig_temp.add_hline(y=45, line_dash="dash", annotation_text="High threshold")
    fig_temp.update_layout(height=300, margin=dict(l=5, r=5, t=10, b=5), xaxis_title="Asset", yaxis_title="°C", showlegend=False)
    st.plotly_chart(fig_temp, use_container_width=True)
with chart_mid:
    st.markdown("**Battery (%)**")
    fig_battery = px.bar(latest, x="asset_id", y="battery_pct", color="status", color_discrete_map=STATUS_COLORS)
    fig_battery.add_hline(y=15, line_dash="dash", annotation_text="Low threshold")
    fig_battery.update_layout(height=300, margin=dict(l=5, r=5, t=10, b=5), xaxis_title="Asset", yaxis_title="%", showlegend=False)
    st.plotly_chart(fig_battery, use_container_width=True)
with chart_right:
    st.markdown("**Speed (km/h)**")
    fig_speed = px.bar(latest, x="asset_id", y="speed_kmh", color="status", color_discrete_map=STATUS_COLORS)
    fig_speed.add_hline(y=80, line_dash="dash", annotation_text="High threshold")
    fig_speed.update_layout(height=300, margin=dict(l=5, r=5, t=10, b=5), xaxis_title="Asset", yaxis_title="km/h", showlegend=False)
    st.plotly_chart(fig_speed, use_container_width=True)

st.divider()
st.subheader("🚨 Anomaly event log")
if anomalies.empty:
    st.success("No anomaly events have been logged yet.")
else:
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        asset_options = ["All assets"] + sorted(anomalies["asset_id"].dropna().astype(str).unique().tolist())
        selected_alert_asset = st.selectbox("Filter by asset", asset_options)
    with filter_col2:
        severity_options = ["All severities"] + sorted(anomalies["severity"].dropna().astype(str).unique().tolist())
        selected_severity = st.selectbox("Filter by severity", severity_options)
    filtered = anomalies.copy()
    if selected_alert_asset != "All assets":
        filtered = filtered[filtered["asset_id"].astype(str) == selected_alert_asset]
    if selected_severity != "All severities":
        filtered = filtered[filtered["severity"].astype(str) == selected_severity]
    preferred = ["timestamp", "asset_id", "zone", "metric", "observed_value", "threshold", "severity", "message"]
    shown = [column for column in preferred if column in filtered.columns]
    if "timestamp" in filtered.columns:
        filtered = filtered.sort_values("timestamp", ascending=False)
    st.dataframe(filtered[shown], use_container_width=True, hide_index=True)

with st.expander("About this prototype"):
    st.markdown(
        "- **Tracking:** eight sample assets plus the Wokwi ESP32 demo asset (ASSET_001).\\n"
        "- **Interactive map:** click markers to inspect assets; recent telemetry forms route trails and markers pulse by status.\\n"
        "- **Device integration:** Wokwi ESP32 publishes GPS-like coordinates, battery and speed through MQTT; Python simulates temperature because DHT22 readings were unreliable.\\n"
        "- **Live mode:** choose ESP32/MQTT to display device telemetry, or built-in simulation for local sample data.\\n"
        "- **Telemetry history:** plots saved readings over time and supports per-asset inspection.\\n"
        "- **Demo alert:** injects a labelled synthetic event for presentations.\\n"
        "- **Geofencing:** a 150 m circular boundary around each asset home point; alerts are logged on exit and re-entry.\\n"
        "- **Detection:** transparent threshold rules; no machine learning is used.\\n"
        "- **Storage:** CSV files in the project's `data` folder.\\n"
        "- **Limitations:** Wokwi readings are simulated; the public MQTT broker is for demonstration only, not production."
    )
