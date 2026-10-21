// ==========================================
// INVENTORY AUDIT HISTORY COMPONENT
// ==========================================

import React from 'react';
import { ClipboardList, CheckCircle2, AlertCircle, Clock } from 'lucide-react';
import { formatTimestamp } from '../utils/formatters';

export default function AuditHistorySection({ auditsData, isLoading }) {
  const audits = auditsData?.items || [];

  return (
    <section className="table-card" aria-label="Inventory Audit History">
      <div className="table-header-row">
        <div>
          <h2 className="table-title">Inventory Audit Logs</h2>
          <p className="table-subtitle">
            Formal inventory audits comparing registered assets against scanned tag batches
          </p>
        </div>
      </div>

      {isLoading && audits.length === 0 ? (
        <div className="table-loading">
          <span>Loading audit history...</span>
        </div>
      ) : audits.length === 0 ? (
        <div className="table-empty">
          <ClipboardList className="empty-icon text-muted" aria-hidden="true" />
          <p className="empty-text">No formal inventory audits recorded yet.</p>
          <span className="empty-subtext">
            Audit executions will appear here, identifying assets flagged for missing investigation.
          </span>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Audit ID</th>
                <th scope="col">Execution Time</th>
                <th scope="col">Total Expected</th>
                <th scope="col">Detected</th>
                <th scope="col">Missing Count</th>
                <th scope="col">Missing Asset IDs</th>
                <th scope="col">Notes</th>
              </tr>
            </thead>
            <tbody>
              {audits.map((a) => {
                const missingList = Array.isArray(a.missing_asset_ids)
                  ? a.missing_asset_ids
                  : [];
                const hasMissing = a.missing_count > 0;

                return (
                  <tr key={a.audit_id} className={hasMissing ? 'row-warning' : ''}>
                    <td>
                      <span className="mono-badge">AUDIT-#{a.audit_id}</span>
                    </td>
                    <td>
                      <span className="inline-flex-center text-secondary">
                        <Clock className="icon-xs mr-1 text-muted" aria-hidden="true" />
                        {formatTimestamp(a.audit_timestamp)}
                      </span>
                    </td>
                    <td>{a.total_expected}</td>
                    <td>
                      <span className="inline-flex-center text-success font-medium">
                        <CheckCircle2 className="icon-xs mr-1" aria-hidden="true" />
                        {a.detected_count}
                      </span>
                    </td>
                    <td>
                      {hasMissing ? (
                        <span className="badge badge-orange inline-flex-center">
                          <AlertCircle className="icon-xs mr-1" aria-hidden="true" />
                          {a.missing_count} Missing
                        </span>
                      ) : (
                        <span className="badge badge-success">0 (Complete)</span>
                      )}
                    </td>
                    <td>
                      {missingList.length === 0 ? (
                        <span className="text-muted">None</span>
                      ) : (
                        <div className="tag-group">
                          {missingList.map((mid) => (
                            <span key={mid} className="tag-pill tag-missing">
                              {mid}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="text-secondary">{a.notes || '—'}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
