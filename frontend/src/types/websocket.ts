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
