// ==========================================
// ASSET MAP COMPONENT — Full IoT Live Map
// IoT-Based Smart Asset Tracking System
// ==========================================
//
// Displays ALL assets (RFID + IoT simulation) on an interactive Leaflet map.
// - IoT assets (AST-001 … AST-008): moving markers with trail lines, live
//   telemetry cards (temperature, battery, speed), anomaly color-coding.
// - RFID assets (A001 … A005): static markers from /api/locations/latest
//   (only shown if a location has been posted for them).
// - Simulator control panel: Start / Pause / Tick / Stop the IoT engine.
// - Auto-refresh every 5 s when live mode is on.
//
// DESIGN CONSTRAINTS:
//   - Location / telemetry data is INDEPENDENT of RFID gate-authorization.
//   - Coordinates are labeled source='simulator'; NOT real GPS fixes.
//   - No API key required (OpenStreetMap tiles).
// ==========================================

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import {
  fetchIotStatus,
  fetchIotReadings,
  startIotSimulator,
  stopIotSimulator,
  pauseIotSimulator,
  resumeIotSimulator,
  triggerIotTick,
  fetchLatestLocations,
  fetchAssetLocationHistory,
} from '../api';

// ── Fix Leaflet icon paths in Vite ──────────────────────────────────────────
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// ── Custom Icons ─────────────────────────────────────────────────────────────
function makeIcon(color) {
  return new L.Icon({
    iconUrl:      `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
    shadowUrl:    'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize:     [25, 41],
    iconAnchor:   [12, 41],
    popupAnchor:  [1, -34],
    shadowSize:   [41, 41],
  });
}

const ICONS = {
  normal:  makeIcon('green'),
  alert:   makeIcon('red'),
  rfid:    makeIcon('blue'),
  unknown: makeIcon('grey'),
};

function iconFor(reading) {
  if (!reading) return ICONS.unknown;
  if (reading.status === 'ALERT') return ICONS.alert;
  return ICONS.normal;
}

// ── Map auto-fit helper ───────────────────────────────────────────────────────
function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points || points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 13);
    } else {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40] });
    }
  }, [points, map]);
  return null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(ts) {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleTimeString(); } catch { return ts; }
}

function statusBadge(status) {
  const colors = { NORMAL: '#16a34a', ALERT: '#dc2626', UNKNOWN: '#64748b' };
  const bg = colors[status] || colors.UNKNOWN;
  return (
    <span style={{
      background: bg, color: '#fff', borderRadius: 4,
      padding: '1px 7px', fontSize: 11, fontWeight: 700,
    }}>
      {status || 'UNKNOWN'}
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function AssetMap() {
  // IoT simulator state
  const [simStatus, setSimStatus]     = useState(null);
  const [iotReadings, setIotReadings] = useState([]);
  const [rfidLocs, setRfidLocs]       = useState([]);
  const [trails, setTrails]           = useState({});   // assetId -> [[lat,lon],…]
  const [selected, setSelected]       = useState(null); // assetId
  const [live, setLive]               = useState(true);
  const [lastTick, setLastTick]       = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState(null);

  const fetchingRef = useRef(false);

  // ── Fetch IoT readings + RFID locations ──────────────────────────────────
  const refresh = useCallback(async (quiet = false) => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const [statusRes, readingsRes, rfidRes] = await Promise.allSettled([
        fetchIotStatus(),
        fetchIotReadings(),
        fetchLatestLocations(),
      ]);
      if (statusRes.status === 'fulfilled')   setSimStatus(statusRes.value);
      if (readingsRes.status === 'fulfilled') setIotReadings(readingsRes.value || []);
      if (rfidRes.status === 'fulfilled')     setRfidLocs(rfidRes.value || []);
      setLastTick(new Date());
    } catch (e) {
      setError('Could not reach the backend. Make sure Flask is running on port 5000.');
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, []);

  // ── Load trail for selected asset ─────────────────────────────────────────
  useEffect(() => {
    if (!selected) return;
    fetchAssetLocationHistory(selected, 30)
      .then(hist => {
        const pts = (hist || []).map(h => [h.latitude, h.longitude]);
        setTrails(t => ({ ...t, [selected]: pts }));
      })
      .catch(() => {});
  }, [selected, lastTick]);

  // ── Initial load ─────────────────────────────────────────────────────────
  useEffect(() => { refresh(); }, [refresh]);

  // ── Auto-refresh ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => refresh(true), 5000);
    return () => clearInterval(id);
  }, [live, refresh]);

  // ── Simulator controls ───────────────────────────────────────────────────
  const handleStart   = async () => { await startIotSimulator(5); await refresh(); };
  const handleStop    = async () => { await stopIotSimulator();   await refresh(); };
  const handlePause   = async () => { await pauseIotSimulator();  await refresh(); };
  const handleResume  = async () => { await resumeIotSimulator(); await refresh(); };
  const handleTick    = async () => { await triggerIotTick(false); await refresh(); };
  const handleDemo    = async () => { await triggerIotTick(true);  await refresh(); };

  // ── Collect all visible points for map bounds ─────────────────────────────
  const allPoints = [
    ...iotReadings.map(r => [r.latitude, r.longitude]),
    ...rfidLocs.filter(l => l.latitude && l.longitude).map(l => [l.latitude, l.longitude]),
  ];

  const selectedReading = iotReadings.find(r => r.asset_id === selected)
                       || rfidLocs.find(r => r.asset_id === selected);

  const isRunning = simStatus?.running && !simStatus?.paused;
  const isPaused  = simStatus?.running && simStatus?.paused;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>

      {/* ── Top toolbar ───────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center',
        background: '#1e293b', borderRadius: 10, padding: '10px 16px',
      }}>
        <span style={{ color: '#94a3b8', fontSize: 13, flex: 1 }}>
          🛰️ <strong style={{ color: '#e2e8f0' }}>IoT Asset Map</strong>
          &nbsp;·&nbsp;
          {simStatus
            ? <>{simStatus.asset_count} virtual assets · cycle #{simStatus.cycle_count}</>
            : 'Connecting to backend…'}
          &nbsp;·&nbsp;
          {lastTick && <span style={{ color: '#64748b' }}>Updated {fmt(lastTick)}</span>}
        </span>

        {/* Live toggle */}
        <button
          onClick={() => setLive(v => !v)}
          style={{
            background: live ? '#16a34a' : '#475569',
            color: '#fff', border: 'none', borderRadius: 6,
            padding: '5px 14px', cursor: 'pointer', fontSize: 13,
          }}
        >
          {live ? '🟢 LIVE' : '⏸ PAUSED'}
        </button>

        {/* Simulator controls */}
        {!simStatus?.running && (
          <button onClick={handleStart} style={btnStyle('#2563eb')}>▶ Start Simulator</button>
        )}
        {isRunning && (
          <button onClick={handlePause} style={btnStyle('#d97706')}>⏸ Pause</button>
        )}
        {isPaused && (
          <button onClick={handleResume} style={btnStyle('#16a34a')}>▶ Resume</button>
        )}
        {simStatus?.running && (
          <button onClick={handleStop} style={btnStyle('#dc2626')}>■ Stop</button>
        )}
        <button onClick={handleTick} style={btnStyle('#7c3aed')}>⚡ Tick</button>
        <button onClick={handleDemo} style={btnStyle('#be185d')}>🚨 Demo Alert</button>
        <button onClick={() => refresh()} style={btnStyle('#475569')}>🔄 Refresh</button>
      </div>

      {/* ── Error banner ──────────────────────────────────────────────── */}
      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fca5a5',
          borderRadius: 8, padding: '8px 14px', color: '#dc2626', fontSize: 13,
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Main layout: map left, panel right ───────────────────────── */}
      <div style={{ display: 'flex', gap: 12, flex: 1, minHeight: 500 }}>

        {/* MAP */}
        <div style={{ flex: 2, borderRadius: 10, overflow: 'hidden', border: '1px solid #334155' }}>
          <MapContainer
            center={[28.627, 77.209]}
            zoom={13}
            style={{ width: '100%', height: '100%', minHeight: 480 }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://osm.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {allPoints.length > 0 && <FitBounds points={allPoints} />}

            {/* IoT asset markers */}
            {iotReadings.map(r => (
              <Marker
                key={r.asset_id}
                position={[r.latitude, r.longitude]}
                icon={iconFor(r)}
                eventHandlers={{ click: () => setSelected(r.asset_id) }}
              >
                <Popup>
                  <strong>{r.asset_id}</strong> — {r.asset_type}<br />
                  Zone: {r.zone}<br />
                  {statusBadge(r.status)}<br />
                  🌡 {r.temperature_c}°C &nbsp; 🔋 {r.battery_pct}% &nbsp; ⚡ {r.speed_kmh} km/h<br />
                  <small>{fmt(r.timestamp)}</small>
                </Popup>
              </Marker>
            ))}

            {/* RFID static markers */}
            {rfidLocs
              .filter(l => l.latitude && l.longitude)
              .filter(l => !iotReadings.find(r => r.asset_id === l.asset_id))
              .map(l => (
                <Marker
                  key={l.asset_id}
                  position={[l.latitude, l.longitude]}
                  icon={ICONS.rfid}
                  eventHandlers={{ click: () => setSelected(l.asset_id) }}
                >
                  <Popup>
                    <strong>{l.asset_id}</strong> — {l.asset_name}<br />
                    Zone: {l.expected_zone}<br />
                    <small>RFID tracked · {fmt(l.recorded_at)}</small>
                  </Popup>
                </Marker>
              ))}

            {/* Trail lines */}
            {Object.entries(trails).map(([id, pts]) =>
              pts.length > 1 ? (
                <Polyline
                  key={id}
                  positions={pts}
                  color={selected === id ? '#f59e0b' : '#64748b'}
                  weight={selected === id ? 3 : 1.5}
                  opacity={0.75}
                />
              ) : null
            )}
          </MapContainer>
        </div>

        {/* SIDE PANEL */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Asset list */}
          <div style={{
            background: '#0f172a', borderRadius: 10, padding: 12,
            border: '1px solid #1e293b', overflowY: 'auto', maxHeight: 320,
          }}>
            <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 8 }}>
              SELECT ASSET — {iotReadings.length} IoT · {rfidLocs.length} RFID
            </div>
            {iotReadings.map(r => (
              <div
                key={r.asset_id}
                onClick={() => setSelected(r.asset_id)}
                style={{
                  padding: '6px 10px', borderRadius: 6, marginBottom: 4,
                  cursor: 'pointer', fontSize: 13,
                  background: selected === r.asset_id ? '#1e3a5f' : '#1e293b',
                  border: `1px solid ${r.status === 'ALERT' ? '#dc2626' : selected === r.asset_id ? '#3b82f6' : '#334155'}`,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
              >
                <span style={{ color: '#e2e8f0' }}>{r.asset_id}</span>
                <span style={{ color: '#94a3b8', fontSize: 11 }}>{r.asset_type}</span>
                {statusBadge(r.status)}
              </div>
            ))}
          </div>

          {/* Selected asset telemetry card */}
          {selectedReading ? (
            <div style={{
              background: '#0f172a', borderRadius: 10, padding: 14,
              border: '1px solid #1e293b', flex: 1,
            }}>
              <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 6 }}>SELECTED ASSET</div>
              <div style={{ color: '#f1f5f9', fontSize: 16, fontWeight: 700 }}>
                {selectedReading.asset_id}
              </div>
              <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 10 }}>
                {selectedReading.asset_type || selectedReading.asset_name}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <TelemetryCard label="Status"      value={statusBadge(selectedReading.status)} />
                <TelemetryCard label="Zone"        value={selectedReading.zone || selectedReading.expected_zone || '—'} />
                <TelemetryCard label="Temperature" value={selectedReading.temperature_c != null ? `${selectedReading.temperature_c} °C` : '—'} alert={selectedReading.temperature_c > 45} />
                <TelemetryCard label="Battery"     value={selectedReading.battery_pct != null ? `${selectedReading.battery_pct} %` : '—'}    alert={selectedReading.battery_pct < 15} />
                <TelemetryCard label="Speed"       value={selectedReading.speed_kmh   != null ? `${selectedReading.speed_kmh} km/h` : '—'}   alert={selectedReading.speed_kmh > 80} />
                <TelemetryCard label="Coordinates" value={
                  selectedReading.latitude
                    ? `${Number(selectedReading.latitude).toFixed(4)}, ${Number(selectedReading.longitude).toFixed(4)}`
                    : '—'
                } />
              </div>

              {/* Anomaly events */}
              {selectedReading.anomaly_events?.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ color: '#f87171', fontSize: 12, fontWeight: 700, marginBottom: 4 }}>
                    🚨 ACTIVE ANOMALIES
                  </div>
                  {selectedReading.anomaly_events.map((ev, i) => (
                    <div key={i} style={{
                      background: '#3b0d0d', borderRadius: 6, padding: '6px 10px',
                      fontSize: 12, color: '#fca5a5', marginBottom: 4,
                    }}>
                      <strong>{ev.metric}</strong>: {ev.observed_value} (threshold {ev.threshold}) — {ev.message}
                    </div>
                  ))}
                </div>
              )}

              <div style={{ color: '#475569', fontSize: 11, marginTop: 10 }}>
                Last updated: {fmt(selectedReading.timestamp || selectedReading.recorded_at)}
              </div>
            </div>
          ) : (
            <div style={{
              background: '#0f172a', borderRadius: 10, padding: 20,
              border: '1px solid #1e293b', color: '#475569', fontSize: 13,
              textAlign: 'center', flex: 1,
            }}>
              Click a marker or select an asset above to see telemetry details.
            </div>
          )}

          {/* Simulator thresholds */}
          <div style={{
            background: '#0f172a', borderRadius: 10, padding: 12,
            border: '1px solid #1e293b', fontSize: 12, color: '#64748b',
          }}>
            <div style={{ color: '#94a3b8', fontWeight: 700, marginBottom: 6 }}>ALERT THRESHOLDS</div>
            <div>🌡 Temp &gt; 45°C or &lt; -5°C → HIGH</div>
            <div>🔋 Battery &lt; 15% → MEDIUM</div>
            <div>⚡ Speed &gt; 80 km/h → HIGH</div>
            <div style={{ marginTop: 6, color: '#475569' }}>
              🗺 Simulated routes — not real GPS.
            </div>
          </div>
        </div>
      </div>

      {/* ── Legend ───────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#64748b', paddingLeft: 4 }}>
        <span>🟢 Normal IoT</span>
        <span>🔴 Anomaly alert</span>
        <span>🔵 RFID tracked</span>
        <span>⬛ Trail line</span>
        <span>🟡 Selected trail</span>
      </div>
    </div>
  );
}

// ── Small helpers ─────────────────────────────────────────────────────────────
function btnStyle(bg) {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 6,
    padding: '5px 12px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
  };
}

function TelemetryCard({ label, value, alert = false }) {
  return (
    <div style={{
      background: alert ? '#3b0d0d' : '#1e293b',
      borderRadius: 8, padding: '8px 10px',
      border: `1px solid ${alert ? '#dc2626' : '#334155'}`,
    }}>
      <div style={{ color: '#64748b', fontSize: 10, marginBottom: 2 }}>{label}</div>
      <div style={{ color: alert ? '#f87171' : '#e2e8f0', fontSize: 13, fontWeight: 600 }}>
        {value}
      </div>
    </div>
  );
}
