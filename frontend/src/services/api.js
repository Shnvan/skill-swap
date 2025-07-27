// src/services/api.js
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Store user reference for interceptor
let currentUser = null;

// Function to set the current user (called from AuthContext)
export const setCurrentUser = (user) => {
  currentUser = user;
};

// Function to get the current user
export const getCurrentUser = () => currentUser;

// Axios request interceptor to dynamically set the `x-user-id` header
apiClient.interceptors.request.use((config) => {
  if (currentUser?.id) {
    config.headers['x-user-id'] = currentUser.id;
  } else {
    // Fallback for development
    config.headers['x-user-id'] = 'test-user-123';
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Add response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      console.error('Unauthorized access');
    }
    return Promise.reject(error);
  }
);

export const apiService = {
  // Users
  getProfile: () => apiClient.get('/users/me'),
  updateProfile: (data) => apiClient.put('/users/', data),
  createUser: (data) => apiClient.post('/users/', data),
  
  // Tasks
  getOpenTasks: (params = {}) => apiClient.get('/tasks/open', { params }),
  getMyPostedTasks: (params = {}) => apiClient.get('/tasks/my/posted', { params }),
  getMyAcceptedTasks: (params = {}) => apiClient.get('/tasks/my/accepted', { params }),
  createTask: (task) => apiClient.post('/tasks/', task),
  acceptTask: (taskId) => apiClient.post(`/tasks/${taskId}/accept`),
  completeTask: (taskId) => apiClient.post(`/tasks/${taskId}/complete`),
  deleteTask: (taskId) => apiClient.delete(`/tasks/${taskId}`),
  
  // Ratings
  getMyRatings: (params = {}) => apiClient.get('/ratings/my/received', { params }),
  getMyGivenRatings: (params = {}) => apiClient.get('/ratings/my/given', { params }),
  createRating: (rating) => apiClient.post('/ratings/', rating),
  flagRating: (ratingId, reason) => apiClient.post(`/ratings/${ratingId}/flag`, null, { params: { flag_reason: reason } }),
  
  // Reports
  createReport: (report) => apiClient.post('/reports/', report),
  getMyReports: (params = {}) => apiClient.get('/reports/my/sent', { params }),
  getReportsAgainstMe: (params = {}) => apiClient.get('/reports/my/received', { params })
};

// Transform backend responses to match frontend expectations
export const transformTaskResponse = (response) => ({
  tasks: response.data.tasks || response.data.items || [response.data],
  count: response.data.count || (response.data.tasks ? response.data.tasks.length : 1),
  message: response.data.message
});

export const transformRatingResponse = (response) => ({
  ratings: response.data.ratings || [response.data],
  statistics: response.data.statistics || { average_rating: 0, total_ratings: 0 }
});