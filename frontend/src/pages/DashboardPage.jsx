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
  Zap,
  BarChart3,
  ChevronRight,
  ArrowDownRight,
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
  AreaChart,
  Area,
} from "recharts";

const COLORS = {
  primary: "hsl(217, 91%, 60%)",
  danger: "hsl(0, 72%, 51%)",
  success: "hsl(142, 71%, 45%)",
  warning: "hsl(38, 92%, 50%)",
  purple: "hsl(262, 83%, 58%)",
};

function MetricCard({ title, value, subtitle, icon: Icon, color = "primary", trend }) {
  const colorMap = {
    primary: "bg-blue-500/10 text-blue-500",
    danger: "bg-red-500/10 text-red-500",
    success: "bg-emerald-500/10 text-emerald-500",
    warning: "bg-amber-500/10 text-amber-500",
    purple: "bg-purple-500/10 text-purple-500",
  };

  return (
    <div className="group border border-border bg-card rounded-lg p-5 hover:border-primary/30 transition-all">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
          <p className="text-3xl font-bold font-heading mt-2 leading-none">{value}</p>
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-2">{subtitle}</p>
          )}
        </div>
        <div className={`p-2.5 rounded-lg ${colorMap[color] || colorMap.primary}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      {trend !== undefined && trend !== null && (
        <div className="flex items-center gap-1 mt-3 pt-3 border-t border-border/50">
          {trend >= 0 ? (
            <ArrowUpRight className="h-3.5 w-3.5 text-emerald-500" />
          ) : (
            <ArrowDownRight className="h-3.5 w-3.5 text-red-500" />
          )}
          <span className={`text-xs font-semibold ${trend >= 0 ? "text-emerald-500" : "text-red-500"}`}>
            {Math.abs(trend)}%
          </span>
          <span className="text-xs text-muted-foreground">vs mês anterior</span>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ value, label, color }) {
  const colorMap = {
    warning: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    danger: "bg-red-500/10 text-red-600 border-red-500/20",
    info: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    success: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
  };

  return (
    <div className={`flex flex-col items-center justify-center p-4 rounded-lg border ${colorMap[color]}`}>
      <span className="text-2xl font-bold font-heading">{value}</span>
      <span className="text-xs font-medium mt-1">{label}</span>
    </div>
  );
}

function RankingList({ title, items, valueLabel, valueFormatter, icon: Icon, emptyMsg }) {
  return (
    <div className="border border-border rounded-lg bg-card">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
        <Icon className="h-5 w-5 text-primary" />
        <h3 className="font-heading font-semibold">{title}</h3>
      </div>
      {items && items.length > 0 ? (
        <div className="divide-y divide-border/50">
          {items.map((item, idx) => (
            <div key={idx} className="flex items-center justify-between px-5 py-3 hover:bg-muted/30 transition-colors">
              <div className="flex items-center gap-3">
                <span className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                  idx === 0 ? 'bg-red-500/10 text-red-500' : 
                  idx === 1 ? 'bg-amber-500/10 text-amber-500' : 
                  'bg-muted text-muted-foreground'
                }`}>
                  {idx + 1}
                </span>
                <div>
                  <p className="text-sm font-medium">{item.nome}</p>
                  <p className="text-xs text-muted-foreground">{item.codigo}</p>
                </div>
              </div>
              <span className="text-sm font-semibold font-mono">
                {valueFormatter ? valueFormatter(item) : item.total}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
          {emptyMsg || "Sem dados"}
        </div>
      )}
    </div>
  );
}

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
      toast.success(`Dados de demonstração criados! Login: ${res.data.email}`);
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
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="h-6 w-6 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Carregando indicadores...</span>
        </div>
      </div>
    );
  }

  if (!kpis) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <span className="text-muted-foreground">Nenhum dado disponível</span>
        <Button onClick={loadData}>Tentar novamente</Button>
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

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Inteligência de Manutenção</h1>
          <p className="text-muted-foreground text-sm">Indicadores estratégicos para decisão rápida</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadData} data-testid="refresh-btn">
            <RefreshCw className="h-4 w-4 mr-2" />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={handleSeedDemo} disabled={seeding} data-testid="seed-demo-btn">
            <Database className="h-4 w-4 mr-2" />
            {seeding ? "Criando..." : "Dados Demo"}
          </Button>
        </div>
      </div>

      {/* Plan Warning Banner */}
      {showPlanWarning && (
        <div className="flex items-center justify-between bg-amber-500/10 border border-amber-500/20 rounded-lg px-5 py-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            <span className="text-sm font-medium text-amber-700 dark:text-amber-400">
              Você está próximo do limite do plano {billing?.plano?.toUpperCase()}
            </span>
          </div>
          <Button size="sm" variant="outline" onClick={() => navigate('/billing')} className="text-amber-700 border-amber-500/30">
            <Zap className="h-4 w-4 mr-1" />
            Fazer Upgrade
          </Button>
        </div>
      )}

      {/* Main KPIs - "5 second" metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Disponibilidade"
          value={`${kpis?.disponibilidade?.toFixed(1) || 0}%`}
          subtitle={kpis?.disponibilidade >= 95 ? "Excelente" : kpis?.disponibilidade >= 85 ? "Atenção necessária" : "Crítico"}
          icon={Gauge}
          color={kpis?.disponibilidade >= 95 ? "success" : kpis?.disponibilidade >= 85 ? "warning" : "danger"}
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

      {/* Second row - Operational metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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
          subtitle={kpis?.os_atrasadas > 0 ? "Requer atenção" : "Dentro do padrão"}
          icon={AlertTriangle}
          color={kpis?.os_atrasadas > 0 ? "danger" : "success"}
        />
        <MetricCard
          title="Custo de Parada"
          value={`R$ ${(kpis?.custo_parada_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
          subtitle="Máquina parada este mês"
          icon={TrendingDown}
          color="danger"
        />
      </div>

      {/* Backlog Status */}
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-heading font-semibold flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-primary" />
            Status do Backlog
          </h2>
          <span className="text-sm font-semibold text-muted-foreground">
            {backlog?.total_pendentes || 0} pendentes
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border">
          <StatusBadge value={backlog?.abertas || 0} label="Abertas" color="warning" />
          <StatusBadge value={backlog?.em_atendimento || 0} label="Em Atendimento" color="info" />
          <StatusBadge value={backlog?.aguardando_revisao || 0} label="Ag. Revisão" color="info" />
          <StatusBadge value={backlog?.atrasadas || 0} label="Atrasadas" color="danger" />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Preventiva vs Corretiva */}
        <div className="border border-border rounded-lg bg-card p-5">
          <h3 className="font-heading font-semibold mb-1">Preventiva vs Corretiva</h3>
          <p className="text-xs text-muted-foreground mb-4">
            {prevPercent}% preventiva — {prevPercent >= 60 ? "Boa prática" : "Oportunidade de melhoria"}
          </p>
          {totalPie > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  <Cell fill={COLORS.success} />
                  <Cell fill={COLORS.danger} />
                </Pie>
                <Legend 
                  verticalAlign="bottom" 
                  formatter={(value) => <span className="text-xs">{value}</span>}
                />
                <Tooltip 
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              Sem dados disponíveis
            </div>
          )}
        </div>

        {/* Financial Impact */}
        <div className="border border-border rounded-lg bg-card p-5">
          <h3 className="font-heading font-semibold mb-1">Impacto Financeiro</h3>
          <p className="text-xs text-muted-foreground mb-4">Custo de manutenção vs parada</p>
          <div className="space-y-4">
            <div className="relative">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">Custo de Manutenção</span>
                <span className="text-lg font-bold font-heading text-blue-500">
                  R$ {(kpis?.custo_total_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${Math.min(((kpis?.custo_total_mes || 0) / Math.max((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0), 1)) * 100, 100)}%` }}
                />
              </div>
            </div>
            <div className="relative">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">Custo de Parada</span>
                <span className="text-lg font-bold font-heading text-red-500">
                  R$ {(kpis?.custo_parada_mes || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-500 rounded-full"
                  style={{ width: `${Math.min(((kpis?.custo_parada_mes || 0) / Math.max((kpis?.custo_total_mes || 0) + (kpis?.custo_parada_mes || 0), 1)) * 100, 100)}%` }}
                />
              </div>
            </div>
            <div className="pt-3 border-t border-border">
              <div className="flex justify-between items-center">
                <span className="text-sm font-semibold">Custo Total</span>
                <span className="text-xl font-bold font-heading">
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
          title="Mais Falhas"
          items={kpis?.top_equipamentos_falhas}
          icon={AlertTriangle}
          valueFormatter={(item) => `${item.total} falhas`}
          emptyMsg="Nenhuma falha registrada"
        />
        <RankingList
          title="Maior Custo"
          items={kpis?.top_equipamentos_custos}
          icon={DollarSign}
          valueFormatter={(item) => `R$ ${item.total?.toLocaleString('pt-BR', { minimumFractionDigits: 0 })}`}
          emptyMsg="Sem custos registrados"
        />
        <RankingList
          title="Maior Downtime"
          items={kpis?.top_equipamentos_downtime}
          icon={Clock}
          valueFormatter={(item) => `${item.total_horas}h`}
          emptyMsg="Sem dados de parada"
        />
      </div>
    </div>
  );
}
