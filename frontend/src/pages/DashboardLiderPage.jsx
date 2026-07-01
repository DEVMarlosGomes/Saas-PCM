import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getDashboardLider } from "../lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Activity, Clock, Wrench, BarChart2, Timer, DollarSign,
  Users, AlertCircle, RefreshCw, Loader2, TrendingUp,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList,
} from "recharts";
import { HelpTooltip } from "../components/shared/HelpTooltip";

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
  return `${Math.round(h)}h`;
}

function fmtBRL(v) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}

const GRUPO_COLORS_CHART = {
  eletrico: "#3B82F6", hidraulico: "#F59E0B", mecanico: "#6B7280",
  pneumatico: "#0D9488", instrumentacao: "#8B5CF6", estrutural: "#FB923C", outro: "#64748B",
};

const STATUS_COLOR = {
  aberta: "#3B82F6", em_atendimento: "#F59E0B",
  aguardando_peca: "#F97316", aguardando_revisao: "#8B5CF6", revisada: "#10B981",
};
const PRIO_COLOR = { critica: "#EF4444", alta: "#F97316", media: "#EAB308", baixa: "#10B981" };

// ─── KPI card ────────────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, label, value, sub, color = "#3B82F6", tooltip }) {
  return (
    <div style={{
      background: "#171717", border: "1px solid #262626",
      borderRadius: 4, padding: "18px 18px 14px",
      borderTop: `2px solid ${color}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ fontSize: 10, fontWeight: 600, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.05em", display: "flex", alignItems: "center", gap: 2 }}>
          {label}
          {tooltip && <HelpTooltip text={tooltip} />}
        </span>
        <div style={{
          width: 28, height: 28, borderRadius: 4,
          background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon size={14} style={{ color }} />
        </div>
      </div>
      <p style={{ fontSize: 24, fontWeight: 800, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginTop: 3 }}>{sub}</p>}
    </div>
  );
}

// ─── Pareto tooltip ───────────────────────────────────────────────────────────

function ParetoTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#1A1A1A", border: "1px solid #262626", borderRadius: 4,
      padding: "8px 12px", fontSize: 12,
    }}>
      <p style={{ color: "#F8FAFC", margin: 0, fontWeight: 700 }}>{payload[0]?.payload?.grupo}</p>
      <p style={{ color: payload[0]?.color, margin: "2px 0 0" }}>OS: {payload[0]?.value}</p>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function DashboardLiderPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await getDashboardLider();
      setData(res.data);
      setLastUpdate(new Date());
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error("Acesso negado. Este dashboard é exclusivo para líderes e administradores.");
        navigate("/dashboard");
      } else {
        toast.error("Erro ao carregar dashboard do líder");
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => { load(); }, [load]);
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

  // Pareto data
  const paretoData = Object.entries(data.os_por_grupo_falha || {})
    .sort(([, a], [, b]) => b - a)
    .map(([grupo, total]) => ({ grupo, total, color: GRUPO_COLORS_CHART[grupo] || "#64748B" }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: "rgba(255,255,255,0.6)", margin: 0 }}>
            {data.setor_nome ? (
              <>Setor: <strong style={{ color: "#3B82F6" }}>{data.setor_nome}</strong></>
            ) : (
              <>Visão geral da organização</>
            )}
            {lastUpdate && (
              <span style={{ marginLeft: 12, color: "rgba(255,255,255,0.35)" }}>
                · {lastUpdate.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
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

      {/* 6 KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
        <KpiCard icon={Activity} label="Disponibilidade" color="#10B981"
          value={`${(data.disponibilidade_percent ?? 0).toFixed(1)}%`} sub="Uptime dos equipamentos"
          tooltip="% do tempo em que os equipamentos estavam operacionais. Meta ideal: acima de 95%." />
        <KpiCard icon={Wrench} label="MTTR" color="#F59E0B"
          value={fmtMin(data.mttr_minutos)} sub="Tempo médio de reparo"
          tooltip="Mean Time To Repair — tempo médio entre o início do atendimento e a conclusão do reparo. Quanto menor, melhor a eficiência da equipe." />
        <KpiCard icon={Clock} label="MTBF" color="#3B82F6"
          value={fmtHoras(data.mtbf_horas)} sub="Tempo médio entre falhas"
          tooltip="Mean Time Between Failures — tempo médio entre falhas do mesmo equipamento. Quanto maior, mais confiável é o ativo." />
        <KpiCard icon={BarChart2} label="OS do Mês" color="#8B5CF6"
          value={data.os_mes ?? 0} sub="Abertas este mês"
          tooltip="Total de ordens de serviço abertas no mês corrente, independente do status atual." />
        <KpiCard icon={Timer} label="T. Resposta" color="#F97316"
          value={fmtMin(data.tempo_resposta_medio_min)} sub="Tempo médio de resposta"
          tooltip="Tempo médio entre a abertura da OS e o início efetivo do atendimento pelo técnico. Reflete agilidade da equipe." />
        <KpiCard icon={DollarSign} label="Custo Parada" color="#EF4444"
          value={fmtBRL(data.custo_total_parada_mes)} sub="Acumulado no mês"
          tooltip="Soma do custo de parada de máquina de todas as OS do mês. Calculado com base no valor/hora configurado em cada equipamento." />
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Pareto por grupo de falha */}
        <div style={{ background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <TrendingUp size={15} style={{ color: "#3B82F6" }} />
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
              OS por Grupo de Falha
            </h3>
          </div>
          {paretoData.length === 0 ? (
            <div style={{ textAlign: "center", padding: "32px 16px", color: "rgba(255,255,255,0.2)", fontSize: 13 }}>
              Sem dados este mês
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={paretoData} layout="vertical" margin={{ left: 12, right: 20, top: 4, bottom: 4 }}>
                <XAxis type="number" hide />
                <YAxis
                  type="category" dataKey="grupo" tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }}
                  width={90} axisLine={false} tickLine={false}
                />
                <Tooltip content={<ParetoTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                <Bar dataKey="total" radius={[0, 2, 2, 0]} maxBarSize={20}>
                  {paretoData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                  <LabelList dataKey="total" position="right" style={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top 5 por custo */}
        <div style={{ background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <DollarSign size={15} style={{ color: "#EF4444" }} />
            <h3 style={{ fontSize: 13, fontWeight: 700, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
              Top 5 por Custo de Parada
            </h3>
          </div>
          {(data.top_equipamentos_custo?.length ?? 0) === 0 ? (
            <div style={{ textAlign: "center", padding: "32px 16px", color: "rgba(255,255,255,0.2)", fontSize: 13 }}>
              Sem dados
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.top_equipamentos_custo.map((eq, i) => {
                const maxCusto = data.top_equipamentos_custo[0]?.custo || 1;
                const ratio = (eq.custo / maxCusto) * 100;
                return (
                  <div key={i}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: "#F8FAFC", fontWeight: 600 }}>{eq.nome}</span>
                      <span style={{ fontSize: 12, color: "#EF4444", fontWeight: 700, fontFamily: "monospace" }}>
                        {fmtBRL(eq.custo)}
                      </span>
                    </div>
                    <div style={{ height: 3, background: "rgba(255,255,255,0.08)", borderRadius: 2 }}>
                      <div style={{ height: "100%", width: `${ratio}%`, background: "#EF4444", borderRadius: 2 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Técnicos ativos + pendentes revisão */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Técnicos ativos */}
        <div style={{ background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Users size={15} style={{ color: "#10B981" }} />
              <h3 style={{ fontSize: 13, fontWeight: 700, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
                Técnicos Ativos Agora
              </h3>
            </div>
            <span style={{
              fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 99,
              background: "rgba(16,185,129,0.12)", color: "#10B981",
            }}>
              {data.tecnicos_ativos?.length ?? 0}
            </span>
          </div>
          {(data.tecnicos_ativos?.length ?? 0) === 0 ? (
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.2)", textAlign: "center", padding: "16px 0" }}>
              Nenhum técnico em atendimento
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {data.tecnicos_ativos.map(t => (
                <div key={t.id} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "8px 10px", borderRadius: 4,
                  background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.12)",
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: "50%",
                    background: "rgba(16,185,129,0.15)", border: "1px solid rgba(16,185,129,0.3)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 700, color: "#10B981",
                  }}>
                    {(t.nome || "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <p style={{ fontSize: 12, fontWeight: 600, color: "#F8FAFC", margin: 0 }}>{t.nome}</p>
                    {t.employee_id && (
                      <p style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", margin: 0, fontFamily: "monospace" }}>
                        mat. {t.employee_id}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pendentes revisão + OS abertas */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Pendentes revisão */}
          <div style={{
            background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 16,
            borderLeft: `3px solid ${(data.pendentes_revisao ?? 0) > 0 ? "#8B5CF6" : "#262626"}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertCircle size={15} style={{ color: "#8B5CF6" }} />
              <span style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", fontWeight: 600 }}>
                Pendentes de Revisão
              </span>
              <span style={{
                marginLeft: "auto", fontSize: 20, fontWeight: 800, color: "#8B5CF6",
                fontFamily: "Outfit, sans-serif",
              }}>
                {data.pendentes_revisao ?? 0}
              </span>
            </div>
          </div>

          {/* OS abertas resumo */}
          <div style={{ background: "#171717", border: "1px solid #262626", borderRadius: 4, padding: 16, flex: 1 }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: "#F8FAFC", margin: "0 0 10px", fontFamily: "Outfit, sans-serif" }}>
              OS Abertas
            </h3>
            {(data.os_abertas?.length ?? 0) === 0 ? (
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.2)", textAlign: "center", padding: "8px 0" }}>
                Nenhuma OS aberta
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                {data.os_abertas.slice(0, 8).map(os => (
                  <div key={os.id} style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "6px 8px", borderRadius: 4, borderLeft: `2px solid ${PRIO_COLOR[os.prioridade] || "#64748B"}`,
                    background: "rgba(255,255,255,0.02)",
                  }}>
                    <span style={{ fontSize: 11, color: "rgba(255,255,255,0.6)" }}>
                      #{os.numero} · {os.descricao.slice(0, 40)}
                    </span>
                    <span style={{
                      fontSize: 10, padding: "1px 6px", borderRadius: 2,
                      background: `${STATUS_COLOR[os.status] || "#64748B"}15`,
                      color: STATUS_COLOR[os.status] || "#64748B",
                      fontWeight: 600, whiteSpace: "nowrap", marginLeft: 8,
                    }}>
                      {os.status?.replace(/_/g, " ")}
                    </span>
                  </div>
                ))}
                {data.os_abertas.length > 8 && (
                  <p style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", textAlign: "center", margin: 0 }}>
                    +{data.os_abertas.length - 8} mais
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
