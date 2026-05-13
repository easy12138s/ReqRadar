import { apiClient } from './client';

export interface RequirementRelease {
  id: number;
  project_id: number;
  user_id: number;
  task_id: number | null;
  release_code: string;
  version: number;
  title: string;
  content: string;
  context_json: Record<string, unknown> | null;
  status: 'draft' | 'published' | 'archived';
  superseded_by: number | null;
  published_at: string | null;
  archived_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateReleaseRequest {
  project_id: number;
  release_code: string;
  title: string;
  content: string;
  context_json?: Record<string, unknown> | null;
  task_id?: number | null;
}

export interface UpdateReleaseRequest {
  title?: string;
  content?: string;
  context_json?: Record<string, unknown> | null;
}

export async function listReleases(params?: {
  project_id?: number;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<RequirementRelease[]> {
  const response = await apiClient.get<RequirementRelease[]>('/releases', { params });
  return response.data;
}

export async function getRelease(releaseId: number): Promise<RequirementRelease> {
  const response = await apiClient.get<RequirementRelease>(`/releases/${releaseId}`);
  return response.data;
}

export async function createRelease(data: CreateReleaseRequest): Promise<RequirementRelease> {
  const response = await apiClient.post<RequirementRelease>('/releases', data);
  return response.data;
}

export async function updateRelease(releaseId: number, data: UpdateReleaseRequest): Promise<RequirementRelease> {
  const response = await apiClient.put<RequirementRelease>(`/releases/${releaseId}`, data);
  return response.data;
}

export async function publishRelease(releaseId: number): Promise<RequirementRelease> {
  const response = await apiClient.post<RequirementRelease>(`/releases/${releaseId}/publish`);
  return response.data;
}

export async function archiveRelease(releaseId: number): Promise<RequirementRelease> {
  const response = await apiClient.post<RequirementRelease>(`/releases/${releaseId}/archive`);
  return response.data;
}

export async function deleteRelease(releaseId: number): Promise<void> {
  await apiClient.delete(`/releases/${releaseId}`);
}
