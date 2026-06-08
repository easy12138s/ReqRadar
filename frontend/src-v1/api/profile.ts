import { apiClient } from './client';
import type { ProjectProfile, PendingChange } from '@/types/api';

export async function getProjectProfile(projectId: string): Promise<ProjectProfile> {
  const response = await apiClient.get<ProjectProfile>(`/projects/${projectId}/profile`);
  return response.data;
}

export async function updateProjectProfile(
  projectId: string,
  profile: { content?: string; data?: Record<string, unknown> },
): Promise<ProjectProfile> {
  const response = await apiClient.put<ProjectProfile>(`/projects/${projectId}/profile`, profile);
  return response.data;
}

export async function getPendingChanges(projectId: string): Promise<PendingChange[]> {
  const response = await apiClient.get<PendingChange[]>(`/projects/${projectId}/pending-changes`);
  return response.data;
}

export async function acceptPendingChange(projectId: string, changeId: string): Promise<void> {
  await apiClient.post(`/projects/${projectId}/pending-changes/${changeId}/accept`);
}

export async function rejectPendingChange(projectId: string, changeId: string): Promise<void> {
  await apiClient.post(`/projects/${projectId}/pending-changes/${changeId}/reject`);
}
