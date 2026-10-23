// ==========================================
// EVENT SIMULATOR COMPONENT
// IoT-Based Smart Asset Tracking System
// ==========================================

import React, { useState, useEffect, useRef } from 'react';
import {
  AlertCircle,
  Play,
  StopCircle,
  Activity,
  CheckCircle2,
  Loader2,
  Send,
  Zap,
  ShieldCheck,
  ShieldAlert,
  MapPinOff,
  HelpCircle,
  Clock,
} from 'lucide-react';
import { getStatusMeta, formatTimestamp } from '../utils/formatters';

// 5 Core Preset Test Scenarios matching Capstone / M.Tech evaluation criteria
const PRESET_SCENARIOS = [
  {
    id: 'scenario-normal',
    asset_id: 'A001',
    location: 'SHELF_01',
    zone: 'SHELF_01',
    event_type: 'INTERNAL_SCAN',
    label: 'Normal Location',
    description: 'A001 (Laptop) detected at its designated rack SHELF_01',
    expectedStatus: 'NORMAL',
  },
  {
    id: 'scenario-misplaced',
    asset_id: 'A002',
    location: 'SHELF_03',
    zone: 'SHELF_03',
    event_type: 'INTERNAL_SCAN',
    label: 'Misplaced Asset',
    description: 'A002 (Monitor) detected at SHELF_03 instead of SHELF_01',
    expectedStatus: 'MISPLACED',
  },
  {
    id: 'scenario-auth-gate',
    asset_id: 'A004',
    location: 'MAIN_GATE',
    zone: 'MAIN_GATE',
    event_type: 'GATE_SCAN',
    label: 'Authorized Gate Exit',
    description: 'A004 (Projector) scanned at MAIN_GATE with valid permit',
    expectedStatus: 'AUTHORIZED_EXIT',
  },
  {
    id: 'scenario-unauth-gate',
    asset_id: 'A005',
    location: 'MAIN_GATE',
    zone: 'MAIN_GATE',
    event_type: 'GATE_SCAN',
    label: 'Unauthorized Gate Exit',
    description: 'A005 (Scanner) scanned at MAIN_GATE without exit permit',
    expectedStatus: 'UNAUTHORIZED_EXIT',
  },
  {
    id: 'scenario-unknown',
    asset_id: 'UNKNOWN_TAG_999',
    location: 'SHELF_01',
    zone: 'SHELF_01',
    event_type: 'INTERNAL_SCAN',
    label: 'Unknown / Unregistered Tag',
    description: 'Uncataloged RFID/Tag scanned inside the warehouse',
    expectedStatus: 'UNKNOWN_ASSET',
  },
];

export default function Simulator({ assets, fetchZones, postTrackingEvent, refreshDashboard }) {
  // Form & Zone State
  const [zonesList, setZonesList] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState('');
  const [selectedZone, setSelectedZone] = useState('');
  const [selectedSource, setSelectedSource] = useState('INTERNAL_SCAN');

  // Async Execution State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Automated Demo Loop State
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoIntervalMs, setDemoIntervalMs] = useState(1200);
  const [activeScenarioIdx, setActiveScenarioIdx] = useState(null);
  const demoTimerRef = useRef(null);

  // Load facility zones from backend API on mount
  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const data = await fetchZones();
        if (isMounted && Array.isArray(data)) {
          setZonesList(data);
        }
      } catch (err) {
        // Fallback default zones if network call fails
        if (isMounted) {
          setZonesList([
            { zone_id: 'SHELF_01', zone_name: 'Storage Shelf 1 - IT Equipment' },
            { zone_id: 'SHELF_02', zone_name: 'Storage Shelf 2 - AV & Accessories' },
            { zone_id: 'SHELF_03', zone_name: 'Storage Shelf 3 - Warehouse Scanners' },
            { zone_id: 'MAIN_GATE', zone_name: 'Main Perimeter Gate' },
          ]);
        }
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [fetchZones]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (demoTimerRef.current) {
        clearTimeout(demoTimerRef.current);
      }
    };
  }, []);

  // Event submission handler
  const executeEventSubmission = async (eventPayload) => {
    if (isSubmitting) return; // Prevent concurrent submissions
    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const resp = await postTrackingEvent(eventPayload);
      // The backend returns { success, message, duplicate, data: { status, message, ... } }
      const evaluation = resp?.data || resp;
      setResult(evaluation);

      // Refresh dashboard metrics and recent events
      if (typeof refreshDashboard === 'function') {
        await refreshDashboard();
      }
    } catch (err) {
      console.error('Simulator event submission error:', err);
      const serverErrMsg =
        err?.response?.data?.error ||
        err?.response?.data?.message ||
        err?.message ||
        'Failed to submit tracking event to backend';
      setError(serverErrMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Manual Form Submission
  const handleManualSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAsset || !selectedZone) {
      setError('Please select both an asset and a target zone.');
      return;
    }

    const payload = {
      asset_id: selectedAsset.trim(),
      location: selectedZone.trim(), // Canonical field required by anomaly_engine
      detected_zone: selectedZone.trim(), // Alias for compatibility
      event_type: selectedSource,
      timestamp: new Date().toISOString(),
    };

    await executeEventSubmission(payload);
  };

  // Quick Preset Button Click
  const handlePresetClick = async (scenario) => {
    if (isSubmitting || demoRunning) return;
    setSelectedAsset(scenario.asset_id);
    setSelectedZone(scenario.location);
    setSelectedSource(scenario.event_type);

    const payload = {
      asset_id: scenario.asset_id,
      location: scenario.location,
      detected_zone: scenario.location,
      event_type: scenario.event_type,
      timestamp: new Date().toISOString(),
    };

    await executeEventSubmission(payload);
  };

  // Automated Sequential Demo
  const startDemo = () => {
    if (demoRunning) return;
    setDemoRunning(true);
    setError(null);

    let idx = 0;
    const runNext = async () => {
      setActiveScenarioIdx(idx);
      const scenario = PRESET_SCENARIOS[idx];

      const payload = {
        asset_id: scenario.asset_id,
        location: scenario.location,
        detected_zone: scenario.location,
        event_type: scenario.event_type,
        timestamp: new Date().toISOString(),
      };

      try {
        const resp = await postTrackingEvent(payload);
        setResult(resp?.data || resp);
        if (typeof refreshDashboard === 'function') {
          await refreshDashboard();
        }
      } catch (err) {
        console.error('Demo cycle submission failed:', err);
      }

      idx = (idx + 1) % PRESET_SCENARIOS.length;
      demoTimerRef.current = setTimeout(runNext, Math.max(400, demoIntervalMs));
    };

    runNext();
  };

  const stopDemo = () => {
    setDemoRunning(false);
    setActiveScenarioIdx(null);
    if (demoTimerRef.current) {
      clearTimeout(demoTimerRef.current);
      demoTimerRef.current = null;
    }
  };

  // Status metadata for result rendering
  const resultMeta = result ? getStatusMeta(result.status) : null;
  const eventId = result?.persistence?.event_id;
  const isDuplicate = Boolean(result?.persistence?.duplicate);

  return (
    <div className="simulator-container" aria-label="Local Asset Event Simulator">
      {/* 1. Header Card */}
      <section className="table-card" style={{ marginBottom: '1.25rem' }}>
        <div className="table-header-row">
          <div>
            <h2 className="table-title inline-flex-center">
              <Activity className="icon-sm mr-2" style={{ color: '#38bdf8' }} aria-hidden="true" />
              Local Edge Event Simulator
            </h2>
            <p className="table-subtitle">
              Simulate RFID portal & warehouse antenna scans. Events flow directly into the anomaly engine and SQLite audit trail.
            </p>
          </div>

          <div className="inline-flex-center">
            {demoRunning ? (
              <span className="badge badge-warning inline-flex-center">
                <span className="pulsing-dot" style={{ marginRight: '6px' }}></span>
                Demo Running ({PRESET_SCENARIOS[activeScenarioIdx]?.label || 'Active'})
              </span>
            ) : (
              <span className="badge badge-info">Interactive Mode</span>
            )}
          </div>
        </div>

        {/* 2. Quick Scenario Presets */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', fontWeight: 500 }}>
            Quick Scenario Presets (Click to Trigger):
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {PRESET_SCENARIOS.map((sc) => {
              const meta = getStatusMeta(sc.expectedStatus);
              const isActive = demoRunning && PRESET_SCENARIOS[activeScenarioIdx]?.id === sc.id;
              return (
                <button
                  key={sc.id}
                  type="button"
                  onClick={() => handlePresetClick(sc)}
                  disabled={isSubmitting || demoRunning}
                  className={`btn btn-sm ${isActive ? 'btn-primary' : 'btn-outline-secondary'}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    borderColor: isActive ? 'var(--primary)' : undefined,
                  }}
                  title={sc.description}
                >
                  <span className={`badge ${meta.badgeClass}`} style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>
                    {sc.expectedStatus}
                  </span>
                  <span>{sc.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Manual Event Form */}
        <form onSubmit={handleManualSubmit} style={{ borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem', fontWeight: 500 }}>
            Custom Scan Event Generator:
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1rem',
              alignItems: 'end',
              marginBottom: '1rem',
            }}
          >
            {/* Asset Selector */}
            <div>
              <label htmlFor="sim-asset-select" style={{ display: 'block', fontSize: '0.775rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Monitored Asset <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <select
                id="sim-asset-select"
                value={selectedAsset}
                onChange={(e) => setSelectedAsset(e.target.value)}
                disabled={isSubmitting || demoRunning}
                className="select-input"
                style={{ width: '100%' }}
                required
              >
                <option value="">— Select Cataloged Asset —</option>
                {(assets || []).map((a) => (
                  <option key={a.asset_id} value={a.asset_id}>
                    {a.asset_id} – {a.asset_name} (Expected: {a.expected_zone})
                  </option>
                ))}
                <option value="UNKNOWN_TAG_999">UNKNOWN_TAG_999 (Unregistered External Tag)</option>
              </select>
            </div>

            {/* Target Zone Selector */}
            <div>
              <label htmlFor="sim-zone-select" style={{ display: 'block', fontSize: '0.775rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Detected Facility Zone <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <select
                id="sim-zone-select"
                value={selectedZone}
                onChange={(e) => setSelectedZone(e.target.value)}
                disabled={isSubmitting || demoRunning}
                className="select-input"
                style={{ width: '100%' }}
                required
              >
                <option value="">— Select Target Zone —</option>
                {zonesList.map((z) => {
                  const zoneId = typeof z === 'object' && z !== null ? z.zone_id : z;
                  const zoneName =
                    typeof z === 'object' && z !== null && z.zone_name
                      ? `${z.zone_id} — ${z.zone_name}`
                      : zoneId;
                  return (
                    <option key={zoneId} value={zoneId}>
                      {zoneName}
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Event Scan Source */}
            <div>
              <label htmlFor="sim-source-select" style={{ display: 'block', fontSize: '0.775rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                Event / Scan Type
              </label>
              <select
                id="sim-source-select"
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
                disabled={isSubmitting || demoRunning}
                className="select-input"
                style={{ width: '100%' }}
              >
                <option value="INTERNAL_SCAN">INTERNAL_SCAN (Storage Shelf Reader)</option>
                <option value="GATE_SCAN">GATE_SCAN (Perimeter Exit Portal)</option>
                <option value="MANUAL_SIMULATION">MANUAL_SIMULATION (Audit Tool)</option>
              </select>
            </div>

            {/* Submit Button */}
            <div>
              <button
                type="submit"
                disabled={isSubmitting || demoRunning}
                className="btn btn-primary"
                style={{ width: '100%', minHeight: '38px', gap: '0.5rem' }}
                aria-label="Submit Scan Event"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="icon-sm spin" aria-hidden="true" />
                    <span>Evaluating...</span>
                  </>
                ) : (
                  <>
                    <Send className="icon-xs" aria-hidden="true" />
                    <span>Send Scan Event</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {/* 4. Automated Demo Sequencer Controls */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            borderTop: '1px solid var(--border-color)',
            paddingTop: '0.85rem',
            marginTop: '0.5rem',
          }}
        >
          <div className="inline-flex-center" style={{ gap: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Automated Scenario Loop:
            </span>
            <label className="inline-flex-center" style={{ fontSize: '0.775rem', color: 'var(--text-muted)', gap: '0.35rem' }}>
              Cycle Interval:
              <input
                type="number"
                min={400}
                max={5000}
                step={200}
                value={demoIntervalMs}
                onChange={(e) => setDemoIntervalMs(Number(e.target.value))}
                disabled={demoRunning}
                className="select-input"
                style={{ width: '85px', padding: '0.2rem 0.4rem', textAlign: 'center' }}
              />
              <span>ms</span>
            </label>
          </div>

          <div>
            {demoRunning ? (
              <button
                type="button"
                className="btn btn-sm btn-outline-danger inline-flex-center"
                onClick={stopDemo}
                style={{ gap: '0.35rem' }}
              >
                <StopCircle className="icon-xs" aria-hidden="true" />
                <span>Stop Demo Loop</span>
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-sm btn-outline-success inline-flex-center"
                onClick={startDemo}
                disabled={isSubmitting}
                style={{ gap: '0.35rem' }}
              >
                <Play className="icon-xs" aria-hidden="true" />
                <span>Run Automated Demo</span>
              </button>
            )}
          </div>
        </div>
      </section>

      {/* 5. Error Banner */}
      {error && (
        <div
          className="alert-card alert-critical"
          role="alert"
          style={{ marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}
        >
          <AlertCircle className="icon-md" style={{ color: 'var(--danger)', flexShrink: 0 }} aria-hidden="true" />
          <div style={{ flex: 1 }}>
            <strong style={{ color: '#ffffff' }}>Simulation Error:</strong>{' '}
            <span style={{ color: '#f87171' }}>{error}</span>
          </div>
        </div>
      )}

      {/* 6. Live Result Evaluation Card */}
      {result && resultMeta && (
        <section
          className={`table-card alert-card ${
            resultMeta.severity === 'critical'
              ? 'alert-critical'
              : resultMeta.severity === 'high'
              ? 'alert-high'
              : resultMeta.severity === 'warning'
              ? 'alert-warning'
              : ''
          }`}
          style={{
            borderLeft: `4px solid ${
              resultMeta.severity === 'critical'
                ? 'var(--danger)'
                : resultMeta.severity === 'high'
                ? 'var(--orange)'
                : resultMeta.severity === 'warning'
                ? 'var(--warning)'
                : 'var(--success)'
            }`,
            backgroundColor: '#162032',
          }}
          role="status"
          aria-label="Event Evaluation Result"
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div className="inline-flex-center" style={{ gap: '0.5rem' }}>
              {result.status === 'NORMAL' && <CheckCircle2 className="icon-md text-success" aria-hidden="true" />}
              {result.status === 'MISPLACED' && <MapPinOff className="icon-md" style={{ color: '#fbbf24' }} aria-hidden="true" />}
              {result.status === 'AUTHORIZED_EXIT' && <ShieldCheck className="icon-md" style={{ color: '#38bdf8' }} aria-hidden="true" />}
              {result.status === 'UNAUTHORIZED_EXIT' && <ShieldAlert className="icon-md" style={{ color: '#f87171' }} aria-hidden="true" />}
              {result.status === 'UNKNOWN_ASSET' && <HelpCircle className="icon-md" style={{ color: '#c084fc' }} aria-hidden="true" />}
              
              <span className={`badge ${resultMeta.badgeClass}`} style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem' }}>
                {result.status}
              </span>

              {isDuplicate && (
                <span className="badge badge-secondary" title="Deduplicated by event_id / message_id">
                  Deduplicated
                </span>
              )}
            </div>

            <div className="inline-flex-center" style={{ fontSize: '0.775rem', color: 'var(--text-muted)', gap: '0.5rem' }}>
              {eventId && (
                <span className="mono-badge">
                  Event ID: #{eventId}
                </span>
              )}
              <span className="inline-flex-center">
                <Clock className="icon-xs mr-1 text-muted" aria-hidden="true" />
                {formatTimestamp(result.event_metadata?.timestamp || new Date().toISOString())}
              </span>
            </div>
          </div>

          {/* Details Row */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.75rem',
              background: '#0f172a',
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              marginBottom: '0.75rem',
              fontSize: '0.825rem',
            }}
          >
            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>ASSET ID</span>
              <strong className="mono-badge" style={{ marginTop: '2px', display: 'inline-block' }}>
                {result.asset_id || 'UNKNOWN'}
              </strong>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>DETECTED IN</span>
              <span className="zone-pill" style={{ marginTop: '2px', display: 'inline-block' }}>
                {result.detected_zone || 'N/A'}
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>EXPECTED ZONE</span>
              <span style={{ color: result.expected_zone ? '#ffffff' : 'var(--text-muted)', marginTop: '2px', display: 'inline-block' }}>
                {result.expected_zone || 'None (Unregistered)'}
              </span>
            </div>

            <div>
              <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>CLASSIFICATION</span>
              <span style={{ color: resultMeta.isAnomaly ? '#fbbf24' : '#34d399', fontWeight: 600 }}>
                {resultMeta.isAnomaly ? 'Anomaly Flagged' : 'Verified Valid'}
              </span>
            </div>
          </div>

          {/* Explanation Text */}
          <p style={{ fontSize: '0.875rem', color: '#f8fafc', lineHeight: 1.5, margin: 0 }}>
            {result.message}
          </p>
        </section>
      )}
    </div>
  );
}
