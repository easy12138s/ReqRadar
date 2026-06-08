export type CheckpointType =
  | 'STEP_COMPLETE'
  | 'TOOL_PRE'
  | 'TOOL_POST'
  | 'MANUAL'
  | 'PERIODIC'
  | 'CHATBACK_SNAPSHOT';

export interface CheckpointRecord {
  checkpoint_id: string;
  session_id: string;
  version: number;
  checkpoint_type: CheckpointType;
  state_summary: Record<string, unknown>;
  created_at: string;
}
