import { useState, useEffect } from "react";
import { getDashboardKPIs, getBacklog, seedDemo, getBillingPlan, getConfiabilidade, getDashboardTendencia } from "../lib/api";
import { useFinancialAccess, BlurredMoney } from "../components/shared/FinancialGuard";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Clock,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wrench,
  Timer,
  XCircle,
  RefreshCw,
  Database,
  Gauge,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  BarChart3,
  ChevronRight,
  Target,
  ShieldCheck,
  Loader2,
  ShieldAlert,
  Radio,
  Flame,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  Area,
  AreaChart,
} from "recharts";

const CHART_COLORS = {
  primary: "hsl(217, 91%, 60%)",
  danger: "hsl(0, 72%, 51%)",
  success: "hsl(142, 71%, 45%)",
  warning: "hsl(38, 92%, 50%)",
  purple: "hsl(262, 83%, 58%)",
};

// ========== COMPONENTS ==========

function MetricCard({ title, value, subtitle, icon: Icon, color = "primary", className = "" }) {
  const colorMap = {
    primary: { bg: "bg-blue-500/10", text: "text-blue-500", glow: "metric-glow-blue" },
    danger: { bg: "bg-red-500/10", text: "text-red-500", glow: "metric-glow-red" },
    success: { bg: "bg-emerald-500/10", text: "text-emerald-500", glow: "metric-glow-green" },
    warning: { bg: "bg-amber-500/10", text: "text-amber-500", glow: "metric-glow-amber" },
    purple: { bg: "bg-purple-500/10", text: "text-purple-500", glow: "metric-glow-purple" },
  };

  const c = colorMap[color] || colorMap.primary;

  return (
    <div className={`group border border-border/50 bg-card rounded-xl p-5 card-hover ${c.glow} ${className}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{title}</p>
          <p className="text-3xl font-bold font-heading mt-2 leading-none animate-counter">{value}</p>
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-2 truncate">{subtitle}</p>
          )}
        </div>
        <div className={`p-2.5 rounded-xl ${c.bg} ${c.text} transition-transform group-hover:scale-110`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ value, label, color, icon: Icon }) {
  const colorMap = {
    warning: "bg-amber-500/8 text-amber-600 dark:text-amber-400 border-amber-500/15",
    danger: "bg-red-500/8 text-red-600 dark:text-red-400 border-red-500/15",
    info: "bg-blue-500/8 text-blue-600 dark:text-blue-400 border-blue-500/15",
    success: "bg-emerald-500/8 text-emerald-600 dark:text-emerald-400 border-emerald-500/15",
  };

  return (
    <div className={`flex flex-col items-center justify-center p-5 rounded-xl border ${colorMap[color]} transition-all hover:scale-[1.02]`}>
      {Icon && <Icon className="h-4 w-4 mb-1.5 opacity-60" />}
      <span className="text-2xl font-bold font-heading leading-none">{value}</span>
      <span className="text-[11px] font-medium mt-1.5 opacity-70">{label}</span>
    </div>
  );
}

function RankingList({ title, items, valueFormatter, icon: Icon, emptyMsg, accentColor = "primary" }) {
  const borderMap = {
    primary: "border-l-blue-500",
    danger: "border-l-red-500",
    warning: "border-l-amber-500",
  };

  return (
    <div className="border border-border/50 rounded-xl bg-card overflow-hidden card-hover">
      <div className="flex items-center gap-2.5 px-5 py-4 border-b border-border/50">
        <Icon className="h-5 w-5 text-primary" />
        <h3 className="font-heading font-semibold text-sm">{title}</h3>
      </div>
      {items && items.length > 0 ? (
        <div className="divide-y divide-border/30">
          {items.map((item, idx) => (
            <div
              key={idx}
              className={`flex items-center justify-between px-5 py-3.5 hover:bg-muted/30 transition-colors border-l-2 ${
                idx === 0 ? borderMap[accentColor] || borderMap.primary : "border-l-transparent"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className={`flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold ${
                  idx === 0 ? 'bg-red-500/15 text-red-500' :
                  idx === 1 ? 'bg-amber-500/15 text-amber-500' :
                  'bg-muted text-muted-foreground'
                }`}>
                  {idx + 1}
                </span>
                <div>
                  <p className="text-sm font-medium leading-tight">{item.nome}</p>
                  <p className="text-[11px] text-muted-foreground">{item.codigo}</p>
                </div>
              </div>
              <span className="text-sm font-semibold font-mono whitespace-nowrap">
                {valueFormatter ? valueFormatter(item) : item.total}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
          {emptyMsg || "Sem dados disponíveis"}
        </div>
      )}
    </div>
  );
}

// Custom tooltip for charts
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card/95 backdrop-blur-xl border border-border rounded-lg px-3 py-2 shadow-xl">
      {payload.map((entry, i) => (
        <p key={i} className="text-xs">
          <span className="text-muted-foreground">{entry.name}: </span>
          <span className="font-semibold">{entry.value}</span>
        </p>
      ))}
    </div>
  );
}

// ========== MAIN DASHBOARD ==========

export default function DashboardPage() {
  const [kpis, setKpis] = useState(null);
  const [backlog, setBacklog] = useState(null);
  const [billing, setBilling] = useState(null);
  const [confiabilidade, setConfiabilidade] = useState(null);
  const [tendencia, setTendencia] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const navigate = useNavigate();

  const loadData = async () => {
    setLoading(true);
    try {
      const [kpisRes, backlogRes, billingRes, confRes, tendRes] = await Promise.all([
        getDashboardKPIs(),
        getBacklog(),
        getBillingPlan().catch(() => ({ data: null })),
        getConfiabilidade(24).catch(() => ({ data: null })),
        getDashboardTendencia(30).catch(() => ({ data: null })),
      ]);
      setKpis(kpisRes.data || null);
      setBacklog(backlogRes.data || null);
      if (billingRes && billingRes.data) setBilling(billingRes.data);
      if (confRes && confRes.data) setConfiabilidade(confRes.data);
      if (tendRes && tendRes.data) setTendencia(tendRes.data);
    } catch (error) {
      console.error("Error loading dashboard:", error);
      toast.error("Erro ao carregar dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const [seedCreds, setSeedCreds] = useState(null);
  const finAccess = useFinancialAccess();

  const handleSeedDemo = async (reset = false) => {
    setSeeding(true);
    try {
      const res = await seedDemo(reset);
      if (res.data?.credenciais) {
        setSeedCreds(res.data.credenciais);
        toast.success(`Dados demo ${reset ? "recriados" : "criados"}! 12 usuários criados.`);
      } else {
        toast.info(res.data?.message || "Dados de demonstração já existem. Use 'Recriar' para resetar.");
      }
      loadData();
    } catch (error) {
      toast.error("Erro ao criar dados de demonstração");
    } finally {
      setSeeding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-80">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground font-medium">Calculando indicadores...</span>
        </div>
      </div>
    );
  }

  if (!kpis) {
    return (
      <div className="flex flex-col items-center justify-center h-80 gap-4">
        <div className="p-4 rounded-full bg-muted">
          <BarChart3 className="h-8 w-8 text-muted-foreground" />
        </div>
        <div className="text-center">
          <p className="font-heading font-semibold text-lg">Nenhum dado disponível</p>
          <p className="text-sm text-muted-foreground mt-1">Crie dados de demonstração para começar</p>
        </div>
        <div className="flex gap-2 mt-2">
          <Button variant="outline" onClick={loadData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Tentar novamente
          </Button>
          <Button onClick={handleSeedDemo} disabled={seeding}>
            <Database className="h-4 w-4 mr-2" />
            {seeding ? "Criando..." : "Dados Demo"}
          </Button>
        </div>
      </div>
    );
  }

  const pvc = kpis?.preventiva_vs_corretiva || {};
  const pieData = [
    { name: "Corretiva",  value: pvc.corretiva  || 0, color: CHART_COLORS.danger  },
    { name: "Preventiva", value: pvc.preventiva || 0, color: CHART_COLORS.success },
    { name: "Preditiva",  value: pvc.preditiva  || 0, color: CHART_COLORS.purple  },
  ].filter(d => d.value > 0);

  const totalPie = pieData.reduce((s, d) => s + d.value, 0);
  const prevVal  = pvc.preventiva || 0;
  const prevPercent = totalPie > 0 ? Math.round((prevVal / totalPie) * 100) : 0;

  // Plan usage warning
  const showPlanWarning = billing && billing.usage_percent && (
    billing.usage_percent.equipamentos >= 80 ||
    billing.usage_percent.users >= 80 ||
    billing.usage_percent.os_mes >= 80
  );

  // Availability status
  const availStatus = kpis?.disponibilidade >= 95 ? "success" :
                      kpis?.disponibilidade >= 85 ? "warning" : "danger";
  const availLabel = kpis?.disponibilidade >= 95 ? "Excelente" :
                     kpis?.disponibilidade >= 85 ? "Atenção" : "Crítico";

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Target className="h-6 w-6 text-primary" />
            Inteligência de Manutenção
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Indicadores estratégicos para decisão em 5 segundos
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadData} className="h-9 rounded-lg" data-testid="refresh-btn">
            <RefreshCw className="h-4 w-4 mr-2" />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleSeedDemo(false)} disabled={seeding} className="h-9 rounded-lg" data-testid="seed-demo-btn">
            <Database className="h-4 w-4 mr-2" />
            {seeding ? "Criando..." : "Demo"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleSeedDemo(true)} disabled={seeding} className="h-9 rounded-lg text-amber-500 border-amber-500/30 hover:bg-amber-500/10" data-testid="seed-reset-btn" title="Apaga todos os dados demo e recria do zero">
            <RefreshCw className="h-4 w-4 mr-2" />
            Recriar
          </Button>
        </div>
      </div>

      {/* Credenciais de Demo */}
      {seedCreds && (
        <div className="bg-card border border-primary/20 rounded-xl p-5 animate-slide-in-bottom" data-testid="seed-credentials-panel">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" />
              <span className="font-semibold text-sm">Credenciais de Acesso — Demo</span>
            </div>
            <button onClick={() => setSeedCreds(null)} className="text-muted-foreground hover:text-foreground text-xs" data-testid="btn-fechar-credenciais">✕ Fechar</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/40">
                  {["Perfil","E-mail","Senha","Role","Setor"].map(h => (
                    <th key={h} className="text-left text-muted-foreground font-medium px-3 py-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(seedCreds).map(([key, c]) => (
                  <tr key={key} className="border-b border-border/10 hover:bg-muted/20">
                    <td className="px-3 py-2 font-medium capitalize">{key.replace(/_/g," ")}</td>
                    <td className="px-3 py-2 font-mono text-primary">{c.email}</td>
                    <td className="px-3 py-2 font-mono">{c.senha}</td>
                    <td className="px-3 py-2 capitalize">{c.role}</td>
                    <td className="px-3 py-2 text-muted-foreground">{c.setor || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-muted-foreground mt-3">Plano: AVANÇADO · 15 equipamentos · 50 OS · 420 leituras de sensor · 7 alertas preditivos</p>
        </div>
      )}

      {/* Plan Warning Banner */}
      {showPlanWarning && (
        <div className="flex items-center justify-between bg-amber-500/8 border border-amber-500/15 rounded-xl px-5 py-3 animate-slide-in-bottom">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
              Você está próximo do limite do plano {billing?.plano?.toUpperCase()}
            </span>
          </div>
          <Button size="sm" onClick={() => navigate('/billing')} className="bg-amber-500 hover:bg-amber-600 text-white rounded-lg h-8">
            <Zap className="h-3.5 w-3.5 mr-1.5" />
            Upgrade
          </Button>
        </div>
      )}

      {/* Main KPIs — the "5 second" metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        <MetricCard
          title="Disponibilidade"
          value={`${kpis?.disponibilidade?.toFixed(1) || 0}%`}
          subtitle={availLabel}
          icon={Gauge}
          color={availStatus}
        />
        <MetricCard
          title="MTTR"
          value={`${kpis?.mttr?.toFixed(1) || 0}h`}
          subtitle="Tempo médio de reparo"
          icon={Timer}
          color="primary"
        />
        <MetricCard
          title="MTBF"
          value={`${kpis?.mtbf?.toFixed(0) || 0}h`}
          subtitle="Tempo entre falhas"
          icon={Activity}
          color="purple"
        />
        <MetricCard
          title="Custo Total"
          value={finAccess === 'full'
            ? `R$ ${(kpis?.custo_total_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
            : <BlurredMoney size="lg" />}
          subtitle="Manutenção este mês"
          icon={DollarSign}
          color="warning"
        />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        <MetricCard
          title="OS do Mês"
          value={kpis?.total_os_mes || 0}
          icon={Wrench}
          color="primary"
        />
        <MetricCard
          title="Tempo Resposta"
          value={`${kpis?.avg_tempo_resposta?.toFixed(0) || 0} min`}
          subtitle="Média de resposta"
          icon={Clock}
          color="primary"
        />
        <MetricCard
          title="Fora do SLA"
          value={kpis?.os_atrasadas || 0}
          subtitle={kpis?.os_atrasadas > 0 ? "Requer atenção" : "Todas dentro do SLA"}
          icon={AlertTriangle}
          color={kpis?.os_atrasadas > 0 ? "danger" : "success"}
        />
        <MetricCard
          title="Custo de Parada"
          value={finAccess === 'full'
            ? `R$ ${(kpis?.custo_parada_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
            : <BlurredMoney size="lg" color="red" />}
          subtitle="Máquina parada"
          icon={TrendingDown}
          color="danger"
        />
      </div>

      {/* Backlog Status */}
      <div className="border border-border/50 rounded-xl bg-card overflow-hidden card-hover">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/50">
          <h2 className="font-heading font-semibold flex items-center gap-2.5">
            <BarChart3 className="h-5 w-5 text-primary" />
            Backlog Operacional
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold font-heading">{backlog?.total_pendentes || 0}</span>
            <span className="text-xs text-muted-foreground font-medium">pendentes</span>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-border/30">
          <StatusBadge value={backlog?.abertas || 0} label="Abertas" color="warning" icon={XCircle} />
          <StatusBadge value={backlog?.em_atendimento || 0} label="Em Atendimento" color="info" icon={Wrench} />
          <StatusBadge value={backlog?.aguardando_peca || 0} label="Ag. Peça" color="warning" icon={Timer} />
          <StatusBadge value={backlog?.aguardando_revisao || 0} label="Ag. Revisão" color="info" icon={ShieldCheck} />
          <StatusBadge value={backlog?.atrasadas || 0} label="Atrasadas" color="danger" icon={AlertTriangle} />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Mix de Manutenção */}
        <div className="border border-border/50 rounded-xl bg-card p-5 card-hover">
          <h3 className="font-heading font-semibold text-sm mb-1">Mix de Manutenção</h3>
          <p className="text-xs text-muted-foreground mb-4">
            {totalPie > 0
              ? `${prevPercent}% preventiva — ${prevPercent >= 60 ? "✅ Boa prática" : "⚠️ Oportunidade de melhoria"}`
              : "Sem OS registradas"}
          </p>
          {totalPie > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="45%"
                  innerRadius={55}
                  outerRadius={82}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                  label={({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
                    if (percent < 0.05) return null;
                    const RADIAN = Math.PI / 180;
                    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                    const x = cx + radius * Math.cos(-midAngle * RADIAN);
                    const y = cy + radius * Math.sin(-midAngle * RADIAN);
                    return (
                      <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central"
                        fontSize={11} fontWeight={700}>
                        {`${(percent * 100).toFixed(0)}%`}
                      </text>
                    );
                  }}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Legend
                  verticalAlign="bottom"
                  formatter={(value, entry) => (
                    <span className="text-xs font-medium">
                      {value} ({entry.payload.value})
                    </span>
                  )}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload;
                    const pct = totalPie > 0 ? Math.round((d.value / totalPie) * 100) : 0;
                    return (
                      <div className="bg-card/95 backdrop-blur-xl border border-border rounded-lg px-3 py-2 shadow-xl">
                        <p className="text-xs font-semibold">{d.name}</p>
                        <p className="text-xs text-muted-foreground">{d.value} OS ({pct}%)</p>
                      </div>
                    );
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-muted-foreground text-sm">
              Sem dados disponíveis
            </div>
          )}
        </div>

        {/* Financial Impact */}
        <div className="border border-border/50 rounded-xl bg-card p-5 card-hover">
          <h3 className="font-heading font-semibold text-sm mb-1">Impacto Financeiro</h3>
          <p className="text-xs text-muted-foreground mb-5">Custo de manutenção vs custo de parada</p>
          <div className="space-y-5">
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                  Manutenção
                </span>
                {finAccess === 'full' ? (
                  <span className="text-lg font-bold font-heading text-blue-500">
                    R$ {(kpis?.custo_total_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </span>
                ) : <BlurredMoney size="md" color="blue" />}
              </div>
              <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                {finAccess === 'full' && (
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-1000"
                    style={{ width: `${Math.min(((kpis?.custo_total_mes || 0) / Math.max((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0), 1)) * 100, 100)}%` }}
                  />
                )}
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                  Parada de Máquina
                </span>
                {finAccess === 'full' ? (
                  <span className="text-lg font-bold font-heading text-red-500">
                    R$ {(kpis?.custo_parada_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </span>
                ) : <BlurredMoney size="md" color="red" />}
              </div>
              <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                {finAccess === 'full' && (
                  <div
                    className="h-full bg-gradient-to-r from-red-500 to-red-400 rounded-full transition-all duration-1000"
                    style={{ width: `${Math.min(((kpis?.custo_parada_mes || 0) / Math.max((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0), 1)) * 100, 100)}%` }}
                  />
                )}
              </div>
            </div>
            <div className="pt-4 border-t border-border/50">
              <div className="flex justify-between items-center">
                <span className="text-sm font-semibold">Custo Total Mensal</span>
                {finAccess === 'full' ? (
                  <span className="text-2xl font-bold font-heading">
                    R$ {((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0)).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </span>
                ) : <BlurredMoney size="lg" />}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Rankings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <RankingList
          title="🔥 Mais Falhas"
          items={kpis?.top_equipamentos_falhas}
          icon={AlertTriangle}
          valueFormatter={(item) => `${item.total} falhas`}
          emptyMsg="Nenhuma falha registrada"
          accentColor="danger"
        />
        <RankingList
          title="💰 Maior Custo"
          items={kpis?.top_equipamentos_custos}
          icon={DollarSign}
          valueFormatter={(item) =>
            finAccess === 'full'
              ? `R$ ${item.total?.toLocaleString('pt-BR', { minimumFractionDigits: 0 })}`
              : <BlurredMoney />
          }
          emptyMsg="Sem custos registrados"
          accentColor="warning"
        />
        <RankingList
          title="⏱ Maior Downtime"
          items={kpis?.top_equipamentos_downtime}
          icon={Clock}
          valueFormatter={(item) => `${item.total_horas}h`}
          emptyMsg="Sem dados de parada"
          accentColor="primary"
        />
      </div>

      {/* Tendência OS — últimos 30 dias */}
      {tendencia && tendencia.serie?.length > 0 && (
        <div className="border border-border/50 rounded-xl bg-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-sm">Tendência de OS — Últimos 30 dias</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Total, corretivas e fechadas por dia</p>
            </div>
            <button
              onClick={() => navigate("/relatorios")}
              className="text-xs text-primary flex items-center gap-1 hover:underline"
            >
              Ver relatório <ChevronRight className="h-3 w-3" />
            </button>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={tendencia.serie} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#1A6FE8" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#1A6FE8" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradCorr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#EF4444" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="data" tick={{ fontSize: 10, fill: "#64748B" }} tickLine={false} axisLine={false}
                interval={Math.floor(tendencia.serie.length / 7)} />
              <YAxis tick={{ fontSize: 10, fill: "#64748B" }} tickLine={false} axisLine={false} allowDecimals={false} width={24} />
              <Tooltip
                contentStyle={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }}
                formatter={(v, name) => [v, name === "total" ? "Total" : name === "corretivas" ? "Corretivas" : "Fechadas"]}
              />
              <Area type="monotone" dataKey="total" name="total" stroke="#1A6FE8" strokeWidth={2} fill="url(#gradTotal)" dot={false} />
              <Area type="monotone" dataKey="corretivas" name="corretivas" stroke="#EF4444" strokeWidth={1.5} fill="url(#gradCorr)" dot={false} strokeDasharray="4 2" />
              <Line type="monotone" dataKey="fechadas" name="fechadas" stroke="#10B981" strokeWidth={1.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
          <div className="flex gap-5 justify-center mt-3">
            {[["#1A6FE8","Total"],["#EF4444","Corretivas"],["#10B981","Fechadas"]].map(([c,l]) => (
              <span key={l} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="w-4 h-0.5 rounded" style={{ background: c }} />{l}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Confiabilidade & Risco */}
      {confiabilidade && confiabilidade.equipamentos?.length > 0 && (
        <div className="space-y-4" data-testid="reliability-section">
          {/* Reliability Header */}
          <div className="flex items-center justify-between">
            <h2 className="font-heading font-semibold text-lg flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-primary" />
              Confiabilidade & Risco
              <span className="text-xs font-normal text-muted-foreground ml-1">
                (horizonte: {confiabilidade.horizonte_horas}h)
              </span>
            </h2>
          </div>

          {/* Reliability KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
            <MetricCard
              title="Confiabilidade Média"
              value={`${confiabilidade.resumo?.confiabilidade_media?.toFixed(1) || 100}%`}
              subtitle={`R(t) em ${confiabilidade.horizonte_horas}h`}
              icon={ShieldAlert}
              color={confiabilidade.resumo?.confiabilidade_media >= 80 ? "success" : confiabilidade.resumo?.confiabilidade_media >= 50 ? "warning" : "danger"}
            />
            <MetricCard
              title="λ Médio"
              value={confiabilidade.resumo?.lambda_medio?.toFixed(4) || "0"}
              subtitle="falhas/hora"
              icon={Radio}
              color={confiabilidade.resumo?.lambda_medio >= 0.05 ? "danger" : confiabilidade.resumo?.lambda_medio >= 0.01 ? "warning" : "success"}
            />
            <MetricCard
              title="Alertas Críticos"
              value={confiabilidade.resumo?.alertas_criticos || 0}
              subtitle={`${confiabilidade.resumo?.alertas_alto || 0} altos, ${confiabilidade.resumo?.alertas_atencao || 0} atenção`}
              icon={Flame}
              color={confiabilidade.resumo?.alertas_criticos > 0 ? "danger" : "success"}
            />
            <MetricCard
              title="Equip. Instáveis"
              value={confiabilidade.resumo?.["equipamentos_instáveis"] || 0}
              subtitle="λ ≥ 0.05 falhas/h"
              icon={AlertTriangle}
              color={confiabilidade.resumo?.["equipamentos_instáveis"] > 0 ? "danger" : "success"}
            />
          </div>

          {/* Reliability Alerts */}
          {confiabilidade.alertas?.length > 0 && (
            <div className="space-y-2">
              {confiabilidade.alertas.slice(0, 5).map((alerta, i) => (
                <div
                  key={i}
                  className={`flex items-start gap-3 px-4 py-3 rounded-xl border text-sm animate-slide-in-bottom ${
                    alerta.tipo === "critico"
                      ? "bg-red-500/8 border-red-500/20 text-red-700 dark:text-red-400"
                      : alerta.tipo === "alto"
                        ? "bg-amber-500/8 border-amber-500/20 text-amber-700 dark:text-amber-400"
                        : "bg-blue-500/8 border-blue-500/20 text-blue-700 dark:text-blue-400"
                  }`}
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <AlertTriangle className={`h-4 w-4 mt-0.5 shrink-0 ${
                    alerta.tipo === "critico" ? "text-red-500" : alerta.tipo === "alto" ? "text-amber-500" : "text-blue-500"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium">{alerta.mensagem}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-mono font-bold text-xs">R(t) {alerta.confiabilidade}%</p>
                    <p className="font-mono text-[10px] opacity-70">Risco {alerta.risco}%</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Equipment Risk Table */}
          <div className="border border-border/50 rounded-xl bg-card overflow-hidden card-hover">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border/50">
              <h3 className="font-heading font-semibold text-sm flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                Matriz de Risco por Equipamento
              </h3>
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                Probabilidade × Impacto
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full table-dense">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-4 py-3">Equipamento</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">Crit.</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">Falhas</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">λ (falhas/h)</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">MTBF</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">R(t)</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">Risco</th>
                    <th className="text-center text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {confiabilidade.equipamentos.slice(0, 15).map((eq) => (
                    <tr key={eq.equipamento_id} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-3">
                        <p className="text-sm font-medium">{eq.nome}</p>
                        <p className="text-[11px] text-muted-foreground">{eq.codigo}</p>
                      </td>
                      <td className="text-center px-3 py-3">
                        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold ${
                          eq.criticidade >= 4 ? 'bg-red-500/15 text-red-500' :
                          eq.criticidade >= 3 ? 'bg-amber-500/15 text-amber-500' :
                          'bg-muted text-muted-foreground'
                        }`}>
                          {eq.criticidade}
                        </span>
                      </td>
                      <td className="text-center px-3 py-3 font-mono text-sm font-semibold">{eq.falhas}</td>
                      <td className="text-center px-3 py-3">
                        <span className={`font-mono text-sm font-semibold ${
                          eq.lambda_status === 'instavel' ? 'text-red-500' :
                          eq.lambda_status === 'atencao' ? 'text-amber-500' :
                          'text-emerald-500'
                        }`}>
                          {eq.lambda.toFixed(4)}
                        </span>
                      </td>
                      <td className="text-center px-3 py-3 font-mono text-sm">{eq.mtbf_horas.toFixed(0)}h</td>
                      <td className="text-center px-3 py-3">
                        <span className={`font-mono text-sm font-bold ${
                          eq.confiabilidade_percent >= 80 ? 'text-emerald-500' :
                          eq.confiabilidade_percent >= 50 ? 'text-amber-500' :
                          'text-red-500'
                        }`}>
                          {eq.confiabilidade_percent}%
                        </span>
                      </td>
                      <td className="text-center px-3 py-3">
                        <div className="flex items-center justify-center gap-1.5">
                          <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${
                                eq.risco_percent >= 60 ? 'bg-red-500' :
                                eq.risco_percent >= 30 ? 'bg-amber-500' :
                                eq.risco_percent >= 10 ? 'bg-blue-500' :
                                'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(eq.risco_percent, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-[11px] font-semibold w-10 text-right">{eq.risco_percent}%</span>
                        </div>
                      </td>
                      <td className="text-center px-3 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          eq.nivel_risco === 'critico' ? 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20' :
                          eq.nivel_risco === 'alto' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20' :
                          eq.nivel_risco === 'atencao' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20' :
                          'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                        }`}>
                          {eq.nivel_risco}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
