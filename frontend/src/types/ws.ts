import type { EventType, EventLevel } from './event';

export interface WsEvent {
  event_type: EventType;
  level: EventLevel;
  session_id: string;
  producer: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface WsConnectionState {
  connected: boolean;
  reconnecting: boolean;
  error: string | null;
}
