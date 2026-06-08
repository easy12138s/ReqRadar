import client from './client';
import type { KnowledgeEntry, KnowledgeQueryParams } from '@/types';

export async function queryKnowledge(params: KnowledgeQueryParams): Promise<{ items: KnowledgeEntry[] }> {
  const { project_id, ...body } = params;
  const { data } = await client.post(`/projects/${project_id}/knowledge`, body);
  return data;
}

export async function getProjectKnowledge(projectId: string, types?: string): Promise<{ items: KnowledgeEntry[] }> {
  const { data } = await client.get(`/projects/${projectId}/knowledge`, {
    params: types ? { knowledge_types: types } : undefined,
  });
  return data;
}
