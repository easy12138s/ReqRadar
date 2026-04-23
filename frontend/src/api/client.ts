import axios, { AxiosError } from 'axios';
import { message } from 'antd';

const API_BASE_URL = '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const status = error.response?.status;
    const detail =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An error occurred';

    if (status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    } else if (status === 403) {
      message.error('You do not have permission to perform this action');
    } else if (status === 422) {
      message.error(`Validation error: ${detail}`);
    } else if (status && status >= 500) {
      message.error('Server error. Please try again later.');
    } else if (!error.response) {
      message.error('Network error. Please check your connection.');
    } else {
      message.error(detail);
    }

    return Promise.reject(error);
  }
);
