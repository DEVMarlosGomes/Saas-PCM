import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useRealtime } from "../contexts/RealtimeContext";
import { getKanban, updateOrdemServico, patchOcorrencia } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Kanban, Lock, Loader2, RefreshCw, Clock, Repeat2, Timer, Zap,
  MessageSquare, MapPin, Hash, User, X, Send, Package,
} from "lucide-react";
import { Button } from "../components/ui/button";

// ─── constants ───────────────────────────────────────────────────────────────

const PRIORIDADE_CONFIG = {
  critica: { label: "Crítica", color: "#EF4444", bg: "rgba(239,68,68,0.12)" },
  alta:    { label: "Alta",    color: "#F97316", bg: "rgba(249,115,22,0.12)" },
  media:   { label: "Média",   color: "#EAB308", bg: "rgba(234,179,8,0.12)" },
  baixa:   { label: "Baixa",   color: "#10B981", bg: "rgba(16,185,129,0.12)" },
};

const TIPO_CONFIG = {
  corretiva:  { label: "C",  color: "#EF4444" },
  preventiva: { label: "P",  color: "#10B981" },
  preditiva:  { label: "Pd", color: "#8B5CF6" },
};

const GRUPO_COLORS = {
  eletrico:   { color: "#F59E0B", bg: "rgba(245,158,11,0.12)" },
  elétrico:   { color: "#F59E0B", bg: "rgba(245,158,11,0.12)" },
  hidraulico: { color: "#3B82F6", bg: "rgba(59,130,246,0.12)" },
  hidráulico: { color: "#3B82F6", bg: "rgba(59,130,246,0.12)" },
  mecanico:   { color: "#8B5CF6", bg: "rgba(139,92,246,0.12)" },
  mecânico:   { color: "#8B5CF6", bg: "rgba(139,92,246,0.12)" },
};

const FAILURE_GROUP_COLORS = {
  eletrico:       { color: "#3B82F6", bg: "rgba(59,130,246,0.12)" },
  elétrico:       { color: "#3B82F6", bg: "rgba(59,130,246,0.12)" },
  hidraulico:     { color: "#F59E0B", bg: "rgba(245,158,11,0.12)" },
  hidráulico:     { color: "#F59E0B", bg: "rgba(245,158,11,0.12)" },
  mecanico:       { color: "#6B7280", bg: "rgba(107,114,128,0.12)" },
  mecânico:       { color: "#6B7280", bg: "rgba(107,114,128,0.12)" },
  pneumatico:     { color: "#0D9488", bg: "rgba(13,148,136,0.12)" },
  pneumático:     { color: "#0D9488", bg: "rgba(13,148,136,0.12)" },
  instrumentacao: { color: "#8B5CF6", bg: "rgba(139,92,246,0.12)" },
  instrumentação: { color: "#8B5CF6", bg: "rgba(139,92,246,0.12)" },
  estrutural:     { color: "#FB923C", bg: "rgba(251,146,60,0.12)" },
};

// Status transitions allowed from each status
const VALID_TRANSITIONS = {
  aberta:             ["em_atendimento"],
  em_atendimento:     ["aguardando_peca", "aguardando_revisao"],
  aguardando_peca:    ["em_atendimento"],
  aguardando_revisao: ["revisada"],
  revisada:           ["fechada"],
};

// SLA thresholds (minutes) by priority
const SLA_MINUTOS = { critica: 15, alta: 30, media: 120, baixa: 480 };

function fmtMin(min) {
  if (min == null) return "—";
  if (min < 60) return `${min}min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}h${m}min` : `${h}h`;
}

function elapsedMin(iso) {
  if (!iso) return 0;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000 / 3600;
  if (diff < 1) return "< 1h";
  if (diff < 24) return `${Math.floor(diff)}h`;
  return `${Math.floor(diff / 24)}d`;
}

// ─── UpgradeGate ─────────────────────────────────────────────────────────────

function UpgradeGate() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-5 text-center">
      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
        <Lock className="h-7 w-7 text-primary" />
      </div>
      <div className="max-w-sm space-y-1.5">
        <h2 className="font-heading text-xl font-bold">Kanban de OS</h2>
        <p className="text-muted-foreground text-sm">
          O board Kanban está disponível a partir do plano{" "}
          <strong className="text-foreground">Profissional</strong>.
        </p>
      </div>
      <Button onClick={() => navigate("/billing")} className="rounded-lg shadow-lg shadow-primary/20">
        Ver planos
      </Button>
    </div>
  );
}

// ─── OccurrenceModal ─────────────────────────────────────────────────────────

function OccurrenceModal({ card, onClose, onSubmit }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const textareaRef = useRef(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    const ok = await onSubmit(card.id, text.trim());
    setLoading(false);
    if (ok) onClose();
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.65)", backdropFilter: "blur(3px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--aurix-bg-card, #0D1626)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 14, padding: "24px 22px",
          width: "100%", maxWidth: 420,
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
          <div>
            <p style={{ fontSize: 15, fontWeight: 700, color: "rgba(255,255,255,0.9)", margin: 0 }}>
              Registrar Ocorrência
            </p>
            <p style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", margin: "3px 0 0" }}>
              OS #{card.numero} · {card.equipamento}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none", border: "none", cursor: "pointer",
              color: "rgba(255,255,255,0.4)", padding: 4, lineHeight: 0,
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Existing occurrences count */}
        {card.occurrences_count > 0 && (
          <div style={{
            fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 12,
            padding: "6px 10px", background: "rgba(255,255,255,0.04)",
            borderRadius: 6, display: "flex", alignItems: "center", gap: 5,
          }}>
            <MessageSquare size={10} />
            {card.occurrences_count} ocorrência{card.occurrences_count !== 1 ? "s" : ""} registrada{card.occurrences_count !== 1 ? "s" : ""}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <textarea
            ref={textareaRef}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Descreva a ocorrência observada..."
            rows={4}
            style={{
              width: "100%", borderRadius: 8, resize: "vertical",
              background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.9)", padding: "10px 12px", fontSize: 13,
              outline: "none", fontFamily: "inherit", lineHeight: 1.5,
              boxSizing: "border-box",
            }}
          />
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.12)",
                background: "transparent", color: "rgba(255,255,255,0.5)",
                fontSize: 13, cursor: "pointer", fontWeight: 600,
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading || !text.trim()}
              style={{
                padding: "8px 16px", borderRadius: 8, border: "none",
                background: loading || !text.trim() ? "rgba(26,111,232,0.4)" : "#1A6FE8",
                color: "#fff", fontSize: 13, cursor: loading || !text.trim() ? "not-allowed" : "pointer",
                fontWeight: 700, display: "flex", alignItems: "center", gap: 6,
              }}
            >
              <Send size={13} />
              {loading ? "Salvando..." : "Registrar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── KanbanCard ──────────────────────────────────────────────────────────────

function KanbanCard({ card, onDragStart, canDrag, onOccurrence, canOccurrence }) {
  const prio = PRIORIDADE_CONFIG[card.prioridade] || PRIORIDADE_CONFIG.media;
  const tipo = TIPO_CONFIG[card.tipo] || TIPO_CONFIG.corretiva;

  // Single tick forces re-render every 30s for all live timers
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 30000);
    return () => clearInterval(id);
  }, []);

  // Live time values (recalculated on each render tick)
  const slaLimit = SLA_MINUTOS[card.prioridade] ?? 120;
  const slaElapsed = elapsedMin(card.created_at);
  const slaRatio = Math.min(1, slaElapsed / slaLimit);
  const slaBarColor = slaRatio >= 1 ? "#EF4444" : slaRatio >= 0.75 ? "#F97316" : "#10B981";
  const liveDowntime = elapsedMin(card.downtime_start);

  // Response time badge
  const isAberta = card.tempo_resposta == null;
  let responseLabel, responseColor, responseBg, ResponseIcon;
  if (isAberta) {
    const ratio = slaElapsed / slaLimit;
    responseLabel = `Aguardando ${fmtMin(slaElapsed)}`;
    responseColor = ratio >= 1 ? "#EF4444" : ratio >= 0.75 ? "#F97316" : "#EAB308";
    responseBg = ratio >= 1 ? "rgba(239,68,68,0.12)" : ratio >= 0.75 ? "rgba(249,115,22,0.12)" : "rgba(234,179,8,0.10)";
    ResponseIcon = Timer;
  } else {
    responseLabel = `Resp: ${fmtMin(card.tempo_resposta)}`;
    responseColor = card.dentro_sla !== false ? "#10B981" : "#EF4444";
    responseBg = card.dentro_sla !== false ? "rgba(16,185,129,0.10)" : "rgba(239,68,68,0.12)";
    ResponseIcon = Zap;
  }

  // Equipment group badge
  const grupoKey = (card.grupo_nome || "").toLowerCase();
  const grupoStyle = GRUPO_COLORS[grupoKey] || { color: "#64748B", bg: "rgba(100,116,139,0.12)" };

  // Failure group badge
  const fgKey = (card.failure_group || "").toLowerCase();
  const fgStyle = FAILURE_GROUP_COLORS[fgKey];

  const showDowntimeTimer = card.downtime_start != null;
  const showAbertaTimer = card.status === "aberta";

  return (
    <div
      draggable={canDrag}
      onDragStart={(e) => {
        if (!canDrag) return;
        e.dataTransfer.effectAllowed = "move";
        onDragStart(card.id);
      }}
      style={{
        background: "var(--aurix-bg-card, #0D1626)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderLeft: `3px solid ${prio.color}`,
        borderRadius: "10px",
        padding: "12px 14px",
        cursor: canDrag ? "grab" : "default",
        userSelect: "none",
        transition: "box-shadow 0.15s, transform 0.15s",
        marginBottom: "8px",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.3)";
        if (canDrag) e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.transform = "none";
      }}
    >
      {/* Header row: numero + failure_group + tipo + prioridade */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7, flexWrap: "wrap", gap: 4 }}>
        <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>
          #{card.numero}
        </span>
        <div style={{ display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
          {card.failure_group && fgStyle ? (
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 4,
              background: fgStyle.bg, color: fgStyle.color,
              textTransform: "uppercase", letterSpacing: "0.04em",
            }}>
              {card.failure_group}
            </span>
          ) : card.grupo_nome ? (
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 4,
              background: grupoStyle.bg, color: grupoStyle.color,
              textTransform: "uppercase", letterSpacing: "0.04em",
            }}>
              {card.grupo_nome}
            </span>
          ) : null}
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 4,
            background: tipo.color + "22", color: tipo.color,
          }}>{tipo.label}</span>
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 4,
            background: prio.bg, color: prio.color,
          }}>{prio.label}</span>
        </div>
      </div>

      {/* Equipment name */}
      <p style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.9)", marginBottom: 2, lineHeight: 1.3 }}>
        {card.equipamento}
      </p>

      {/* Equipment code + localizacao */}
      {(card.equipamento_codigo || card.equipamento_localizacao) && (
        <p style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginBottom: 6, fontFamily: "monospace", display: "flex", alignItems: "center", gap: 4 }}>
          {card.equipamento_codigo && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <Hash size={9} />{card.equipamento_codigo}
            </span>
          )}
          {card.equipamento_codigo && card.equipamento_localizacao && <span>·</span>}
          {card.equipamento_localizacao && (
            <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <MapPin size={9} />{card.equipamento_localizacao}
            </span>
          )}
        </p>
      )}

      {/* Description */}
      {card.descricao && (
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", lineHeight: 1.4, marginBottom: 8 }}>
          {card.descricao}
        </p>
      )}

      {/* SLA progress bar */}
      <div style={{
        height: 3, borderRadius: 2, background: "rgba(255,255,255,0.07)", marginBottom: 8, overflow: "hidden",
      }}>
        <div style={{
          height: "100%", borderRadius: 2,
          width: `${slaRatio * 100}%`,
          background: slaBarColor,
          transition: "width 1s linear",
        }} />
      </div>

      {/* Em aberto timer (status: aberta) */}
      {showAbertaTimer && (
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          fontSize: 10, color: "#3B82F6", marginBottom: 8,
          padding: "2px 7px", background: "rgba(59,130,246,0.1)",
          border: "1px solid rgba(59,130,246,0.2)", borderRadius: 4,
        }}>
          <Clock size={9} />
          <span>Em aberto: {fmtMin(slaElapsed)}</span>
        </div>
      )}

      {/* Em manutenção timer (downtime_start) */}
      {showDowntimeTimer && (
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          fontSize: 10, color: "#F97316", marginBottom: 8,
          padding: "2px 7px", background: "rgba(249,115,22,0.1)",
          border: "1px solid rgba(249,115,22,0.2)", borderRadius: 4,
        }}>
          <Package size={9} />
          <span>Em manutenção: {fmtMin(liveDowntime)}</span>
        </div>
      )}

      {/* Response time badge with SLA limit */}
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        padding: "3px 8px", borderRadius: 6, marginBottom: 8,
        background: responseBg, border: `1px solid ${responseColor}33`,
      }}>
        <ResponseIcon size={10} style={{ color: responseColor, flexShrink: 0 }} />
        <span style={{ fontSize: 10, fontWeight: 700, color: responseColor, letterSpacing: "0.01em" }}>
          {responseLabel}
        </span>
        <span style={{ fontSize: 9, color: "rgba(255,255,255,0.25)", marginLeft: 2 }}>
          [SLA: {fmtMin(slaLimit)}]
        </span>
        {!isAberta && card.dentro_sla === false && (
          <span style={{ fontSize: 9, color: "#EF4444", fontWeight: 700, marginLeft: 2 }}>· Fora do SLA</span>
        )}
        {!isAberta && card.dentro_sla !== false && (
          <span style={{ fontSize: 9, color: "#10B981", fontWeight: 700, marginLeft: 2 }}>· No SLA</span>
        )}
      </div>

      {/* Footer: solicitante, tecnico, meta */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {card.solicitante && (
          <span style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", display: "flex", alignItems: "center", gap: 4 }}>
            <User size={9} style={{ flexShrink: 0 }} />
            {card.solicitante}
          </span>
        )}
        {card.tecnico && (
          <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{
              width: 14, height: 14, borderRadius: "50%",
              background: "#1A6FE822", border: "1px solid #1A6FE866",
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              fontSize: 8, color: "#2E90FA", fontWeight: 700, flexShrink: 0,
            }}>
              {card.tecnico[0]}
            </span>
            {card.tecnico}
            {card.tecnico_employee_id && (
              <span style={{ color: "rgba(255,255,255,0.25)", fontFamily: "monospace" }}>
                #{card.tecnico_employee_id}
              </span>
            )}
          </span>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
          {/* Occurrence button (operador only) or count badge */}
          {canOccurrence ? (
            <button
              onClick={(e) => { e.stopPropagation(); onOccurrence(card); }}
              title="Adicionar ocorrência"
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "2px 7px", borderRadius: 5, cursor: "pointer",
                background: (card.occurrences_count ?? 0) > 0
                  ? "rgba(139,92,246,0.15)" : "rgba(255,255,255,0.05)",
                border: (card.occurrences_count ?? 0) > 0
                  ? "1px solid rgba(139,92,246,0.3)" : "1px solid rgba(255,255,255,0.08)",
                color: (card.occurrences_count ?? 0) > 0 ? "#8B5CF6" : "rgba(255,255,255,0.3)",
                fontSize: 10, fontWeight: 600,
              }}
            >
              <MessageSquare size={9} />
              {card.occurrences_count ?? 0}
            </button>
          ) : (card.occurrences_count ?? 0) > 0 ? (
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 4,
              padding: "2px 7px", borderRadius: 5,
              background: "rgba(139,92,246,0.15)",
              border: "1px solid rgba(139,92,246,0.3)",
              color: "#8B5CF6", fontSize: 10, fontWeight: 600,
            }}>
              <MessageSquare size={9} />
              {card.occurrences_count}
            </span>
          ) : null}

          {/* Created at */}
          {card.created_at && (
            <span style={{
              fontSize: 10, color: "rgba(255,255,255,0.3)",
              marginLeft: "auto", display: "flex", alignItems: "center", gap: 3,
            }}>
              <Clock size={9} />
              {timeAgo(card.created_at)}
            </span>
          )}

          {/* Reincidente */}
          {card.reincidente && (
            <span title="Reincidente" style={{ color: "#F97316" }}><Repeat2 size={11} /></span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── KanbanColumn ─────────────────────────────────────────────────────────────

function KanbanColumn({ column, onDrop, dragOverCol, onDragOver, onDragLeave, onDragStart, canDrag, onOccurrence, canOccurrence }) {
  const isOver = dragOverCol === column.id;

  const COL_COLORS = {
    aberta:             "#3B82F6",
    em_atendimento:     "#F59E0B",
    aguardando_peca:    "#F97316",
    aguardando_revisao: "#8B5CF6",
    revisada:           "#10B981",
  };
  const accent = COL_COLORS[column.id] || "#64748B";

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); onDragOver(column.id); }}
      onDragLeave={onDragLeave}
      onDrop={(e) => { e.preventDefault(); onDrop(column.id); }}
      style={{
        minWidth: 250,
        flex: "1 1 250px",
        maxWidth: 310,
        display: "flex",
        flexDirection: "column",
        background: isOver ? "rgba(26,111,232,0.05)" : "transparent",
        border: isOver ? "1px dashed rgba(26,111,232,0.4)" : "1px solid transparent",
        borderRadius: 12,
        transition: "all 0.15s",
        padding: 2,
      }}
    >
      {/* Column header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px 10px 12px", marginBottom: 8,
        borderBottom: `2px solid ${accent}33`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: accent, display: "inline-block" }} />
          <span style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.8)", letterSpacing: "0.02em" }}>
            {column.label.toUpperCase()}
          </span>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 99,
          background: accent + "22", color: accent,
        }}>
          {column.cards.length}
        </span>
      </div>

      {/* Cards */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 2px 8px 2px", minHeight: 80 }}>
        {column.cards.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "24px 16px",
            color: "rgba(255,255,255,0.2)", fontSize: 12, borderRadius: 8,
            border: "1px dashed rgba(255,255,255,0.08)",
          }}>
            Sem OS
          </div>
        ) : column.cards.map(card => (
          <KanbanCard
            key={card.id}
            card={card}
            onDragStart={onDragStart}
            canDrag={canDrag}
            onOccurrence={onOccurrence}
            canOccurrence={canOccurrence}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function KanbanPage() {
  const { user } = useAuth();
  const { subscribe } = useRealtime();
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [dragCardId, setDragCardId] = useState(null);
  const [dragOverCol, setDragOverCol] = useState(null);
  const [moving, setMoving] = useState(false);
  const [occurrenceModal, setOccurrenceModal] = useState(null); // { card }
  const dragLeaveTimer = useRef(null);

  const canDrag = user?.role !== "operador";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getKanban();
      setColumns(data.columns);
    } catch (err) {
      if (err.response?.status === 403) setLocked(true);
      else toast.error("Erro ao carregar Kanban");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.features?.kanban === false) { setLocked(true); setLoading(false); return; }
    load();
  }, [load, user]);

  // SSE: recarrega kanban quando qualquer OS muda de status (evento os_status_changed)
  useEffect(() => {
    const unsub = subscribe('os_status_changed', () => {
      // Reload silencioso — não mostra loading spinner
      getKanban().then(({ data }) => setColumns(data.columns)).catch(() => {});
    });
    return unsub;
  }, [subscribe]);

  // ── occurrence handler ──

  const handleOccurrence = useCallback((card) => {
    setOccurrenceModal({ card });
  }, []);

  const handleOccurrenceSubmit = useCallback(async (osId, descricao) => {
    try {
      await patchOcorrencia(osId, descricao);
      toast.success("Ocorrência registrada");
      load();
      return true;
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao registrar ocorrência");
      return false;
    }
  }, [load]);

  // ── drag handlers ──

  function handleDragStart(cardId) {
    if (!canDrag) return;
    setDragCardId(cardId);
  }

  function handleDragOver(colId) {
    if (!canDrag) return;
    clearTimeout(dragLeaveTimer.current);
    setDragOverCol(colId);
  }

  function handleDragLeave() {
    dragLeaveTimer.current = setTimeout(() => setDragOverCol(null), 80);
  }

  async function handleDrop(targetColId) {
    setDragOverCol(null);
    if (!dragCardId || !canDrag) return;

    let sourceColId = null;
    let card = null;
    for (const col of columns) {
      const found = col.cards.find(c => c.id === dragCardId);
      if (found) { sourceColId = col.id; card = found; break; }
    }

    if (!card || sourceColId === targetColId) { setDragCardId(null); return; }

    const allowed = VALID_TRANSITIONS[sourceColId] || [];
    if (!allowed.includes(targetColId)) {
      toast.warning(`Transição ${sourceColId} → ${targetColId} não permitida`);
      setDragCardId(null);
      return;
    }

    setMoving(true);
    setColumns(prev => prev.map(col => {
      if (col.id === sourceColId) return { ...col, cards: col.cards.filter(c => c.id !== dragCardId) };
      if (col.id === targetColId) return { ...col, cards: [{ ...card }, ...col.cards] };
      return col;
    }));

    try {
      await updateOrdemServico(dragCardId, { status: targetColId });
      toast.success(`OS #${card.numero} → "${targetColId.replace(/_/g, " ")}"`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao mover OS");
      load();
    } finally {
      setMoving(false);
      setDragCardId(null);
    }
  }

  if (locked) return <UpgradeGate />;

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-7 w-7 animate-spin text-primary" />
      </div>
    );
  }

  const total = columns.reduce((s, c) => s + c.cards.length, 0);

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 112px)", gap: 16 }}
        data-testid="kanban-page">
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Kanban className="h-6 w-6 text-primary" />
            <div>
              <h1 className="font-heading text-2xl font-bold">Kanban de OS</h1>
              <p className="text-muted-foreground text-sm">
                {total} ordem{total !== 1 ? "s" : ""} ativa{total !== 1 ? "s" : ""}
                {canDrag ? " · Arraste para mover entre colunas" : " · Visualização (somente leitura)"}
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={moving} className="h-9 gap-2">
            <RefreshCw className={`h-3.5 w-3.5 ${moving ? "animate-spin" : ""}`} />
            Atualizar
          </Button>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: 16, flexShrink: 0, flexWrap: "wrap", alignItems: "center" }}>
          {Object.entries(PRIORIDADE_CONFIG).map(([k, v]) => (
            <span key={k} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "rgba(255,255,255,0.5)" }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: v.color }} />
              {v.label}
            </span>
          ))}
          <span style={{ width: 1, height: 14, background: "rgba(255,255,255,0.1)", margin: "0 4px" }} />
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
            <Timer size={10} style={{ color: "#EAB308" }} /> Aguardando (aberta)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
            <Zap size={10} style={{ color: "#10B981" }} /> Tempo de resposta
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
            <Package size={10} style={{ color: "#F97316" }} /> Parado (downtime)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
            <Repeat2 size={10} style={{ color: "#F97316" }} /> Reincidente
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
            <MessageSquare size={10} style={{ color: "#8B5CF6" }} /> Ocorrências
          </span>
        </div>

        {/* Board */}
        <div style={{
          display: "flex", gap: 12, flex: 1, overflowX: "auto", overflowY: "hidden",
          paddingBottom: 8,
        }}>
          {columns.map(col => (
            <KanbanColumn
              key={col.id}
              column={col}
              onDrop={handleDrop}
              dragOverCol={dragOverCol}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDragStart={handleDragStart}
              canDrag={canDrag}
              onOccurrence={handleOccurrence}
              canOccurrence={user?.role === "operador"}
            />
          ))}
        </div>
      </div>

      {/* Occurrence modal */}
      {occurrenceModal && (
        <OccurrenceModal
          card={occurrenceModal.card}
          onClose={() => setOccurrenceModal(null)}
          onSubmit={handleOccurrenceSubmit}
        />
      )}
    </>
  );
}
