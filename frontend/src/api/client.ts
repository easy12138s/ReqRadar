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

    if (status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/app/login';
    } else if (status === 403) {
      message.error('没有权限执行此操作');
    } else if (status === 422) {
      message.error('请求参数错误');
    } else if (status && status >= 500) {
      message.error('服务器错误，请稍后重试');
    } else if (!error.response) {
      message.error('网络错误，请检查网络连接');
    } else {
      const detail =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        '发生错误';
      message.error(detail);
    }

    return Promise.reject(error);
  }
);