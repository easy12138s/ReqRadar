import { apiClient } from './client';
import type { EvidenceItem } from '@/types/api';

export async function getEvidenceChain(taskId: string, versionNumber?: number): Promise<{ evidence: EvidenceItem[] }> {
  const params = versionNumber !== undefined ? { version_number: versionNumber } : {};
  const response = await apiClient.get<{ evidence: EvidenceItem[] }>(`/analyses/${taskId}/evidence`, { params });
  return response.data;
}

export async function getEvidenceDetail(taskId: string, evidenceId: string, versionNumber?: number): Promise<EvidenceItem> {
  const params = versionNumber !== undefined ? { version_number: versionNumber } : {};
  const response = await apiClient.get<EvidenceItem>(`/analyses/${taskId}/evidence/${evidenceId}`, { params });
  return response.data;
}
