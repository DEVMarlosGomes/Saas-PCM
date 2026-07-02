/**
 * Contexto SSE centralizado — um único EventSource por sessão de aba.
 *
 * Componentes assinam callbacks via RealtimeContext.
 * O token é re-lido do localStorage a cada reconexão, então funciona após
 * login/logout sem precisar re-montar o provider.
 */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useAuth } from './AuthContext';

const RealtimeContext = createContext({
  connected: false,
  subscribe: () => () => {},
});

const API = process.env.REACT_APP_BACKEND_URL || '';
const TOKEN_KEY = 'aurix_token';
const RECONNECT_MS = 5000;

export function RealtimeProvider({ children }) {
  const { user } = useAuth();
  const [connected, setConnected] = useState(false);
  const listenersRef = useRef({});       // {eventType: Set<fn>}
  const esRef = useRef(null);
  const timerRef = useRef(null);
  const attemptsRef = useRef(0);

  const dispatch = useCallback((type, data) => {
    const fns = listenersRef.current[type];
    if (fns) fns.forEach(fn => { try { fn(data); } catch {} });
  }, []);

  const connect = useCallback(() => {
    if (!user) return;
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;

    if (esRef.current) { esRef.current.close(); esRef.current = null; }

    const es = new EventSource(`${API}/api/events?token=${encodeURIComponent(token)}`);
    esRef.current = es;

    es.onopen = () => { setConnected(true); attemptsRef.current = 0; };

    es.onmessage = (e) => {
      if (!e.data?.trim()) return;
      try {
        const msg = JSON.parse(e.data);
        if (msg.type) dispatch(msg.type, msg.data);
      } catch {}
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
      esRef.current = null;
      if (attemptsRef.current < 8) {
        attemptsRef.current += 1;
        const delay = RECONNECT_MS * Math.min(attemptsRef.current, 4);
        timerRef.current = setTimeout(connect, delay);
      }
    };
  }, [user, dispatch]);

  useEffect(() => {
    if (user) {
      attemptsRef.current = 0;
      connect();
    } else {
      clearTimeout(timerRef.current);
      esRef.current?.close();
      esRef.current = null;
      setConnected(false);
    }
    return () => {
      clearTimeout(timerRef.current);
      esRef.current?.close();
    };
  }, [user, connect]);

  const subscribe = useCallback((eventType, fn) => {
    if (!listenersRef.current[eventType]) listenersRef.current[eventType] = new Set();
    listenersRef.current[eventType].add(fn);
    return () => listenersRef.current[eventType]?.delete(fn);
  }, []);

  return (
    <RealtimeContext.Provider value={{ connected, subscribe }}>
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime() {
  return useContext(RealtimeContext);
}
