import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Unauthenticated axios instance for public endpoints
const publicApi = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data) => api.post('/api/auth/register', data),
  login: (data) => api.post('/api/auth/login', data),
  getCurrentUser: () => api.get('/api/auth/me'),
  updateProfile: (data) => api.put('/api/auth/me', data),
};

// Jobs API
export const jobsAPI = {
  getAll: (params) => api.get('/api/jobs', { params }),
  getById: (id) => api.get(`/api/jobs/${id}`),
  getPipeline: (id) => api.get(`/api/jobs/${id}/pipeline`),
  create: (data) => api.post('/api/jobs', data),
  update: (id, data) => api.put(`/api/jobs/${id}`, data),
  delete: (id) => api.delete(`/api/jobs/${id}`),
  publish: (id) => api.post(`/api/jobs/${id}/publish`),
  close: (id) => api.post(`/api/jobs/${id}/close`),
  getStats: () => api.get('/api/jobs/stats'),
};

// Candidates API
export const candidatesAPI = {
  getAll: (params) => api.get('/api/candidates', { params }),
  getById: (id) => api.get(`/api/candidates/${id}`),
  create: (data) => api.post('/api/candidates', data),
  update: (id, data) => api.put(`/api/candidates/${id}`, data),
  delete: (id) => api.delete(`/api/candidates/${id}`),
  uploadResume: (id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/api/candidates/${id}/upload-resume`, formData, {
      headers: { 'Content-Type': undefined }
    });
  },
  getApplications: (id) => api.get(`/api/candidates/${id}/applications`),
};

// Applications API
export const applicationsAPI = {
  getAll: (params) => api.get('/api/applications', { params }),
  getById: (id) => api.get(`/api/applications/${id}`),
  create: (data) => api.post('/api/applications', data),
  update: (id, data) => api.put(`/api/applications/${id}`, data),
  delete: (id) => api.delete(`/api/applications/${id}`),
  shortlist: (id) => api.post(`/api/applications/${id}/shortlist`),
  reject: (id) => api.post(`/api/applications/${id}/reject`),
  bulkInviteScreening: (ids) => api.post('/api/applications/bulk-invite-screening', { application_ids: ids }),
  getStats: (params) => api.get('/api/applications/stats', { params }),
};

// Screenings API
export const screeningsAPI = {
  getAll: (params) => api.get('/api/screenings', { params }),
  getById: (id) => api.get(`/api/screenings/${id}`),
  create: (data) => api.post('/api/screenings', data),
  update: (id, data) => api.put(`/api/screenings/${id}`, data),
  start: (id) => api.post(`/api/screenings/${id}/start`),
  complete: (id) => api.post(`/api/screenings/${id}/complete`),
  cancel: (id) => api.post(`/api/screenings/${id}/cancel`),
  getStats: () => api.get('/api/screenings/stats'),
};

// Dashboard API
export const dashboardAPI = {
  getStats: () => api.get('/api/dashboard/stats'),
  getRecentActivity: (params) => api.get('/api/dashboard/recent-activity', { params }),
  getPipelineOverview: () => api.get('/api/dashboard/pipeline-overview'),
  getTopJobs: (params) => api.get('/api/dashboard/top-jobs', { params }),
  getRecentApplications: (params) => api.get('/api/dashboard/recent-applications', { params }),
  getScreeningPerformance: (params) => api.get('/api/dashboard/screening-performance', { params }),
  getHiringFunnel: (params) => api.get('/api/dashboard/hiring-funnel', { params }),
};

// Settings API
export const settingsAPI = {
  get: () => api.get('/api/settings'),
  update: (data) => api.put('/api/settings', data),
};

// Public API (no auth token)
export const publicAPI = {
  getJobs: (params) => publicApi.get('/api/public/jobs', { params }),
  getJob: (id) => publicApi.get(`/api/public/jobs/${id}`),
  apply: (formData) => publicApi.post('/api/public/apply', formData, {
    headers: { 'Content-Type': undefined },
  }),
  getStatus: (email) => publicApi.get('/api/public/status', { params: { email } }),
};

export default api;
