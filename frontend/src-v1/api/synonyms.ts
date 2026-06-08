import { apiClient } from './client';
import type { SynonymMapping, SynonymMappingCreate } from '@/types/api';

export async function getSynonyms(projectId?: string): Promise<SynonymMapping[]> {
  const params = projectId ? { project_id: projectId } : {};
  const response = await apiClient.get<SynonymMapping[]>('/synonyms', { params });
  return response.data;
}

export async function createSynonym(data: SynonymMappingCreate): Promise<SynonymMapping> {
  const response = await apiClient.post<SynonymMapping>('/synonyms', data);
  return response.data;
}

export async function updateSynonym(id: string, data: Partial<SynonymMappingCreate>): Promise<SynonymMapping> {
  const response = await apiClient.put<SynonymMapping>(`/synonyms/${id}`, data);
  return response.data;
}

export async function deleteSynonym(id: string): Promise<void> {
  await apiClient.delete(`/synonyms/${id}`);
}
