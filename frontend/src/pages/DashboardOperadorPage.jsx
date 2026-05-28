import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getDashboardOperador } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Activity, Clock, Wrench, BarChart2, Timer,
  Loader2, RefreshCw, AlertTriangle, CheckCircle2,
} from "lucide-react";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtMin(min) {
  if (min == null || min === 0) return "—";
  if (min < 60) return `${Math.round(min)}min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

function fmtHoras(h) {
  if (h == null || h === 0) return "—";
  if (h >= 1000) return `${Math.round(h / 24)}d`;
  return `${Math.round(h)}h`;
}

const STATUS_LABEL = {
  aberta: "Aberta", em_atendimento: "Em Atendimento",
  aguardando_peca: "Ag. Peça", aguardando_revisao: "Ag. Revisão", revisada: "Revisada",
};
const STATUS_COLOR = {
  aberta: "#3B82F6", em_atendimento: "#F59E0B",
  aguardando_peca: "#F97316", aguardando_revisao: "#8B5CF6", revisada: "#10B981",
};
const PRIO_COLOR = { critica: "#EF4444", alta: "#F97316", media: "#EAB308", baixa: "#10B981" };
const PRIO_LABEL = { critica: "Crítica", alta: "Alta", media: "Média", baixa: "Baixa" };

// ─── KPI card ────────────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, label, value, sub, color = "#3B82F6", alert = false }) {
  return (
    <div style={{
      background: "#171717", border: `1px solid ${alert ? "rgba(239,68,68,0.3)" : "#262626"}`,
      borderRadius: 4, padding: "20px 20px 16px",
      borderTop: `2px solid ${alert ? "#EF4444" : color}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          {label}
        </span>
        <div style={{
          width: 32, height: 32, borderRadius: 4,
          background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon size={16} style={{ color }} />
        </div>
      </div>
      <p style={{ fontSize: 28, fontWeight: 800, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginTop: 4 }}>{sub}</p>}
    </div>
  );
}

// ─── OS card compacto ─────────────────────────────────────────────────────────

function OSCard({ os }) {
  const status = STATUS_COLOR[os.status] || "#64748B";
  const prio = PRIO_COLOR[os.prioridade] || "#64748B";

  return (
    <div style={{
      padding: "12px 14px", borderRadius: 4,
      background: "#1A1A1A", border: "1px solid #262626",
      borderLeft: `3px solid ${prio}`,
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.35)" }}>
            #{os.numero}
          </span>
          {os.failure_group && (
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 2,
              background: "rgba(59,130,246,0.12)", color: "#60A5FA",
              textTransform: "uppercase", letterSpacing: "0.04em",
            }}>
              {os.failure_group}
            </span>
          )}
        </div>
        <p style={{ fontSize: 13, color: "#F8FAFC", fontWeight: 600, margin: 0, marginBottom: 2 }}>
          {os.descricao}
        </p>
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", margin: 0 }}>
          {new Date(os.created_at).toLocaleDateString("pt-BR")}
        </p>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
        <span style={{
          fontSize: 10, padding: "2px 8px", borderRadius: 2, whiteSpace: "nowrap",
          background: `${status}15`, color: status, fontWeight: 700,
        }}>
          {STATUS_LABEL[os.status] || os.status}
        </span>
        <span style={{
          fontSize: 10, padding: "2px 8px", borderRadius: 2,
          background: `${prio}12`, color: prio, fontWeight: 600,
        }}>
          {PRIO_LABEL[os.prioridade] || os.prioridade}
        </span>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function DashboardOperadorPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await getDashboardOperador();
      setData(res.data);
      setLastUpdate(new Date());
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error("Acesso negado. Este dashboard é exclusivo para operadores e técnicos.");
        navigate("/dashboard");
      } else if (err.response?.status === 400) {
        toast.error(err.response.data?.detail || "Configure seu setor no perfil para ver este dashboard.");
      } else {
        toast.error("Erro ao carregar dashboard");
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh a cada 60s
  useEffect(() => {
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 320 }}>
        <Loader2 size={28} style={{ animation: "spin 1s linear infinite", color: "#3B82F6" }} />
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!data) return null;

  const disp = data.disponibilidade_percent ?? 0;
  const dispAlert = disp < 85;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
            Dashboard do Operador
          </h1>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", margin: "2px 0 0" }}>
            Setor: <strong style={{ color: "#3B82F6" }}>{data.setor_nome || user?.setor || "—"}</strong>
            {lastUpdate && (
              <span style={{ marginLeft: 12, color: "rgba(255,255,255,0.25)" }}>
                · Atualizado às {lastUpdate.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); load(); }}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "8px 14px", borderRadius: 4, border: "1px solid #262626",
            background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.5)",
            cursor: "pointer", fontSize: 12, fontWeight: 600,
          }}
        >
          <RefreshCw size={13} />
          Atualizar
        </button>
      </div>

      {/* 5 KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        <KpiCard
          icon={Activity} label="Disponibilidade" color={dispAlert ? "#EF4444" : "#10B981"}
          value={`${disp.toFixed(1)}%`}
          sub={dispAlert ? "⚠ Abaixo de 85%" : "Equipamentos online"}
          alert={dispAlert}
        />
        <KpiCard
          icon={Wrench} label="MTTR" color="#F59E0B"
          value={fmtMin(data.mttr_minutos)}
          sub="Tempo médio de reparo"
        />
        <KpiCard
          icon={CheckCircle2} label="MTBF" color="#10B981"
          value={fmtHoras(data.mtbf_horas)}
          sub="Tempo médio entre falhas"
        />
        <KpiCard
          icon={BarChart2} label="OS do Mês" color="#3B82F6"
          value={data.os_mes ?? 0}
          sub="Ordens abertas este mês"
        />
        <KpiCard
          icon={Timer} label="T. Resposta" color="#8B5CF6"
          value={fmtMin(data.tempo_resposta_medio_min)}
          sub="Tempo médio de resposta"
        />
      </div>

      {/* OS abertas + equipamentos em manutenção */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* OS Abertas */}
        <div style={{ background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
              OS Abertas do Setor
            </h3>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 99,
              background: "rgba(59,130,246,0.12)", color: "#60A5FA",
            }}>
              {data.os_abertas?.length ?? 0}
            </span>
          </div>
          {(data.os_abertas?.length ?? 0) === 0 ? (
            <div style={{
              textAlign: "center", padding: "24px 16px",
              color: "rgba(255,255,255,0.2)", fontSize: 13, borderRadius: 4,
              border: "1px dashed #262626",
            }}>
              Nenhuma OS aberta
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.os_abertas.map(os => <OSCard key={os.id} os={os} />)}
            </div>
          )}
        </div>

        {/* Equipamentos em manutenção */}
        <div style={{ background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, color: "#F8FAFC", margin: "0 0 14px", fontFamily: "Outfit, sans-serif" }}>
            Equipamentos em Manutenção
          </h3>
          {(data.equipamentos_em_manutencao?.length ?? 0) === 0 ? (
            <div style={{
              textAlign: "center", padding: "24px 16px",
              color: "rgba(255,255,255,0.2)", fontSize: 13, borderRadius: 4,
              border: "1px dashed #262626",
            }}>
              Nenhum equipamento em manutenção
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.equipamentos_em_manutencao.map(eq => (
                <div key={eq.id} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 12px", borderRadius: 4,
                  background: "rgba(249,115,22,0.05)", border: "1px solid rgba(249,115,22,0.15)",
                }}>
                  <AlertTriangle size={14} style={{ color: "#F97316", flexShrink: 0 }} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: "#F8FAFC", margin: 0 }}>{eq.nome}</p>
                    <p style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", margin: 0, fontFamily: "monospace" }}>{eq.codigo}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
