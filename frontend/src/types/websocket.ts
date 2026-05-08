export type WebSocketMessageType =
  | 'analysis_started'
  | 'agent_thinking'
  | 'analysis_complete'
  | 'analysis_cancelled'
  | 'analysis_failed';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  task_id: number;
  message?: string;
  risk_level?: string;
  error?: string;
}

export interface WebSocketState {
  connected: boolean;
  message: WebSocketMessage | null;
  error: string | null;
}
