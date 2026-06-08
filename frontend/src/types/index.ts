export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface VerifyTokenResponse {
  valid: boolean;
  user: UserProfile | null;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export type { SessionStatus, SessionResponse, CreateSessionRequest, StartSessionRequest } from './session';
export type { EventType, EventLevel, EventRecord } from './event';
export type { DimensionStatus, DimensionState, DimensionSummary } from './dimension';
export type { CheckpointType, CheckpointRecord } from './checkpoint';
export type { KnowledgeType, FreshnessStatus, KnowledgeEntry, KnowledgeQueryParams } from './knowledge';
export type { WsEvent, WsConnectionState } from './ws';
