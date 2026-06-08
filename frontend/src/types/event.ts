export type EventType =
  | 'SESSION_CREATED'
  | 'SESSION_STARTED'
  | 'SESSION_COMPLETED'
  | 'SESSION_FAILED'
  | 'SESSION_CANCELLED'
  | 'SESSION_PAUSED'
  | 'SESSION_TIMEOUT'
  | 'STEP_STARTED'
  | 'STEP_COMPLETED'
  | 'STEP_FAILED'
  | 'EVIDENCE_COLLECTED'
  | 'DIMENSION_UPDATED'
  | 'CHECKPOINT_CREATED'
  | 'TOOL_CALLED'
  | 'TOOL_COMPLETED'
  | 'TOOL_FAILED'
  | 'L3_KNOWLEDGE_CREATED'
  | 'L3_KNOWLEDGE_UPDATED'
  | 'L3_KNOWLEDGE_DEPRECATED'
  | 'L3_FRESHNESS_DECAY'
  | 'L3_FEEDBACK_APPLIED'
  | 'L3_CONSOLIDATION_RUN'
  | 'SESSION_WAITING_INPUT';

export type EventLevel = 'session' | 'reasoning' | 'system';

export interface EventRecord {
  id: string;
  session_id: string;
  event_type: EventType;
  level: EventLevel;
  producer: string;
  payload: Record<string, unknown>;
  created_at: string;
}
