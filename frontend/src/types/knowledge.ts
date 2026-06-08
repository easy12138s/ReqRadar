export type KnowledgeType =
  | 'glossary'
  | 'module_profile'
  | 'constraint'
  | 'decision'
  | 'risk'
  | 'requirement'
  | 'incident'
  | 'pattern';

export type FreshnessStatus =
  | 'active'
  | 'historical'
  | 'superseded'
  | 'deprecated'
  | 'stale'
  | 'conflicted';

export interface KnowledgeEntry {
  knowledge_id: string;
  project_id: string;
  knowledge_type: KnowledgeType;
  topic: string;
  content: string;
  confidence: number;
  freshness: FreshnessStatus;
  evidence_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface KnowledgeQueryParams {
  project_id: string;
  knowledge_types?: string;
  query?: string;
  top_k?: number;
}
