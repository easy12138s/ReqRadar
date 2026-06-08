import client from './client';
import type { KnowledgeEntry, KnowledgeQueryParams } from '@/types';

export async function queryKnowledge(params: KnowledgeQueryParams): Promise<{ items: KnowledgeEntry[] }> {
  const { data } = await client.get('/knowledge/query', { params });
  return data;
}

export async function getProjectKnowledge(projectId: string, types?: string): Promise<{ items: KnowledgeEntry[] }> {
  const { data } = await client.get(`/knowledge/${projectId}`, { params: { types } });
  return data;
}
