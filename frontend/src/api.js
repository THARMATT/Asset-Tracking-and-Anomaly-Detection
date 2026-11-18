// ==========================================
// AXIOS API CLIENT
// IoT Asset Tracking & Anomaly Detection
// ==========================================

import axios from 'axios';

// Configurable base URL: defaults to Vite proxy path or environment variable
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchHealth = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

export const fetchSummary = async () => {
  const response = await apiClient.get('/summary');
  return response.data.data;
};

export const fetchAssets = async (activeOnly = false) => {
  const response = await apiClient.get('/assets', {
    params: { active_only: activeOnly },
  });
  return response.data.data;
};

export const fetchSingleAsset = async (assetId) => {
  const response = await apiClient.get(`/assets/${encodeURIComponent(assetId)}`);
  return response.data.data;
};

export const updateAsset = async (assetId, assetData) => {
  const response = await apiClient.put(
    `/assets/${encodeURIComponent(assetId)}`,
    assetData
  );
  return response.data;
};

export const fetchEvents = async ({
  limit = 20,
  offset = 0,
  status = '',
  asset_id = '',
  zone = '',
} = {}) => {
  const params = { limit, offset };
  if (status) params.status = status;
  if (asset_id) params.asset_id = asset_id;
  if (zone) params.zone = zone;

  const response = await apiClient.get('/events', { params });
  return response.data.data;
};

export const postTrackingEvent = async (eventPayload) => {
  const response = await apiClient.post('/events', eventPayload);
  return response.data;
};

export const fetchAudits = async ({ limit = 10, offset = 0 } = {}) => {
  const response = await apiClient.get('/audits', {
    params: { limit, offset },
  });
  return response.data.data;
};

export const triggerAudit = async (scannedAssetIds, notes = '') => {
  const response = await apiClient.post('/audits', {
    scanned_asset_ids: scannedAssetIds,
    notes,
  });
  return response.data;
};

export const fetchZones = async () => {
  const response = await apiClient.get('/zones');
  return response.data.data;
};

export const updateAuthorization = async (assetId, authorizedExit, notes = '') => {
  const response = await apiClient.put(
    `/authorization/${encodeURIComponent(assetId)}`,
    {
      authorized_exit: authorizedExit ? 1 : 0,
      notes,
    }
  );
  return response.data;
};

// ==========================================
// SPATIAL LOCATION ENDPOINTS
// ==========================================
// IMPORTANT: Location data is independent of RFID/gate authorization logic.
// Submitting a location NEVER changes anomaly status or gate permissions.

export const fetchLatestLocations = async () => {
  const response = await apiClient.get('/locations/latest');
  return response.data.data;
};

export const fetchAssetLocationHistory = async (assetId, limit = 100) => {
  const response = await apiClient.get(
    `/assets/${encodeURIComponent(assetId)}/locations`,
    { params: { limit } }
  );
  return response.data.data;
};

export const postLocation = async (payload) => {
  const response = await apiClient.post('/locations', payload);
  return response.data;
};

export const fetchTelemetryHistory = async (assetId = null, limit = 50) => {
  const params = { limit };
  if (assetId) params.asset_id = assetId;
  const response = await apiClient.get('/telemetry/history', { params });
  return response.data.data;
};

export const postSimulatorMovement = async (payload) => {
  const response = await apiClient.post('/simulator/movement', payload);
  return response.data;
};

// ==========================================
// IoT SIMULATOR ENGINE ENDPOINTS
// ==========================================

export const fetchIotStatus = async () => {
  const response = await apiClient.get('/iot/status');
  return response.data.data;
};

export const startIotSimulator = async (interval_s = 5) => {
  const response = await apiClient.post('/iot/start', { interval_s });
  return response.data;
};

export const stopIotSimulator = async () => {
  const response = await apiClient.post('/iot/stop');
  return response.data;
};

export const pauseIotSimulator = async () => {
  const response = await apiClient.post('/iot/pause');
  return response.data;
};

export const resumeIotSimulator = async () => {
  const response = await apiClient.post('/iot/resume');
  return response.data;
};

export const triggerIotTick = async (demo_anomaly = false) => {
  const response = await apiClient.post('/iot/tick', { demo_anomaly });
  return response.data;
};

export const fetchIotReadings = async () => {
  const response = await apiClient.get('/iot/readings');
  return response.data.data;
};

export default apiClient;
