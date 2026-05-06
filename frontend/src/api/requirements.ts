import { apiClient } from './client';

export interface SourceFile {
  filename: string;
  type: string;
  size?: number;
}

export interface RequirementDocument {
  id: number;
  title: string;
  consolidated_text: string;
  source_files: SourceFile[];
  status: string;
  version: number;
  created_at: string;
  updated_at?: string;
}

export async function preprocessRequirements(
  projectId: string,
  files: File[],
  title: string = ''
): Promise<RequirementDocument> {
  const formData = new FormData();
  formData.append('project_id', projectId);
  files.forEach(f => formData.append('files', f));
  if (title) formData.append('title', title);
  const { data } = await apiClient.post('/requirements/preprocess', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getRequirement(id: number): Promise<RequirementDocument> {
  const { data } = await apiClient.get(`/requirements/${id}`);
  return data;
}

export async function updateRequirement(id: number, consolidated_text: string): Promise<void> {
  await apiClient.put(`/requirements/${id}`, { consolidated_text });
}

export async function deleteRequirement(id: number): Promise<void> {
  await apiClient.delete(`/requirements/${id}`);
}

export async function listRequirements(projectId: string): Promise<RequirementDocument[]> {
  const { data } = await apiClient.get('/requirements', { params: { project_id: projectId } });
  return data;
}
