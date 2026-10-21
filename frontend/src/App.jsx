// ==========================================
// MAIN REACT APPLICATION COMPONENT
// ==========================================

import React, { useState, useEffect, useCallback } from 'react';
import Simulator from './components/Simulator';
import Header from './components/Header';
import SummaryCards from './components/SummaryCards';
import AlertsBanner from './components/AlertsBanner';
import AnalyticsCharts from './components/AnalyticsCharts';
import AssetInventoryTable from './components/AssetInventoryTable';
import RecentEventsTable from './components/RecentEventsTable';
import AuditHistorySection from './components/AuditHistorySection';

import {
  fetchHealth,
  fetchSummary,
  fetchAssets,
  fetchEvents,
  fetchAudits,
  updateAuthorization,
  postTrackingEvent,
  fetchZones,
} from './api';

import {
  AlertCircle,
  RefreshCw,
  LayoutDashboard,
  Boxes,
  History,
  ClipboardCheck,
  Activity,
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'assets' | 'events' | 'audits' | 'simulator'

  // Data States
  const [health, setHealth] = useState(null);
  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);
  const [eventsData, setEventsData] = useState({ items: [], total_count: 0 });
  const [auditsData, setAuditsData] = useState({ items: [], total_count: 0 });

  // UI & Network States
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(10000); // 10s default
  const [lastUpdated, setLastUpdated] = useState(null);

  // Events Table Filters
  const [eventFilters, setEventFilters] = useState({
    status: '',
    zone: '',
    asset_id: '',
    limit: 20,
    offset: 0,
  });

  // Master Data Fetcher
  const loadDashboardData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    setErrorMessage(null);

    try {
      const [healthRes, summaryRes, assetsRes, eventsRes, auditsRes] = await Promise.allSettled([
        fetchHealth(),
        fetchSummary(),
        fetchAssets(),
        fetchEvents(eventFilters),
        fetchAudits({ limit: 10, offset: 0 }),
      ]);

      // Health
      if (healthRes.status === 'fulfilled') {
        setHealth(healthRes.value);
      } else {
        setHealth({ status: 'unhealthy', database_status: 'disconnected' });
      }

      // Summary
      if (summaryRes.status === 'fulfilled') {
        setSummary(summaryRes.value);
      }

      // Assets
      if (assetsRes.status === 'fulfilled') {
        setAssets(assetsRes.value);
      }

      // Events
      if (eventsRes.status === 'fulfilled') {
        setEventsData(eventsRes.value);
      }

      // Audits
      if (auditsRes.status === 'fulfilled') {
        setAuditsData(auditsRes.value);
      }

      // If critical endpoints failed, notify user
      if (
        summaryRes.status === 'rejected' &&
        assetsRes.status === 'rejected' &&
        eventsRes.status === 'rejected'
      ) {
        throw new Error('Unable to connect to Flask backend. Please ensure the server is running on port 5000.');
      }

      setLastUpdated(new Date());
    } catch (err) {
      console.error('API Fetch Error:', err);
      setErrorMessage(err.message || 'Failed to communicate with Flask backend API.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [eventFilters]);

  // Load on mount and whenever eventFilters change
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Auto-refresh timer
  useEffect(() => {
    if (!autoRefreshInterval || autoRefreshInterval <= 0) return;
    const timer = setInterval(() => {
      loadDashboardData(false);
    }, autoRefreshInterval);
    return () => clearInterval(timer);
  }, [autoRefreshInterval, loadDashboardData]);

  // Handle Exit Authorization Toggle
  const handleToggleAuthorization = async (assetId, newStatus, notes) => {
    try {
      await updateAuthorization(assetId, newStatus, notes);
      await loadDashboardData(false);
    } catch (err) {
      setErrorMessage(`Failed to update authorization for asset '${assetId}': ${err.message}`);
    }
  };

  return (
    <div className="app-container">
      {/* 1. Header */}
      <Header
        health={health}
        isRefreshing={isRefreshing}
        onRefresh={() => loadDashboardData(true)}
        autoRefreshInterval={autoRefreshInterval}
        setAutoRefreshInterval={setAutoRefreshInterval}
        lastUpdated={lastUpdated}
      />

      {/* 2. Error Banner */}
      {errorMessage && (
        <div className="error-banner" role="alert">
          <AlertCircle className="icon-md mr-2" aria-hidden="true" />
          <div className="error-content">
            <strong>API Connection Notice:</strong> {errorMessage}
          </div>
          <button
            onClick={() => loadDashboardData(true)}
            className="btn btn-sm btn-outline-danger ml-auto"
            aria-label="Retry connection"
          >
            <RefreshCw className="icon-xs mr-1" aria-hidden="true" /> Retry
          </button>
        </div>
      )}

      {/* 3. Navigation Tabs */}
      <nav className="tab-nav" aria-label="Dashboard Sections">
        <button
          onClick={() => setActiveTab('overview')}
          className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
          aria-selected={activeTab === 'overview'}
          role="tab"
        >
          <LayoutDashboard className="icon-sm mr-2" aria-hidden="true" />
          System Overview
        </button>

        <button
          onClick={() => setActiveTab('assets')}
          className={`tab-btn ${activeTab === 'assets' ? 'active' : ''}`}
          aria-selected={activeTab === 'assets'}
          role="tab"
        >
          <Boxes className="icon-sm mr-2" aria-hidden="true" />
          Asset Inventory
          {summary?.registered_assets != null && (
            <span className="tab-badge">{summary.registered_assets}</span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('simulator')}
          className={`tab-btn ${activeTab === 'simulator' ? 'active' : ''}`}
          aria-selected={activeTab === 'simulator'}
          role="tab"
        >
          <Activity className="icon-sm mr-2" aria-hidden="true" />
          Event Simulator
        </button>

        <button
          onClick={() => setActiveTab('events')}
          className={`tab-btn ${activeTab === 'events' ? 'active' : ''}`}
          aria-selected={activeTab === 'events'}
          role="tab"
        >
          <History className="icon-sm mr-2" aria-hidden="true" />
          Event History & Filter
          {summary?.total_events != null && (
            <span className="tab-badge">{summary.total_events}</span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('audits')}
          className={`tab-btn ${activeTab === 'audits' ? 'active' : ''}`}
          aria-selected={activeTab === 'audits'}
          role="tab"
        >
          <ClipboardCheck className="icon-sm mr-2" aria-hidden="true" />
          Inventory Audits
          {auditsData?.total_count != null && auditsData.total_count > 0 && (
            <span className="tab-badge">{auditsData.total_count}</span>
          )}
        </button>
      </nav>

      {/* 4. Tab Content */}
      <main className="main-content">
        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="tab-pane">
            {/* Summary Cards */}
            <SummaryCards summary={summary} />

            {/* Active Security & Operational Alerts */}
            <AlertsBanner events={eventsData.items} />

            {/* Analytics & Charts */}
            <AnalyticsCharts summary={summary} />

            {/* Quick Recent Events Table */}
            <RecentEventsTable
              eventsData={eventsData}
              isLoading={isLoading}
              filters={eventFilters}
              setFilters={setEventFilters}
              onApplyFilters={() => loadDashboardData(false)}
            />
          </div>
        )}

        {/* ASSET INVENTORY TAB */}
        {activeTab === 'assets' && (
          <div className="tab-pane">
            <AssetInventoryTable
              assets={assets}
              isLoading={isLoading}
              onToggleAuthorization={handleToggleAuthorization}
            />
          </div>
        )}

        {/* EVENT HISTORY TAB */}
        {activeTab === 'events' && (
          <div className="tab-pane">
            <RecentEventsTable
              eventsData={eventsData}
              isLoading={isLoading}
              filters={eventFilters}
              setFilters={setEventFilters}
              onApplyFilters={() => loadDashboardData(false)}
            />
          </div>
        )}

        {/* AUDITS TAB */}
        {activeTab === 'audits' && (
          <div className="tab-pane">
            <AuditHistorySection
              auditsData={auditsData}
              isLoading={isLoading}
            />
          </div>
        )}

        {/* SIMULATOR TAB */}
        {activeTab === 'simulator' && (
          <div className="tab-pane">
            <Simulator
              assets={assets}
              fetchZones={fetchZones}
              postTrackingEvent={postTrackingEvent}
              refreshDashboard={() => loadDashboardData(false)}
            />
          </div>
        )}
      </main>

      {/* 5. Accessible Footer */}
      <footer className="app-footer">
        <p>IoT-Based Smart Asset Tracking and Anomaly Detection System &bull; College Capstone Project</p>
        <p className="footer-subtext">
          Local Backend: Flask 3.1 &bull; Persistence: SQLite &bull; Client: React + Vite
        </p>
      </footer>
    </div>
  );
}
