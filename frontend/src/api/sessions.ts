import client from './client';
import type { SessionResponse, CreateSessionRequest, StartSessionRequest, EventRecord } from '@/types';

export async function createSession(req: CreateSessionRequest): Promise<SessionResponse> {
  const { data } = await client.post<SessionResponse>('/sessions', req);
  return data;
}

export async function startSession(sessionId: string, req?: StartSessionRequest): Promise<SessionResponse> {
  const { data } = await client.post<SessionResponse>(`/sessions/${sessionId}/start`, req ?? {});
  return data;
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const { data } = await client.get<SessionResponse>(`/sessions/${sessionId}`);
  return data;
}

export async function cancelSession(sessionId: string): Promise<SessionResponse> {
  const { data } = await client.post<SessionResponse>(`/sessions/${sessionId}/cancel`);
  return data;
}

export async function listSessions(params?: { project_id?: string; status?: string; limit?: number }): Promise<{ sessions: SessionResponse[] }> {
  const { data } = await client.get('/sessions', { params });
  return data;
}

export async function getSessionEvents(sessionId: string, limit = 100): Promise<{ events: EventRecord[]; total: number }> {
  const { data } = await client.get(`/sessions/${sessionId}/events`, { params: { limit } });
  return data;
}
