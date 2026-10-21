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

export default apiClient;
