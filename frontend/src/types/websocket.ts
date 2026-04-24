import type { AnalysisStatus } from './api';

export interface WebSocketMessage {
  type: 'progress' | 'status' | 'error' | 'complete';
  data: ProgressData | StatusData | ErrorData | CompleteData;
}

export interface ProgressData {
  step: number;
  total_steps: number;
  step_name: string;
  message: string;
}

export interface StatusData {
  status: AnalysisStatus;
  message?: string;
}

export interface ErrorData {
  message: string;
  details?: string;
}

export interface CompleteData {
  task_id: string;
  report_id?: string;
}

export interface WebSocketState {
  connected: boolean;
  message: WebSocketMessage | null;
  error: string | null;
}

export interface AgentThinkingMessage extends WebSocketMessage {
  type: 'agent_thinking';
  task_id: string;
  message: string;
}

export interface AgentActionMessage extends WebSocketMessage {
  type: 'agent_action';
  task_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
}

export interface DimensionProgressMessage extends WebSocketMessage {
  type: 'dimension_progress';
  task_id: string;
  step: number;
  max_steps: number;
  dimensions: Record<string, string>;
  evidence_count: number;
}

export interface EvidenceCollectedMessage extends WebSocketMessage {
  type: 'evidence_collected';
  task_id: string;
  evidence_id: string;
  source: string;
}

export interface ReportVersionMessage extends WebSocketMessage {
  type: 'report_version';
  task_id: string;
  version_number: number;
  trigger_type: string;
}
