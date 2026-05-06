import { apiClient } from './client';
import type {
  AnalysisCreate,
  AnalysisTask,
} from '@/types/api';

export async function getAnalyses(): Promise<AnalysisTask[]> {
  const response = await apiClient.get<AnalysisTask[]>('/analyses');
  return response.data;
}

export async function getAnalysis(id: string): Promise<AnalysisTask> {
  const response = await apiClient.get<AnalysisTask>(`/analyses/${id}`);
  return response.data;
}

export async function createAnalysis(data: AnalysisCreate): Promise<AnalysisTask> {
  const response = await apiClient.post<AnalysisTask>('/analyses', data);
  return response.data;
}

export async function uploadAnalysis(
  projectId: string,
  file: File,
  depth?: string,
  templateId?: string,
  focusAreas?: string[]
): Promise<AnalysisTask> {
  const formData = new FormData();
  formData.append('project_id', projectId);
  formData.append('file', file);
  if (depth) formData.append('depth', depth);
  if (templateId) formData.append('template_id', templateId);
  if (focusAreas && focusAreas.length > 0) formData.append('focus_areas', JSON.stringify(focusAreas));

  const response = await apiClient.post<AnalysisTask>('/analyses/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

export async function retryAnalysis(id: string): Promise<AnalysisTask> {
  const response = await apiClient.post<AnalysisTask>(`/analyses/${id}/retry`);
  return response.data;
}

export async function cancelAnalysis(id: string): Promise<void> {
  await apiClient.post(`/analyses/${id}/cancel`);
}
