import { useState, useEffect } from "react";
import { getDashboardKPIs, getBacklog, seedDemo, getBillingPlan } from "../lib/api";
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
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const navigate = useNavigate();

  const loadData = async () => {
    setLoading(true);
    try {
      const [kpisRes, backlogRes, billingRes] = await Promise.all([
        getDashboardKPIs(),
        getBacklog(),
        getBillingPlan().catch(() => ({ data: null })),
      ]);
      setKpis(kpisRes.data || null);
      setBacklog(backlogRes.data || null);
      if (billingRes && billingRes.data) setBilling(billingRes.data);
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

  const handleSeedDemo = async () => {
    setSeeding(true);
    try {
      const res = await seedDemo();
      toast.success(`Dados demo criados! Login: ${res.data.email}`);
      loadData();
    } catch (error) {
      if (error.response?.data?.message?.includes("já existem")) {
        toast.info("Dados de demonstração já existem");
      } else {
        toast.error("Erro ao criar dados de demonstração");
      }
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

  const pieData = kpis?.preventiva_vs_corretiva ? [
    { name: "Preventiva", value: kpis.preventiva_vs_corretiva.preventiva },
    { name: "Corretiva", value: kpis.preventiva_vs_corretiva.corretiva }
  ] : [];

  const totalPie = (pieData[0]?.value || 0) + (pieData[1]?.value || 0);
  const prevPercent = totalPie > 0 ? Math.round((pieData[0]?.value / totalPie) * 100) : 0;

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
          <Button variant="outline" size="sm" onClick={handleSeedDemo} disabled={seeding} className="h-9 rounded-lg" data-testid="seed-demo-btn">
            <Database className="h-4 w-4 mr-2" />
            {seeding ? "Criando..." : "Demo"}
          </Button>
        </div>
      </div>

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
          value={`R$ ${(kpis?.custo_total_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
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
          value={`R$ ${(kpis?.custo_parada_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border/30">
          <StatusBadge value={backlog?.abertas || 0} label="Abertas" color="warning" icon={XCircle} />
          <StatusBadge value={backlog?.em_atendimento || 0} label="Em Atendimento" color="info" icon={Wrench} />
          <StatusBadge value={backlog?.aguardando_revisao || 0} label="Ag. Revisão" color="info" icon={ShieldCheck} />
          <StatusBadge value={backlog?.atrasadas || 0} label="Atrasadas" color="danger" icon={AlertTriangle} />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Preventiva vs Corretiva */}
        <div className="border border-border/50 rounded-xl bg-card p-5 card-hover">
          <h3 className="font-heading font-semibold text-sm mb-1">Preventiva vs Corretiva</h3>
          <p className="text-xs text-muted-foreground mb-4">
            {prevPercent}% preventiva — {prevPercent >= 60 ? "✅ Boa prática" : "⚠️ Oportunidade de melhoria"}
          </p>
          {totalPie > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={4}
                  dataKey="value"
                  strokeWidth={0}
                >
                  <Cell fill={CHART_COLORS.success} />
                  <Cell fill={CHART_COLORS.danger} />
                </Pie>
                <Legend
                  verticalAlign="bottom"
                  formatter={(value) => <span className="text-xs font-medium">{value}</span>}
                />
                <Tooltip content={<CustomTooltip />} />
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
                <span className="text-lg font-bold font-heading text-blue-500">
                  R$ {(kpis?.custo_total_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(((kpis?.custo_total_mes || 0) / Math.max((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0), 1)) * 100, 100)}%` }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                  Parada de Máquina
                </span>
                <span className="text-lg font-bold font-heading text-red-500">
                  R$ {(kpis?.custo_parada_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="h-2.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-red-500 to-red-400 rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(((kpis?.custo_parada_mes || 0) / Math.max((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0), 1)) * 100, 100)}%` }}
                />
              </div>
            </div>
            <div className="pt-4 border-t border-border/50">
              <div className="flex justify-between items-center">
                <span className="text-sm font-semibold">Custo Total Mensal</span>
                <span className="text-2xl font-bold font-heading">
                  R$ {((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0)).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </span>
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
          valueFormatter={(item) => `R$ ${item.total?.toLocaleString('pt-BR', { minimumFractionDigits: 0 })}`}
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
    </div>
  );
}
