import { apiClient } from './client';
import type { ReportVersion, ReportVersionDetail } from '@/types/api';

export async function getVersions(taskId: string): Promise<{ versions: ReportVersion[] }> {
  const response = await apiClient.get<{ versions: ReportVersion[] }>(`/analyses/${taskId}/reports/versions`);
  return response.data;
}

export async function getVersion(taskId: string, versionNumber: number): Promise<ReportVersionDetail> {
  const response = await apiClient.get<ReportVersionDetail>(`/analyses/${taskId}/reports/versions/${versionNumber}`);
  return response.data;
}

export async function rollbackVersion(taskId: string, versionNumber: number): Promise<{ success: boolean; current_version: number }> {
  const response = await apiClient.post(`/analyses/${taskId}/reports/rollback`, { version_number: versionNumber });
  return response.data;
}
