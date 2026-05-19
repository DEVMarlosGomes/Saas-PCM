import { useState, useEffect, useRef, useCallback } from 'react';
import { Bell } from 'lucide-react';
import { getNotificacoes, countNotificacoes, marcarLida, marcarTodasLidas } from '../../lib/api';

const TIPO_ICON = {
  revisao_pendente: '🔍',
  os_revisada: '✅',
  os_fechada: '🔒',
};

function timeAgo(dateStr) {
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return 'agora';
  if (diff < 3600) return `${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export default function NotificacoesDropdown() {
  const [open, setOpen] = useState(false);
  const [notifs, setNotifs] = useState([]);
  const [count, setCount] = useState(0);
  const ref = useRef(null);

  const fetchCount = useCallback(async () => {
    try {
      const { data } = await countNotificacoes();
      setCount(data.nao_lidas ?? 0);
    } catch {}
  }, []);

  const fetchNotifs = useCallback(async () => {
    try {
      const { data } = await getNotificacoes({ limit: 20 });
      setNotifs(data);
    } catch {}
  }, []);

  useEffect(() => {
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, [fetchCount]);

  useEffect(() => {
    if (open) fetchNotifs();
  }, [open, fetchNotifs]);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  async function handleMarkLida(id, e) {
    e.stopPropagation();
    await marcarLida(id);
    setNotifs((prev) => prev.map((n) => (n.id === id ? { ...n, lida: true } : n)));
    setCount((c) => Math.max(0, c - 1));
  }

  async function handleMarcarTodas() {
    await marcarTodasLidas();
    setNotifs((prev) => prev.map((n) => ({ ...n, lida: true })));
    setCount(0);
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          position: 'relative',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--aurix-text-secondary, #94A3B8)',
          padding: '6px',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          transition: 'color 0.2s',
        }}
        title="Notificações"
      >
        <Bell size={20} />
        {count > 0 && (
          <span
            style={{
              position: 'absolute',
              top: 2,
              right: 2,
              background: '#E53E3E',
              color: '#fff',
              fontSize: '10px',
              fontWeight: 700,
              borderRadius: '99px',
              minWidth: '16px',
              height: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 3px',
              lineHeight: 1,
            }}
          >
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 8px)',
            width: 340,
            background: 'var(--aurix-bg-card, #0D1626)',
            border: '1px solid var(--aurix-border, rgba(255,255,255,0.08))',
            borderRadius: '12px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderBottom: '1px solid var(--aurix-border, rgba(255,255,255,0.08))',
            }}
          >
            <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--aurix-text-primary, #E2E8F0)' }}>
              Notificações
            </span>
            {count > 0 && (
              <button
                onClick={handleMarcarTodas}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px',
                  color: 'var(--aurix-blue-primary, #1A6FE8)',
                }}
              >
                Marcar todas como lidas
              </button>
            )}
          </div>

          {/* List */}
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            {notifs.length === 0 ? (
              <div
                style={{
                  padding: '32px 16px',
                  textAlign: 'center',
                  color: 'var(--aurix-text-muted, #64748B)',
                  fontSize: '13px',
                }}
              >
                Nenhuma notificação
              </div>
            ) : (
              notifs.map((n) => (
                <div
                  key={n.id}
                  style={{
                    display: 'flex',
                    gap: '10px',
                    padding: '12px 16px',
                    borderBottom: '1px solid var(--aurix-border, rgba(255,255,255,0.05))',
                    background: n.lida ? 'transparent' : 'rgba(26,111,232,0.06)',
                    cursor: 'default',
                  }}
                >
                  <span style={{ fontSize: '18px', flexShrink: 0, marginTop: 1 }}>
                    {TIPO_ICON[n.tipo] ?? '🔔'}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontWeight: n.lida ? 400 : 600,
                        fontSize: '13px',
                        color: 'var(--aurix-text-primary, #E2E8F0)',
                        marginBottom: 2,
                      }}
                    >
                      {n.titulo}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--aurix-text-muted, #64748B)', lineHeight: 1.4 }}>
                      {n.mensagem}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--aurix-text-muted, #64748B)', marginTop: 4 }}>
                      {timeAgo(n.criada_em)}
                    </div>
                  </div>
                  {!n.lida && (
                    <button
                      onClick={(e) => handleMarkLida(n.id, e)}
                      title="Marcar como lida"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--aurix-blue-primary, #1A6FE8)',
                        fontSize: '18px',
                        flexShrink: 0,
                        alignSelf: 'flex-start',
                      }}
                    >
                      ·
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
