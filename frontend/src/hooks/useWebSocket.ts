import { useEffect, useRef, useState, useCallback } from 'react';

export type WsStatus = 'connecting' | 'open' | 'closed' | 'reconnecting';

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  enabled?: boolean;
  maxRetries?: number;
}

export function useWebSocket({ url, onMessage, enabled = true, maxRetries = 10 }: UseWebSocketOptions) {
  const [status, setStatus] = useState<WsStatus>('closed');
  const retryCountRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    cleanup();
    setStatus(retryCountRef.current > 0 ? 'reconnecting' : 'connecting');

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('open');
        retryCountRef.current = 0;

        pingTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch {
          // ignore non-JSON
        }
      };

      ws.onerror = () => {
        // handled by onclose
      };

      ws.onclose = () => {
        pingTimerRef.current && clearInterval(pingTimerRef.current);
        setStatus('closed');

        if (retryCountRef.current < maxRetries) {
          retryCountRef.current += 1;
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current - 1), 30000);
          timerRef.current = setTimeout(connect, delay);
        }
      };
    } catch {
      if (retryCountRef.current < maxRetries) {
        retryCountRef.current += 1;
        timerRef.current = setTimeout(connect, 2000);
      }
    }
  }, [url, enabled, maxRetries, onMessage, cleanup]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return cleanup;
  }, [connect, cleanup, enabled]);

  return { status, reconnect: connect };
}
