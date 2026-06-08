export type EventType =
  | 'SESSION_CREATED'
  | 'SESSION_STARTED'
  | 'SESSION_CHECKPOINTED'
  | 'SESSION_COMPLETED'
  | 'SESSION_FAILED'
  | 'SESSION_CANCELLING'
  | 'SESSION_CANCELLED'
  | 'SESSION_TIMEOUT'
  | 'SESSION_ABORTED'
  | 'SESSION_WAITING_INPUT'
  | 'SESSION_RESUMED'
  | 'STEP_STARTED'
  | 'STEP_COMPLETED'
  | 'TOOL_INVOKED'
  | 'TOOL_RETURNED'
  | 'TOOL_RETRY'
  | 'TOOL_TIMEOUT'
  | 'TOOL_PERMISSION_DENIED'
  | 'TOOL_CHECKPOINT_FAILED'
  | 'CONTEXT_COLLECTED'
  | 'CONTEXT_SCORED'
  | 'EVIDENCE_ADDED'
  | 'DIMENSION_CHANGED';

export type EventLevel = 'session' | 'reasoning' | 'cognitive';

export interface EventRecord {
  id: string;
  session_id: string;
  event_type: EventType;
  level: EventLevel;
  producer: string;
  payload: Record<string, unknown>;
  created_at: string;
}
