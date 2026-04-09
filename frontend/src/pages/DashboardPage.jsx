import { useState, useEffect } from "react";
import { getDashboardKPIs, getBacklog, seedDemo } from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  Activity,
  Clock,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wrench,
  Timer,
  CheckCircle,
  XCircle,
  RefreshCw,
  Database
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
  Legend
} from "recharts";

const COLORS = ["hsl(217, 91%, 60%)", "hsl(0, 72%, 51%)", "hsl(142, 71%, 45%)", "hsl(38, 92%, 50%)"];

function KPICard({ title, value, subtitle, icon: Icon, trend, color = "primary" }) {
  return (
    <div className="border border-border bg-card p-4 rounded-sm" data-testid={`kpi-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-heading font-bold mt-1">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2 rounded-sm bg-${color}/10`}>
          <Icon className={`h-5 w-5 text-${color}`} />
        </div>
      </div>
      {trend !== undefined && (
        <div className="flex items-center gap-1 mt-2 text-xs">
          {trend >= 0 ? (
            <TrendingUp className="h-3 w-3 text-green-500" />
          ) : (
            <TrendingDown className="h-3 w-3 text-red-500" />
          )}
          <span className={trend >= 0 ? "text-green-500" : "text-red-500"}>
            {Math.abs(trend)}%
          </span>
          <span className="text-muted-foreground">vs mês anterior</span>
        </div>
      )}
    </div>
  );
}

function BacklogCard({ title, value, icon: Icon, status }) {
  const statusColors = {
    warning: "text-yellow-500 bg-yellow-500/10",
    danger: "text-red-500 bg-red-500/10",
    info: "text-blue-500 bg-blue-500/10",
    success: "text-green-500 bg-green-500/10"
  };
  
  return (
    <div className="flex items-center gap-3 p-3 border border-border rounded-sm" data-testid={`backlog-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <div className={`p-2 rounded-sm ${statusColors[status]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="text-xl font-heading font-bold">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [kpis, setKpis] = useState(null);
  const [backlog, setBacklog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [kpisRes, backlogRes] = await Promise.all([
        getDashboardKPIs(),
        getBacklog()
      ]);
      setKpis(kpisRes.data);
      setBacklog(backlogRes.data);
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
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const pieData = kpis?.preventiva_vs_corretiva ? [
    { name: "Preventiva", value: kpis.preventiva_vs_corretiva.preventiva },
    { name: "Corretiva", value: kpis.preventiva_vs_corretiva.corretiva }
  ] : [];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">Visão geral da manutenção</p>
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

      {/* KPIs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="OS do Mês"
          value={kpis?.total_os_mes || 0}
          icon={Wrench}
          color="primary"
        />
        <KPICard
          title="Disponibilidade"
          value={`${kpis?.disponibilidade?.toFixed(1) || 0}%`}
          icon={Activity}
          color="primary"
        />
        <KPICard
          title="MTTR"
          value={`${kpis?.mttr?.toFixed(1) || 0}h`}
          subtitle="Tempo médio de reparo"
          icon={Timer}
          color="primary"
        />
        <KPICard
          title="MTBF"
          value={`${kpis?.mtbf?.toFixed(0) || 0}h`}
          subtitle="Tempo entre falhas"
          icon={Clock}
          color="primary"
        />
      </div>

      {/* Backlog */}
      <div className="border border-border rounded-sm p-4 bg-card">
        <h2 className="font-heading font-semibold mb-4">Backlog de OS</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <BacklogCard
            title="Abertas"
            value={backlog?.abertas || 0}
            icon={AlertTriangle}
            status="warning"
          />
          <BacklogCard
            title="Em Atendimento"
            value={backlog?.em_atendimento || 0}
            icon={Wrench}
            status="info"
          />
          <BacklogCard
            title="Aguardando Revisão"
            value={backlog?.aguardando_revisao || 0}
            icon={Clock}
            status="info"
          />
          <BacklogCard
            title="Atrasadas"
            value={backlog?.atrasadas || 0}
            icon={XCircle}
            status="danger"
          />
        </div>
      </div>

      {/* Costs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-border rounded-sm p-4 bg-card">
          <h2 className="font-heading font-semibold mb-4 flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Custos do Mês
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-muted rounded-sm">
              <span className="text-sm">Custo Total de Manutenção</span>
              <span className="font-heading font-bold text-lg">
                R$ {kpis?.custo_total_mes?.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) || '0,00'}
              </span>
            </div>
            <div className="flex justify-between items-center p-3 bg-destructive/10 rounded-sm">
              <span className="text-sm">Custo de Máquina Parada</span>
              <span className="font-heading font-bold text-lg text-destructive">
                R$ {kpis?.custo_parada_mes?.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) || '0,00'}
              </span>
            </div>
          </div>
        </div>

        {/* Preventiva vs Corretiva Pie */}
        <div className="border border-border rounded-sm p-4 bg-card">
          <h2 className="font-heading font-semibold mb-4">Preventiva vs Corretiva</h2>
          {pieData.length > 0 && (pieData[0].value > 0 || pieData[1].value > 0) ? (
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[180px] flex items-center justify-center text-muted-foreground text-sm">
              Sem dados disponíveis
            </div>
          )}
        </div>
      </div>

      {/* Rankings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Falhas */}
        <div className="border border-border rounded-sm p-4 bg-card">
          <h2 className="font-heading font-semibold mb-4">Top Equipamentos - Falhas</h2>
          {kpis?.top_equipamentos_falhas?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={kpis.top_equipamentos_falhas} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" />
                <YAxis dataKey="codigo" type="category" width={80} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="total" fill="hsl(0, 72%, 51%)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              Sem dados de falhas
            </div>
          )}
        </div>

        {/* Top Custos */}
        <div className="border border-border rounded-sm p-4 bg-card">
          <h2 className="font-heading font-semibold mb-4">Top Equipamentos - Custos</h2>
          {kpis?.top_equipamentos_custos?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={kpis.top_equipamentos_custos} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={(value) => `R$${value}`} />
                <YAxis dataKey="codigo" type="category" width={80} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`} />
                <Bar dataKey="total" fill="hsl(217, 91%, 60%)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
              Sem dados de custos
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
