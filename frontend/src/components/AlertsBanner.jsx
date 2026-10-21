// ==========================================
// ACTIVE SECURITY & ANOMALY ALERTS COMPONENT
// ==========================================

import React from 'react';
import { ShieldAlert, AlertTriangle, HelpCircle, FileSearch, CheckCircle2 } from 'lucide-react';
import { getStatusMeta, formatTimestamp } from '../utils/formatters';

export default function AlertsBanner({ events }) {
  // Filter for real anomaly statuses
  const anomalyStatuses = new Set([
    'MISPLACED',
    'UNAUTHORIZED_EXIT',
    'UNKNOWN_ASSET',
    'MISSING_INVESTIGATION_REQUIRED',
  ]);

  const recentAnomalies = (events || [])
    .filter((e) => anomalyStatuses.has(e.status))
    .slice(0, 6); // Display top 6 most recent anomalies

  const getAlertIcon = (status) => {
    switch (status) {
      case 'UNAUTHORIZED_EXIT':
        return <ShieldAlert className="icon-alert icon-red" aria-hidden="true" />;
      case 'MISPLACED':
        return <AlertTriangle className="icon-alert icon-yellow" aria-hidden="true" />;
      case 'UNKNOWN_ASSET':
        return <HelpCircle className="icon-alert icon-purple" aria-hidden="true" />;
      case 'MISSING_INVESTIGATION_REQUIRED':
        return <FileSearch className="icon-alert icon-orange" aria-hidden="true" />;
      default:
        return <AlertTriangle className="icon-alert" aria-hidden="true" />;
    }
  };

  return (
    <section className="alerts-section" aria-label="Security and Anomaly Alerts">
      <div className="section-header">
        <div className="section-title-group">
          <h2 className="section-title">Active Security & Operational Alerts</h2>
          <span className="badge badge-pill">
            {recentAnomalies.length} Critical / Anomaly Events
          </span>
        </div>
      </div>

      {recentAnomalies.length === 0 ? (
        <div className="empty-state alerts-empty">
          <CheckCircle2 className="empty-icon text-success" aria-hidden="true" />
          <p className="empty-text">No active security alerts or misplaced items.</p>
          <span className="empty-subtext">All verified assets remain in expected zones.</span>
        </div>
      ) : (
        <div className="alerts-grid">
          {recentAnomalies.map((item) => {
            const meta = getStatusMeta(item.status);
            return (
              <div key={item.event_id} className={`alert-card alert-${meta.severity}`}>
                <div className="alert-icon-container">{getAlertIcon(item.status)}</div>
                <div className="alert-content">
                  <div className="alert-meta-row">
                    <span className={`badge ${meta.badgeClass}`}>{meta.label}</span>
                    <span className="alert-time">{formatTimestamp(item.timestamp)}</span>
                  </div>
                  <div className="alert-details">
                    <strong className="alert-asset">Asset: {item.asset_id || 'Unknown'}</strong>
                    <span className="alert-zone">Location: {item.location}</span>
                  </div>
                  <p className="alert-message">{item.message}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
