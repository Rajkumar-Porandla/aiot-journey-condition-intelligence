/**
 * Central API Client with Auth Token handling and error formatting.
 */

const BASE_URL = '/api';

export function getAuthToken() {
  return localStorage.getItem('aiot_auth_token');
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('aiot_auth_token', token);
  } else {
    localStorage.removeItem('aiot_auth_token');
  }
}

export function getSavedUser() {
  const u = localStorage.getItem('aiot_auth_user');
  try {
    return u ? JSON.parse(u) : null;
  } catch (e) {
    return null;
  }
}

export function setSavedUser(user) {
  if (user) {
    localStorage.setItem('aiot_auth_user', JSON.stringify(user));
  } else {
    localStorage.removeItem('aiot_auth_user');
  }
}

export async function apiRequest(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  const response = await fetch(url, config);

  if (response.status === 401) {
    // Session expired or invalid
    setAuthToken(null);
    setSavedUser(null);
    if (!window.location.pathname.includes('/login')) {
      window.dispatchEvent(new CustomEvent('aiot:unauthorized'));
    }
  }

  const contentType = response.headers.get('content-type');
  let data;
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMsg = data?.error || data?.message || `Request failed with status ${response.status}`;
    const err = new Error(errorMsg);
    err.status = response.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const api = {
  // Auth
  login: (credentials) => apiRequest('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
  register: (userData) => apiRequest('/auth/register', { method: 'POST', body: JSON.stringify(userData) }),
  getMe: () => apiRequest('/auth/me'),
  logout: () => apiRequest('/auth/logout', { method: 'POST' }),

  // Dashboard
  getDashboardStats: () => apiRequest('/dashboard/stats'),

  // Products
  getProducts: () => apiRequest('/products'),
  getProduct: (id) => apiRequest(`/products/${id}`),
  createProduct: (data) => apiRequest('/products', { method: 'POST', body: JSON.stringify(data) }),
  updateProduct: (id, data) => apiRequest(`/products/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Shipments
  getShipments: (params = '') => apiRequest(`/shipments${params ? '?' + params : ''}`),
  getShipment: (id) => apiRequest(`/shipments/${id}`),
  createShipment: (data) => apiRequest('/shipments', { method: 'POST', body: JSON.stringify(data) }),
  updateShipment: (id, data) => apiRequest(`/shipments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteShipment: (id) => apiRequest(`/shipments/${id}`, { method: 'DELETE' }),
  getLocations: () => apiRequest('/shipments/locations'),

  // Simulation
  startSimulation: (id, data) => apiRequest(`/simulation/start/${id}`, { method: 'POST', body: JSON.stringify(data) }),
  pauseSimulation: (id) => apiRequest(`/simulation/pause/${id}`, { method: 'POST' }),
  resumeSimulation: (id) => apiRequest(`/simulation/resume/${id}`, { method: 'POST' }),
  stopSimulation: (id) => apiRequest(`/simulation/stop/${id}`, { method: 'POST' }),
  completeSimulation: (id) => apiRequest(`/simulation/complete/${id}`, { method: 'POST' }),
  getReadings: (id, params = '') => apiRequest(`/readings/${id}${params ? '?' + params : ''}`),

  // Alerts
  getAllAlerts: (params = '') => apiRequest(`/alerts${params ? '?' + params : ''}`),
  getShipmentAlerts: (id) => apiRequest(`/alerts/${id}`),

  // ML & Predictions
  getMLMetrics: () => apiRequest('/ml/metrics'),
  predictShipment: (id) => apiRequest(`/predict/${id}`, { method: 'POST' }),
  getShipmentPredictions: (id) => apiRequest(`/predictions/${id}`),
  runWhatIf: (data) => apiRequest('/simulator/what-if', { method: 'POST', body: JSON.stringify(data) }),
  getScenarios: (shipmentId) => apiRequest(`/simulator/scenarios/${shipmentId}`),
  compareShipments: (shipmentIds) => apiRequest('/compare', { method: 'POST', body: JSON.stringify({ shipment_ids: shipmentIds }) }),

  // Reports
  getPdfReportUrl: (shipmentId) => `/api/reports/${shipmentId}/pdf`,
};

