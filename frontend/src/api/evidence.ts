import client from './client';

export interface EvidenceItem {
  evidence_id: string;
  session_id: string;
  evidence_type: string;
  content: string;
  source: string;
  confidence: number;
  created_at: string;
}

export async function getSessionEvidence(sessionId: string, params?: { type?: string; limit?: number }): Promise<{ items: EvidenceItem[] }> {
  const { data } = await client.get(`/sessions/${sessionId}/evidence`, { params });
  return data;
}
