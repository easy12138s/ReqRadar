import { apiClient } from './client';
import type { ReportTemplate, ReportTemplateCreate } from '@/types/api';

export async function getTemplates(): Promise<ReportTemplate[]> {
  const response = await apiClient.get<ReportTemplate[]>('/templates');
  return response.data;
}

export async function getTemplate(id: string): Promise<ReportTemplate> {
  const response = await apiClient.get<ReportTemplate>(`/templates/${id}`);
  return response.data;
}

export async function createTemplate(data: ReportTemplateCreate): Promise<ReportTemplate> {
  const response = await apiClient.post<ReportTemplate>('/templates', data);
  return response.data;
}

export async function updateTemplate(id: string, data: Partial<ReportTemplateCreate>): Promise<ReportTemplate> {
  const response = await apiClient.put<ReportTemplate>(`/templates/${id}`, data);
  return response.data;
}

export async function deleteTemplate(id: string): Promise<void> {
  await apiClient.delete(`/templates/${id}`);
}

export async function setDefaultTemplate(id: string): Promise<void> {
  await apiClient.post(`/templates/${id}/set-default`);
}
