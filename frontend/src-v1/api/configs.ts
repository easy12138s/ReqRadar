import { apiClient } from './client';

export interface ConfigValue {
  key: string;
  value: unknown;
  value_type: string;
  is_sensitive: boolean;
  updated_at: string | null;
}

export interface ConfigValueRequest {
  value: unknown;
  value_type?: string;
  description?: string;
  is_sensitive?: boolean;
}

// Legacy compatibility functions (used by UserPreferences, etc.)
export async function getConfig(key: string, scope: 'user' | 'project' | 'system' = 'user', projectId?: string): Promise<{ value: unknown }> {
  if (scope === 'user') {
    try {
      const res = await getUserConfig(key);
      return { value: res.value };
    } catch {
      return { value: undefined };
    }
  }
  if (scope === 'project' && projectId) {
    try {
      const res = await getProjectConfig(Number(projectId), key);
      return { value: res.value };
    } catch {
      return { value: undefined };
    }
  }
  try {
    const res = await getSystemConfig(key);
    return { value: res.value };
  } catch {
    return { value: undefined };
  }
}

export async function setConfig(key: string, value: unknown, scope: 'user' | 'project' = 'user', projectId?: string): Promise<void> {
  const valueType = typeof value === 'number' ? 'int' : typeof value === 'boolean' ? 'bool' : 'str';
  const req: ConfigValueRequest = { value, value_type: valueType };
  if (scope === 'user') {
    await setUserConfig(key, req);
  } else if (scope === 'project' && projectId) {
    await setProjectConfig(Number(projectId), key, req);
  }
}

// System configs (admin only)
export async function listSystemConfigs(): Promise<ConfigValue[]> {
  const response = await apiClient.get<ConfigValue[]>('/configs/system');
  return response.data;
}

export async function getSystemConfig(key: string): Promise<ConfigValue> {
  const response = await apiClient.get<ConfigValue>(`/configs/system/${key}`);
  return response.data;
}

export async function setSystemConfig(key: string, req: ConfigValueRequest): Promise<ConfigValue> {
  const response = await apiClient.put<ConfigValue>(`/configs/system/${key}`, req);
  return response.data;
}

export async function deleteSystemConfig(key: string): Promise<void> {
  await apiClient.delete(`/configs/system/${key}`);
}

// Project configs
export async function listProjectConfigs(projectId: number): Promise<ConfigValue[]> {
  const response = await apiClient.get<ConfigValue[]>(`/projects/${projectId}/configs`);
  return response.data;
}

export async function getProjectConfig(projectId: number, key: string): Promise<ConfigValue> {
  const response = await apiClient.get<ConfigValue>(`/projects/${projectId}/configs/${key}`);
  return response.data;
}

export async function setProjectConfig(projectId: number, key: string, req: ConfigValueRequest): Promise<ConfigValue> {
  const response = await apiClient.put<ConfigValue>(`/projects/${projectId}/configs/${key}`, req);
  return response.data;
}

export async function deleteProjectConfig(projectId: number, key: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/configs/${key}`);
}

// User configs
export async function listUserConfigs(): Promise<ConfigValue[]> {
  const response = await apiClient.get<ConfigValue[]>('/me/configs');
  return response.data;
}

export async function getUserConfig(key: string): Promise<ConfigValue> {
  const response = await apiClient.get<ConfigValue>(`/me/configs/${key}`);
  return response.data;
}

export async function setUserConfig(key: string, req: ConfigValueRequest): Promise<ConfigValue> {
  const response = await apiClient.put<ConfigValue>(`/me/configs/${key}`, req);
  return response.data;
}

export async function deleteUserConfig(key: string): Promise<void> {
  await apiClient.delete(`/me/configs/${key}`);
}

// Resolve config (see final value across all levels)
export async function resolveConfig(key: string, projectId?: number): Promise<{ key: string; resolved_value: unknown; source: string }> {
  const params: Record<string, string | number> = { key };
  if (projectId) params.project_id = projectId;
  const response = await apiClient.get('/configs/resolve', { params });
  return response.data;
}
