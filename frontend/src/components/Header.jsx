// ==========================================
// HEADER COMPONENT
// ==========================================

import React from 'react';
import { RefreshCw, Radio, CheckCircle2, AlertTriangle, Wifi, WifiOff } from 'lucide-react';

export default function Header({
  health,
  isRefreshing,
  onRefresh,
  autoRefreshInterval,
  setAutoRefreshInterval,
  lastUpdated,
}) {
  const isConnected = health && health.status === 'healthy';
  // MQTT status is derived from /api/health response, not inferred from API availability.
  // "connected" only when the MQTT subscriber reports an active broker connection.
  const mqttStatus = health?.mqtt_status || 'unknown';
  const mqttConnected = mqttStatus === 'connected';

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-icon-wrapper">
          <Radio className="brand-icon" aria-hidden="true" />
        </div>
        <div>
          <h1 className="header-title">
            Smart Asset Tracking & Anomaly Detection
          </h1>
          <p className="header-subtitle">
            IoT Warehouse Perimeter Security & Automated Storage Zone Verification
          </p>
        </div>
      </div>

      <div className="header-controls">
        {/* Local Simulation Mode Indicator */}
        <div
          className="mode-indicator"
          title="Running in Local Demonstration Mode with simulated IoT events"
          role="status"
        >
          <span className="pulsing-dot" aria-hidden="true"></span>
          <span className="mode-text">LOCAL DEMO (SIMULATION)</span>
        </div>

        {/* Backend Connectivity Status */}
        <div
          className={`connection-badge ${isConnected ? 'connected' : 'disconnected'}`}
          role="status"
          aria-label={isConnected ? 'Backend connected' : 'Backend offline'}
        >
          {isConnected ? (
            <>
              <CheckCircle2 className="icon-sm" aria-hidden="true" />
              <span>Backend Connected</span>
            </>
          ) : (
            <>
              <AlertTriangle className="icon-sm" aria-hidden="true" />
              <span>Backend Offline</span>
            </>
          )}
        </div>

        {/* MQTT Broker Status — sourced from /api/health, not inferred */}
        {health && (
          <div
            className={`connection-badge ${mqttConnected ? 'connected' : 'disconnected'}`}
            role="status"
            aria-label={`MQTT broker: ${mqttStatus}`}
            title={`MQTT subscriber reports broker as: ${mqttStatus}`}
          >
            {mqttConnected ? (
              <>
                <Wifi className="icon-sm" aria-hidden="true" />
                <span>MQTT Live</span>
              </>
            ) : (
              <>
                <WifiOff className="icon-sm" aria-hidden="true" />
                <span>MQTT {mqttStatus === 'unknown' ? 'Unknown' : 'Offline'}</span>
              </>
            )}
          </div>
        )}

        {/* Last updated timestamp */}
        {lastUpdated && (
          <span className="last-updated-text" aria-live="polite">
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}

        {/* Auto Refresh Select */}
        <div className="auto-refresh-select">
          <label htmlFor="auto-refresh-interval" className="sr-only">
            Auto Refresh Interval
          </label>
          <select
            id="auto-refresh-interval"
            value={autoRefreshInterval}
            onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
            className="select-input"
            aria-label="Auto-refresh interval"
          >
            <option value={0}>Auto-refresh: Off</option>
            <option value={5000}>Refresh: 5s</option>
            <option value={10000}>Refresh: 10s</option>
            <option value={30000}>Refresh: 30s</option>
          </select>
        </div>

        {/* Manual Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="btn btn-primary refresh-btn"
          aria-label="Refresh dashboard data"
        >
          <RefreshCw
            className={`icon-sm ${isRefreshing ? 'spin' : ''}`}
            aria-hidden="true"
          />
          <span>Refresh</span>
        </button>
      </div>
    </header>
  );
}
