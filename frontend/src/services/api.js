import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('frise_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const authAPI = {
  register: (data) => apiClient.post('/api/auth/register', data),
  login: (data) => apiClient.post('/api/auth/login', data),
  me: () => apiClient.get('/api/auth/me'),
  updateFridge: (fridge_capacity) => apiClient.put('/api/settings/fridge', { fridge_capacity }),
};

// Food Items API
export const foodItemsAPI = {
  create: (data) => apiClient.post('/api/food-items', data),
  list: (params = {}) => apiClient.get('/api/food-items', { params }),
  get: (id) => apiClient.get(`/api/food-items/${id}`),
  update: (id, data) => apiClient.put(`/api/food-items/${id}`, data),
  delete: (id) => apiClient.delete(`/api/food-items/${id}`),
  consume: (id) => apiClient.post(`/api/food-items/${id}/consume`),
  waste: (id) => apiClient.post(`/api/food-items/${id}/waste`),
  lookupBarcode: (barcode) => apiClient.get(`/api/barcode/${barcode}`),
  scanExpiryDate: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/ocr/expiry-date', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  scanBarcodeNumber: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/ocr/barcode', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  uploadImage: (id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/api/food-items/${id}/upload-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  search: (query) => apiClient.get('/api/search', { params: { query } }),
};

export const getMediaUrl = (path) => {
  if (!path) return '';
  if (/^(https?:|blob:|data:)/i.test(path)) return path;

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

// Dashboard API
export const dashboardAPI = {
  getStats: () => apiClient.get('/api/dashboard/stats'),
  getCategoryStats: () => apiClient.get('/api/dashboard/categories'),
  getConsumptionPatterns: () => apiClient.get('/api/dashboard/consumption-patterns'),
};

// Notifications API
export const notificationsAPI = {
  list: (params = {}) => apiClient.get('/api/notifications', { params }),
  markRead: (id) => apiClient.put(`/api/notifications/${id}/read`),
  delete: (id) => apiClient.delete(`/api/notifications/${id}`),
};

export default apiClient;
