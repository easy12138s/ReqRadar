import { createContext, useContext, type ReactNode } from 'react';
import { useSessionWebSocket, type UseSessionWebSocketOptions } from '@/hooks/useSessionWebSocket';

interface WsContextValue {
  connected: boolean;
  reconnecting: boolean;
  error: string | null;
}

const WsContext = createContext<WsContextValue>({ connected: false, reconnecting: false, error: null });

export function WsProvider({ children, ...opts }: { children: ReactNode } & UseSessionWebSocketOptions) {
  const { state } = useSessionWebSocket(opts);
  return <WsContext.Provider value={state}>{children}</WsContext.Provider>;
}

export function useWs(): WsContextValue {
  return useContext(WsContext);
}
