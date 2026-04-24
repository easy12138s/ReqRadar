import { apiClient } from './client';

export async function getConfig(key: string, scope: 'user' | 'project' | 'system' = 'user', projectId?: string): Promise<{ key: string; value: unknown; scope: string }> {
  const params: Record<string, string> = { scope };
  if (projectId) params.project_id = projectId;
  const response = await apiClient.get(`/configs/${key}`, { params });
  return response.data;
}

export async function setConfig(key: string, value: unknown, scope: 'user' | 'project' = 'user', projectId?: string): Promise<void> {
  const body: Record<string, unknown> = { value, scope };
  if (projectId) body.project_id = projectId;
  await apiClient.put(`/configs/${key}`, body);
}
