import { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getKanban, updateOrdemServico } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Kanban, Lock, Loader2, AlertTriangle, RefreshCw, Clock, Repeat2, Timer, Zap,
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

// Status transitions allowed from each status
const VALID_TRANSITIONS = {
  aberta:             ["em_atendimento"],
  em_atendimento:     ["aguardando_revisao"],
  aguardando_revisao: ["revisada"],
  revisada:           ["fechada"],
};

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

// SLA thresholds (minutes) by priority
const SLA_MINUTOS = { critica: 15, alta: 30, media: 120, baixa: 480 };

// Convert minutes to readable string
function fmtMin(min) {
  if (min == null) return "—";
  if (min < 60) return `${min}min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}h${m}min` : `${h}h`;
}

// Time elapsed since an ISO string, in minutes
function elapsedMin(iso) {
  if (!iso) return 0;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
}

// ─── KanbanCard ──────────────────────────────────────────────────────────────

function KanbanCard({ card, onDragStart }) {
  const prio = PRIORIDADE_CONFIG[card.prioridade] || PRIORIDADE_CONFIG.media;
  const tipo = TIPO_CONFIG[card.tipo] || TIPO_CONFIG.corretiva;

  function timeAgo(iso) {
    if (!iso) return "";
    const diff = (Date.now() - new Date(iso).getTime()) / 1000 / 3600;
    if (diff < 1) return "< 1h";
    if (diff < 24) return `${Math.floor(diff)}h`;
    return `${Math.floor(diff / 24)}d`;
  }

  // ── Response time badge ──────────────────────────────────────────────────
  // cards still "aberta": show waiting time + SLA pressure color
  // cards already attended: show actual tempo_resposta + SLA result color
  const isAberta = card.tempo_resposta == null;
  const slaSecs = SLA_MINUTOS[card.prioridade] ?? 120;

  let responseLabel, responseColor, responseBg, ResponseIcon;

  if (isAberta) {
    // Still waiting — show elapsed time since creation
    const waitMin = elapsedMin(card.created_at);
    const ratio = waitMin / slaSecs;
    responseLabel = `Aguardando ${fmtMin(waitMin)}`;
    if (ratio >= 1) {
      responseColor = "#EF4444"; responseBg = "rgba(239,68,68,0.12)";
    } else if (ratio >= 0.75) {
      responseColor = "#F97316"; responseBg = "rgba(249,115,22,0.12)";
    } else {
      responseColor = "#EAB308"; responseBg = "rgba(234,179,8,0.10)";
    }
    ResponseIcon = Timer;
  } else {
    // Attended — show actual response time
    responseLabel = `Resp: ${fmtMin(card.tempo_resposta)}`;
    if (card.dentro_sla !== false) {
      responseColor = "#10B981"; responseBg = "rgba(16,185,129,0.10)";
    } else {
      responseColor = "#EF4444"; responseBg = "rgba(239,68,68,0.12)";
    }
    ResponseIcon = Zap;
  }

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        onDragStart(card.id);
      }}
      style={{
        background: "var(--aurix-bg-card, #0D1626)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderLeft: `3px solid ${prio.color}`,
        borderRadius: "10px",
        padding: "12px 14px",
        cursor: "grab",
        userSelect: "none",
        transition: "box-shadow 0.15s, transform 0.15s",
        marginBottom: "8px",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,0,0,0.3)";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.transform = "none";
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>
          #{card.numero}
        </span>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
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

      {/* Equipment */}
      <p style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.9)", marginBottom: 4, lineHeight: 1.3 }}>
        {card.equipamento}
      </p>

      {/* Description */}
      {card.descricao && (
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", lineHeight: 1.4, marginBottom: 8 }}>
          {card.descricao}
        </p>
      )}

      {/* Response time badge */}
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        padding: "3px 8px", borderRadius: 6, marginBottom: 8,
        background: responseBg,
        border: `1px solid ${responseColor}33`,
      }}>
        <ResponseIcon size={10} style={{ color: responseColor, flexShrink: 0 }} />
        <span style={{ fontSize: 10, fontWeight: 700, color: responseColor, letterSpacing: "0.01em" }}>
          {responseLabel}
        </span>
        {!isAberta && card.dentro_sla === false && (
          <span style={{ fontSize: 9, color: "#EF4444", fontWeight: 700, marginLeft: 2 }}>· Fora do SLA</span>
        )}
        {!isAberta && card.dentro_sla !== false && (
          <span style={{ fontSize: 9, color: "#10B981", fontWeight: 700, marginLeft: 2 }}>· No SLA</span>
        )}
      </div>

      {/* Footer */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {card.tecnico && (
          <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 14, height: 14, borderRadius: "50%", background: "#1A6FE822", border: "1px solid #1A6FE866", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 8, color: "#2E90FA", fontWeight: 700 }}>
              {card.tecnico[0]}
            </span>
            {card.tecnico}
          </span>
        )}
        {card.created_at && (
          <span style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", marginLeft: "auto", display: "flex", alignItems: "center", gap: 3 }}>
            <Clock size={9} />
            {timeAgo(card.created_at)}
          </span>
        )}
        {card.reincidente && (
          <span title="Reincidente" style={{ color: "#F97316" }}><Repeat2 size={11} /></span>
        )}
      </div>
    </div>
  );
}

// ─── KanbanColumn ─────────────────────────────────────────────────────────────

function KanbanColumn({ column, onDrop, dragOverCol, onDragOver, onDragLeave, onDragStart }) {
  const isOver = dragOverCol === column.id;

  const COL_COLORS = {
    aberta:             "#3B82F6",
    em_atendimento:     "#F59E0B",
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
        minWidth: 260,
        flex: "1 1 260px",
        maxWidth: 320,
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
          <KanbanCard key={card.id} card={card} onDragStart={onDragStart} />
        ))}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function KanbanPage() {
  const { user } = useAuth();
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [dragCardId, setDragCardId] = useState(null);
  const [dragOverCol, setDragOverCol] = useState(null);
  const [moving, setMoving] = useState(false);
  const dragLeaveTimer = useRef(null);

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

  // ── drag handlers ──

  function handleDragStart(cardId) {
    setDragCardId(cardId);
  }

  function handleDragOver(colId) {
    clearTimeout(dragLeaveTimer.current);
    setDragOverCol(colId);
  }

  function handleDragLeave() {
    dragLeaveTimer.current = setTimeout(() => setDragOverCol(null), 80);
  }

  async function handleDrop(targetColId) {
    setDragOverCol(null);
    if (!dragCardId) return;

    // Find source column
    let sourceColId = null;
    let card = null;
    for (const col of columns) {
      const found = col.cards.find(c => c.id === dragCardId);
      if (found) { sourceColId = col.id; card = found; break; }
    }

    if (!card || sourceColId === targetColId) { setDragCardId(null); return; }

    // Validate transition
    const allowed = VALID_TRANSITIONS[sourceColId] || [];
    if (!allowed.includes(targetColId)) {
      toast.warning(`Transição ${sourceColId} → ${targetColId} não permitida`);
      setDragCardId(null);
      return;
    }

    setMoving(true);
    // Optimistic update
    setColumns(prev => prev.map(col => {
      if (col.id === sourceColId) return { ...col, cards: col.cards.filter(c => c.id !== dragCardId) };
      if (col.id === targetColId) return { ...col, cards: [{ ...card, prioridade: card.prioridade }, ...col.cards] };
      return col;
    }));

    try {
      await updateOrdemServico(dragCardId, { status: targetColId });
      toast.success(`OS #${card.numero} movida para "${targetColId.replace("_", " ")}"`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao mover OS");
      load(); // revert
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
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 112px)", gap: 16 }}
      data-testid="kanban-page">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Kanban className="h-6 w-6 text-primary" />
          <div>
            <h1 className="font-heading text-2xl font-bold">Kanban de OS</h1>
            <p className="text-muted-foreground text-sm">{total} ordem{total !== 1 ? "s" : ""} ativa{total !== 1 ? "s" : ""} · Arraste para mover entre colunas</p>
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
          <Repeat2 size={10} style={{ color: "#F97316" }} /> Reincidente
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
          />
        ))}
      </div>
    </div>
  );
}
