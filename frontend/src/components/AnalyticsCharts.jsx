// ==========================================
// ANALYTICS & RECHARTS COMPONENT
// ==========================================

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { BarChart3, PieChart as PieChartIcon } from 'lucide-react';

const STATUS_COLORS = {
  NORMAL: '#10b981',       // Emerald
  MISPLACED: '#f59e0b',    // Amber
  AUTHORIZED_EXIT: '#06b6d4', // Cyan
  UNAUTHORIZED_EXIT: '#ef4444', // Red
  UNKNOWN_ASSET: '#8b5cf6', // Violet
  MISSING_INVESTIGATION_REQUIRED: '#f97316', // Orange
};

const ZONE_COLORS = ['#3b82f6', '#6366f1', '#8b5cf6', '#ec4899', '#14b8a6'];

export default function AnalyticsCharts({ summary }) {
  const statusBreakdown = summary?.status_breakdown || {};
  const zoneBreakdown = summary?.zone_breakdown || {};

  // Convert status breakdown object to chart array
  const statusData = Object.entries(statusBreakdown).map(([status, count]) => ({
    name: status.replace(/_/g, ' '),
    rawStatus: status,
    count: Number(count),
  }));

  // Convert zone breakdown object to chart array
  const zoneData = Object.entries(zoneBreakdown).map(([zone, count]) => ({
    zone: zone,
    count: Number(count),
  }));

  const hasStatusData = statusData.some((d) => d.count > 0);
  const hasZoneData = zoneData.some((d) => d.count > 0);

  return (
    <section className="charts-grid" aria-label="System Analytics Visualizations">
      {/* 1. Status Breakdown Bar Chart */}
      <div className="chart-card">
        <div className="chart-header">
          <div className="chart-title-group">
            <BarChart3 className="chart-icon" aria-hidden="true" />
            <h3 className="chart-title">Tracking Events by Classified Status</h3>
          </div>
          <span className="chart-hint">Live Database Aggregation</span>
        </div>

        <div className="chart-body">
          {!hasStatusData ? (
            <div className="chart-empty">
              <p>No tracking events recorded yet.</p>
              <span>Scan events will visualize status distribution here.</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={statusData}
                margin={{ top: 10, right: 20, left: -10, bottom: 25 }}
              >
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  angle={-15}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                />
                <Tooltip
                  formatter={(value) => [value, 'Scans Recorded']}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {statusData.map((entry, index) => (
                    <Cell
                      key={`status-cell-${index}`}
                      fill={STATUS_COLORS[entry.rawStatus] || '#64748b'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 2. Zone Breakdown Chart */}
      <div className="chart-card">
        <div className="chart-header">
          <div className="chart-title-group">
            <PieChartIcon className="chart-icon" aria-hidden="true" />
            <h3 className="chart-title">Asset Allocation by Expected Zone</h3>
          </div>
          <span className="chart-hint">Registered Inventory Density</span>
        </div>

        <div className="chart-body">
          {!hasZoneData ? (
            <div className="chart-empty">
              <p>No registered assets in database.</p>
              <span>Storage density will display when assets are cataloged.</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={zoneData}
                margin={{ top: 10, right: 20, left: -10, bottom: 10 }}
              >
                <XAxis
                  dataKey="zone"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                />
                <Tooltip
                  formatter={(value) => [value, 'Assigned Assets']}
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {zoneData.map((entry, index) => (
                    <Cell
                      key={`zone-cell-${index}`}
                      fill={ZONE_COLORS[index % ZONE_COLORS.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </section>
  );
}
