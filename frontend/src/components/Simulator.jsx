// ==========================================
// EVENT SIMULATOR COMPONENT
// ==========================================
import React, { useState, useEffect, useRef } from 'react';
import { fetchZones, postTrackingEvent } from '../api';
import { AlertCircle, Play, StopCircle, Activity } from 'lucide-react';

const PRESET_SCENARIOS = [
  // 1️⃣ Normal
  {
    asset_id: 'A001',
    zone: 'SHELF_01',
    event_type: 'INTERNAL_SCAN',
    description: 'Normal (expected zone)',
  },
  // 2️⃣ Misplaced
  {
    asset_id: 'A002',
    zone: 'SHELF_03',
    event_type: 'INTERNAL_SCAN',
    description: 'Misplaced (different zone)',
  },
  // 3️⃣ Authorized Exit
  {
    asset_id: 'A004',
    zone: 'MAIN_GATE',
    event_type: 'GATE_SCAN',
    description: 'Authorized exit (has exit auth)',
  },
  // 4️⃣ Unauthorized Exit
  {
    asset_id: 'A005',
    zone: 'MAIN_GATE',
    event_type: 'GATE_SCAN',
    description: 'Unauthorized exit (no exit auth)',
  },
  // 5️⃣ Unknown Asset
  {
    asset_id: 'UNKNOWN_999',
    zone: 'SHELF_01',
    event_type: 'INTERNAL_SCAN',
    description: 'Unknown asset',
  },
];

export default function Simulator({ assets, fetchZones, postTrackingEvent, refreshDashboard }) {
  // UI state
  const [zones, setZones] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState('');
  const [selectedZone, setSelectedZone] = useState('');
  const [selectedSource, setSelectedSource] = useState('INTERNAL_SCAN');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoIntervalMs, setDemoIntervalMs] = useState(800);
  const demoTimerRef = useRef(null);

  // Load zones once on mount
  useEffect(() => {
    (async () => {
      try {
        const data = await fetchZones();
        setZones(data);
      } catch (_) {
        setZones(['SHELF_01', 'SHELF_02', 'SHELF_03', 'MAIN_GATE']);
      }
    })();
  }, []);

  const submitEvent = async (payload) => {
    setIsSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const resp = await postTrackingEvent(payload);
      setResult(resp.data);
      await refreshDashboard();
    } catch (e) {
      setError(e.message || 'Failed to submit event');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAsset || !selectedZone) {
      setError('Select both asset and zone');
      return;
    }
    const payload = {
      asset_id: selectedAsset,
      zone: selectedZone,
      event_type: selectedSource,
      timestamp: new Date().toISOString(),
    };
    await submitEvent(payload);
  };

  const startDemo = () => {
    if (demoRunning) return;
    setDemoRunning(true);
    let idx = 0;
    const runNext = async () => {
      if (!demoRunning) return;
      const scenario = PRESET_SCENARIOS[idx];
      const payload = {
        asset_id: scenario.asset_id,
        zone: scenario.zone,
        event_type: scenario.event_type,
        timestamp: new Date().toISOString(),
      };
      await submitEvent(payload);
      idx = (idx + 1) % PRESET_SCENARIOS.length;
      demoTimerRef.current = setTimeout(runNext, demoIntervalMs);
    };
    runNext();
  };

  const stopDemo = () => {
    setDemoRunning(false);
    clearTimeout(demoTimerRef.current);
  };

  useEffect(() => () => clearTimeout(demoTimerRef.current), []);

  return (
    <section className="simulator" aria-label="Local Event Simulator">
      <h2 className="section-title">Local Asset Event Simulator</h2>

      {/* Manual event form */}
      <form className="sim-form" onSubmit={handleManualSubmit}>
        <div className="form-row">
          <label>
            Asset
            <select
              value={selectedAsset}
              onChange={(e) => setSelectedAsset(e.target.value)}
              required
            >
              <option value="">— select —</option>
              {assets.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.asset_id} – {a.asset_name}
                </option>
              ))}
            </select>
          </label>

          <label>
            Zone
            <select
              value={selectedZone}
              onChange={(e) => setSelectedZone(e.target.value)}
              required
            >
              <option value="">— select —</option>
              {zones.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          </label>

          <label>
            Source
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
            >
              <option value="INTERNAL_SCAN">Internal Scan</option>
              <option value="GATE_SCAN">Gate Scan</option>
              <option value="MANUAL_SIMULATION">Manual Simulation</option>
            </select>
          </label>
        </div>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting ? 'Submitting…' : 'Submit Event'}
        </button>
      </form>

      {/* Demo controls */}
      <div className="demo-controls">
        <h3>Demo Sequence</h3>
        <label>
          Interval (ms):
          <input
            type="number"
            min={200}
            step={100}
            value={demoIntervalMs}
            onChange={(e) => setDemoIntervalMs(Number(e.target.value))}
            disabled={demoRunning}
          />
        </label>
        {demoRunning ? (
          <button className="btn btn-danger" onClick={stopDemo}>
            <StopCircle className="icon-sm mr-1" /> Stop Demo
          </button>
        ) : (
          <button className="btn btn-success" onClick={startDemo}>
            <Play className="icon-sm mr-1" /> Run Demo
          </button>
        )}
      </div>

      {/* Result / error display */}
      {error && (
        <div className="alert alert-error" role="alert">
          <AlertCircle className="icon-sm mr-1" aria-hidden="true" /> {error}
        </div>
      )}

      {result && (
        <div className="alert alert-success" role="status">
          <strong>Event Processed:</strong> ID {result.event_id || '(generated)'} – Status{' '}
          <code>{result.status}</code>
          <br />
          <em>{result.explanation}</em>
        </div>
      )}
    </section>
  );
}
