// ==========================================
// RECENT TRACKING EVENTS TABLE COMPONENT
// ==========================================

import React from 'react';
import {
  Filter,
  ChevronLeft,
  ChevronRight,
  History,
  Clock,
  Loader2,
  X,
} from 'lucide-react';
import { formatTimestamp, getStatusMeta } from '../utils/formatters';

export default function RecentEventsTable({
  eventsData,
  isLoading,
  filters,
  setFilters,
  onApplyFilters,
}) {
  const items = eventsData?.items || [];
  const totalCount = eventsData?.total_count || 0;
  const limit = eventsData?.limit || 20;
  const offset = eventsData?.offset || 0;
  const hasMore = eventsData?.has_more || false;

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(totalCount / limit));

  const handleStatusChange = (e) => {
    setFilters((prev) => ({ ...prev, status: e.target.value, offset: 0 }));
  };

  const handleZoneChange = (e) => {
    setFilters((prev) => ({ ...prev, zone: e.target.value, offset: 0 }));
  };

  const handleAssetSearch = (e) => {
    setFilters((prev) => ({ ...prev, asset_id: e.target.value, offset: 0 }));
  };

  const clearFilters = () => {
    setFilters({ status: '', zone: '', asset_id: '', limit: 20, offset: 0 });
  };

  const hasActiveFilters = Boolean(filters.status || filters.zone || filters.asset_id);

  const handlePrevPage = () => {
    if (offset > 0) {
      setFilters((prev) => ({ ...prev, offset: Math.max(0, offset - limit) }));
    }
  };

  const handleNextPage = () => {
    if (hasMore) {
      setFilters((prev) => ({ ...prev, offset: offset + limit }));
    }
  };

  return (
    <section className="table-card" aria-label="Tracking Event History">
      <div className="table-header-row">
        <div>
          <h2 className="table-title">Recent Tracking Event History</h2>
          <p className="table-subtitle">
            Auditable log of asset scans, perimeter crossings, and anomaly evaluations
          </p>
        </div>

        {/* Filter Controls Bar */}
        <div className="filter-bar">
          <div className="filter-group">
            <Filter className="filter-icon" aria-hidden="true" />
            <span className="filter-label">Filters:</span>

            {/* Status Filter */}
            <select
              value={filters.status}
              onChange={handleStatusChange}
              className="select-input select-filter"
              aria-label="Filter events by status"
            >
              <option value="">All Statuses</option>
              <option value="NORMAL">Normal</option>
              <option value="MISPLACED">Misplaced</option>
              <option value="AUTHORIZED_EXIT">Authorized Exit</option>
              <option value="UNAUTHORIZED_EXIT">Unauthorized Exit</option>
              <option value="UNKNOWN_ASSET">Unknown Asset</option>
              <option value="MISSING_INVESTIGATION_REQUIRED">
                Audit Investigation
              </option>
            </select>

            {/* Zone Filter */}
            <select
              value={filters.zone}
              onChange={handleZoneChange}
              className="select-input select-filter"
              aria-label="Filter events by detected zone"
            >
              <option value="">All Zones</option>
              <option value="SHELF_01">SHELF_01 (IT Equipment)</option>
              <option value="SHELF_02">SHELF_02 (AV Accessories)</option>
              <option value="SHELF_03">SHELF_03 (Warehouse)</option>
              <option value="MAIN_GATE">MAIN_GATE (Perimeter)</option>
            </select>

            {/* Asset ID Input */}
            <input
              type="text"
              placeholder="Asset ID..."
              value={filters.asset_id}
              onChange={handleAssetSearch}
              className="search-input input-asset-filter"
              aria-label="Filter events by Asset ID"
            />

            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="btn btn-sm btn-outline-secondary"
                title="Reset all filters"
                aria-label="Clear active filters"
              >
                <X className="icon-xs mr-1" aria-hidden="true" />
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {isLoading && items.length === 0 ? (
        <div className="table-loading">
          <Loader2 className="spin icon-md" aria-hidden="true" />
          <span>Retrieving tracking events...</span>
        </div>
      ) : items.length === 0 ? (
        <div className="table-empty">
          <History className="empty-icon text-muted" aria-hidden="true" />
          <p className="empty-text">No tracking events found.</p>
          <span className="empty-subtext">
            {hasActiveFilters
              ? 'No events match the selected status, zone, or asset filters.'
              : 'The tracking history is empty. Events will appear here as scans arrive.'}
          </span>
        </div>
      ) : (
        <>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Time (UTC)</th>
                  <th scope="col">Asset ID</th>
                  <th scope="col">Detected Zone</th>
                  <th scope="col">Classified Status</th>
                  <th scope="col">Event Explanation & Message</th>
                </tr>
              </thead>
              <tbody>
                {items.map((event) => {
                  const meta = getStatusMeta(event.status);
                  return (
                    <tr
                      key={event.event_id}
                      className={meta.isAnomaly ? 'row-anomaly' : ''}
                    >
                      <td className="text-secondary whitespace-nowrap">
                        <span className="inline-flex-center">
                          <Clock className="icon-xs mr-1 text-muted" aria-hidden="true" />
                          {formatTimestamp(event.timestamp)}
                        </span>
                      </td>
                      <td>
                        <span className="mono-badge font-bold">
                          {event.asset_id || 'UNKNOWN'}
                        </span>
                      </td>
                      <td>
                        <span className="zone-pill">{event.location}</span>
                      </td>
                      <td>
                        <span className={`badge ${meta.badgeClass}`}>{meta.label}</span>
                      </td>
                      <td>
                        <p className="event-explanation">{event.message}</p>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="pagination-footer">
            <span className="pagination-info">
              Showing {totalCount === 0 ? 0 : offset + 1} to{' '}
              {Math.min(offset + limit, totalCount)} of {totalCount} events
            </span>

            <div className="pagination-buttons">
              <button
                onClick={handlePrevPage}
                disabled={offset === 0 || isLoading}
                className="btn btn-sm btn-outline-secondary"
                aria-label="Previous page"
              >
                <ChevronLeft className="icon-xs mr-1" aria-hidden="true" />
                Previous
              </button>

              <span className="page-counter">
                Page {currentPage} of {totalPages}
              </span>

              <button
                onClick={handleNextPage}
                disabled={!hasMore || isLoading}
                className="btn btn-sm btn-outline-secondary"
                aria-label="Next page"
              >
                Next
                <ChevronRight className="icon-xs ml-1" aria-hidden="true" />
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
