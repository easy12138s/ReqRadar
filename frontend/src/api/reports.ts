import { apiClient } from './client';
import type { Report } from '@/types/api';

export async function getReport(taskId: string): Promise<Report> {
  const response = await apiClient.get<Report>(`/reports/${taskId}`);
  return response.data;
}

export async function getReportMarkdown(taskId: string): Promise<string> {
  const response = await apiClient.get<string>(`/reports/${taskId}/markdown`, {
    responseType: 'text',
  });
  return response.data;
}

export async function getReportHtml(taskId: string): Promise<string> {
  const response = await apiClient.get<string>(`/reports/${taskId}/html`, {
    responseType: 'text',
  });
  return response.data;
}
