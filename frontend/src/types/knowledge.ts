export type KnowledgeType =
  | 'terminology'
  | 'module_profile'
  | 'architecture_constraint'
  | 'code_pattern'
  | 'historical_decision'
  | 'risk_record'
  | 'incident_record';

export type FreshnessStatus = 'fresh' | 'stale' | 'deprecated';

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
