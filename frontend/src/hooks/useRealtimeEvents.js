/**
 * Hook de Server-Sent Events para tempo real por tenant.
 *
 * Autenticação via token JWT no query param (SSE não suporta headers).
 * O servidor valida o JWT no handshake e recusa conexão inválida.
 * Cada org recebe apenas seus próprios eventos — isolamento garantido no backend.
 *
 * Uso:
 *   const { connected } = useRealtimeEvents({
 *     onOsStatusChanged: (data) => { ... },
 *     onNotificacaoNova: (data) => { ... },
 *     onEstoqueAlerta: (data) => { ... },
 *   });
 */
import { useEffect, useRef, useState, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const TOKEN_KEY = 'aurix_token';
const RECONNECT_DELAY_MS = 5000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function useRealtimeEvents({
  onOsStatusChanged,
  onNotificacaoNova,
  onEstoqueAlerta,
  enabled = true,
} = {}) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef(null);
  const attemptsRef = useRef(0);
  const timerRef = useRef(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token || !enabled) return;

    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const url = `${API}/api/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      attemptsRef.current = 0;
    };

    es.onmessage = (e) => {
      if (!e.data || e.data.trim() === '') return;
      try {
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case 'os_status_changed':
            onOsStatusChanged?.(msg.data);
            break;
          case 'notificacao_nova':
            onNotificacaoNova?.(msg.data);
            break;
          case 'estoque_alerta':
            onEstoqueAlerta?.(msg.data);
            break;
          default:
            break;
        }
      } catch {
        // Mensagem malformada — ignora
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
      esRef.current = null;

      // Reconexão com backoff — para se token expirou ou muitos erros
      if (attemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        attemptsRef.current += 1;
        const delay = RECONNECT_DELAY_MS * Math.min(attemptsRef.current, 4);
        timerRef.current = setTimeout(connect, delay);
      }
    };
  }, [enabled, onOsStatusChanged, onNotificacaoNova, onEstoqueAlerta]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(timerRef.current);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);

  return { connected };
}
