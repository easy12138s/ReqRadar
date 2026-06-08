export type SessionStatus =
  | 'CREATED'
  | 'READY'
  | 'RUNNING'
  | 'CHECKPOINTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLING'
  | 'CANCELLED'
  | 'TIMEOUT'
  | 'ABORTED'
  | 'WAITING_INPUT';

export interface SessionResponse {
  session_id: string;
  project_id: string;
  user_id: string;
  requirement_text: string | null;
  status: SessionStatus;
  config: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  total_reasoning_steps: number;
  last_checkpoint_version: number;
}

export interface CreateSessionRequest {
  project_id: string;
  requirement_text?: string;
  config?: Record<string, unknown>;
}

export interface StartSessionRequest {
  resume_from?: number;
  requirement_text?: string;
}
