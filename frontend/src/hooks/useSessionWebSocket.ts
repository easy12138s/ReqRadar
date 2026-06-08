import { useEffect, useRef, useState, useCallback } from 'react';
import type { WsEvent, WsConnectionState } from '@/types';

interface UseSessionWebSocketOptions {
  sessionId: string;
  enabled?: boolean;
  onEvent?: (event: WsEvent) => void;
}

export function useSessionWebSocket({ sessionId, enabled = true, onEvent }: UseSessionWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<WsConnectionState>({ connected: false, reconnecting: false, error: null });
  const [events, setEvents] = useState<WsEvent[]>([]);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (!enabled || !sessionId) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/sessions/${sessionId}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setState({ connected: true, reconnecting: false, error: null });
      };

      ws.onmessage = (msg) => {
        try {
          const event: WsEvent = JSON.parse(msg.data);
          setEvents((prev) => [...prev.slice(-499), event]);
          onEventRef.current?.(event);
        } catch {
          // ignore non-JSON messages
        }
      };

      ws.onclose = (evt) => {
        setState((prev) => ({ ...prev, connected: false }));
        if (evt.code !== 1000 && enabled) {
          setState((prev) => ({ ...prev, reconnecting: true }));
          reconnectTimer.current = setTimeout(() => connect(), 3000);
        }
      };

      ws.onerror = () => {
        setState((prev) => ({ ...prev, error: 'WebSocket 连接失败' }));
      };
    } catch (err) {
      setState((prev) => ({ ...prev, error: String(err) }));
    }
  }, [sessionId, enabled]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close(1000);
        wsRef.current = null;
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { state, events, clearEvents };
}

export type { UseSessionWebSocketOptions };
