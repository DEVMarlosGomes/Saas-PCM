import { useState, useEffect } from "react";
import { getOrdensServico, createOrdemServico, updateOrdemServico, getEquipamentos, getGrupos, getCustos, createCusto, getPendingReviews, autoApproveExpired } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";
import UpgradeDialog from "../components/UpgradeDialog";
import { useUpgradeDialog } from "../hooks/useUpgradeDialog";
import {
  Plus, Search, Wrench, Clock, AlertTriangle, CheckCircle, Eye, Play,
  FileCheck, DollarSign, Filter, X, Loader2, TrendingDown, Shield,
  ArrowRight, Timer, RefreshCw, Zap,
} from "lucide-react";

const statusConfig = {
  aberta: { label: "Aberta", color: "status-aberta", icon: AlertTriangle, next: "em_atendimento", nextLabel: "Iniciar" },
  em_atendimento: { label: "Em Atendimento", color: "status-em-atendimento", icon: Wrench, next: "aguardando_revisao", nextLabel: "Concluir" },
  aguardando_revisao: { label: "Ag. Revisão", color: "status-aguardando-revisao", icon: Clock, next: "revisada", nextLabel: "Aprovar" },
  revisada: { label: "Revisada", color: "status-revisada", icon: CheckCircle, next: "fechada", nextLabel: "Fechar" },
  fechada: { label: "Fechada", color: "status-fechada", icon: FileCheck },
};

const prioridadeConfig = {
  baixa: { label: "Baixa", color: "priority-baixa" },
  media: { label: "Média", color: "priority-media" },
  alta: { label: "Alta", color: "priority-alta" },
  critica: { label: "Crítica", color: "priority-critica" },
};

const tipoConfig = {
  corretiva: { label: "Corretiva", color: "bg-red-500/10 text-red-500 border-red-500/20" },
  preventiva: { label: "Preventiva", color: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
  preditiva: { label: "Preditiva", color: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
};

export default function OrdensServicoPage() {
  const { user } = useAuth();
  const { upgradeOpen, upgradeMessage, handleApiError, closeUpgrade } = useUpgradeDialog();
  const [ordens, setOrdens] = useState([]);
  const [equipamentos, setEquipamentos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterTipo, setFilterTipo] = useState("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [detailOS, setDetailOS] = useState(null);
  const [detailCustos, setDetailCustos] = useState([]);
  const [showCustoModal, setShowCustoModal] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const [formData, setFormData] = useState({
    equipamento_id: "", tipo: "corretiva", prioridade: "media", descricao: "",
    falha_tipo: "", falha_modo: "", falha_causa: ""
  });
  const [custoForm, setCustoForm] = useState({
    tipo: "consumo", descricao: "", valor: "", quantidade: "1"
  });
  const [creating, setCreating] = useState(false);

  const canEditOS = user?.role === "admin" || user?.role === "lider" || user?.role === "tecnico";
  const canReviewOS = user?.role === "admin" || user?.role === "lider";

  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterStatus && filterStatus !== "all") params.status = filterStatus;
      if (filterTipo && filterTipo !== "all") params.tipo = filterTipo;
      const [osRes, eqRes] = await Promise.all([
        getOrdensServico(params),
        getEquipamentos(),
      ]);
      setOrdens(osRes.data || []);
      setEquipamentos(eqRes.data || []);

      // Count pending reviews
      if (canReviewOS) {
        try {
          const pr = await getPendingReviews();
          setPendingCount(pr.data?.length || 0);
        } catch { setPendingCount(0); }
      }
    } catch (error) {
      toast.error("Erro ao carregar ordens de serviço");
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadData(); }, [filterStatus, filterTipo]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.equipamento_id || !formData.descricao) {
      toast.error("Preencha equipamento e descrição");
      return;
    }
    setCreating(true);
    try {
      await createOrdemServico(formData);
      toast.success("OS criada com sucesso!");
      setShowCreateModal(false);
      setFormData({ equipamento_id: "", tipo: "corretiva", prioridade: "media", descricao: "", falha_tipo: "", falha_modo: "", falha_causa: "" });
      loadData();
    } catch (error) {
      if (!handleApiError(error)) {
        toast.error(error.response?.data?.detail || "Erro ao criar OS");
      }
    } finally {
      setCreating(false);
    }
  };

  const handleStatusChange = async (os, newStatus) => {
    try {
      await updateOrdemServico(os.id, { status: newStatus });
      toast.success("Status atualizado!");
      loadData();
      if (detailOS?.id === os.id) {
        viewOSDetail(os.id);
      }
    } catch (error) {
      toast.error("Erro ao atualizar status");
    }
  };

  const handleAutoApprove = async () => {
    try {
      const res = await autoApproveExpired();
      if (res.data.auto_approved > 0) {
        toast.success(`${res.data.auto_approved} OS auto-aprovadas`);
      } else {
        toast.info("Nenhuma OS expirada para auto-aprovar");
      }
      loadData();
    } catch (error) {
      toast.error("Erro ao auto-aprovar");
    }
  };

  const viewOSDetail = async (osId) => {
    const os = ordens.find(o => o.id === osId);
    if (!os) return;
    try {
      const custosRes = await getCustos({ ordem_servico_id: osId });
      setDetailCustos(custosRes.data || []);
    } catch { setDetailCustos([]); }
    setDetailOS(os);
  };

  const handleAddCusto = async (e) => {
    e.preventDefault();
    if (!custoForm.descricao || !custoForm.valor) {
      toast.error("Preencha descrição e valor");
      return;
    }
    try {
      await createCusto({
        ordem_servico_id: detailOS.id,
        tipo: custoForm.tipo,
        descricao: custoForm.descricao,
        valor: parseFloat(custoForm.valor),
        quantidade: parseFloat(custoForm.quantidade) || 1
      });
      toast.success("Custo adicionado!");
      setShowCustoModal(false);
      setCustoForm({ tipo: "consumo", descricao: "", valor: "", quantidade: "1" });
      if (detailOS) viewOSDetail(detailOS.id);
    } catch (error) {
      toast.error("Erro ao adicionar custo");
    }
  };

  const filteredOrdens = ordens.filter(os =>
    os.numero?.toString().includes(search) ||
    os.descricao?.toLowerCase().includes(search.toLowerCase())
  );

  const getEquipamentoNome = (id) => {
    const eq = equipamentos.find(e => e.id === id);
    return eq ? `${eq.codigo} - ${eq.nome}` : id;
  };

  const getNextAction = (os) => {
    const cfg = statusConfig[os.status];
    if (!cfg?.next) return null;
    if (os.status === "aberta" && !canEditOS) return null;
    if (os.status === "em_atendimento" && !canEditOS) return null;
    if (os.status === "aguardando_revisao" && !canReviewOS) return null;
    if (os.status === "revisada" && !canReviewOS) return null;
    return cfg;
  };

  return (
    <div className="space-y-6" data-testid="ordens-servico-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Wrench className="h-6 w-6 text-primary" />
            Ordens de Serviço
          </h1>
          <p className="text-muted-foreground text-sm mt-1">{ordens.length} ordens encontradas</p>
        </div>
        <div className="flex gap-2">
          {canReviewOS && pendingCount > 0 && (
            <Button variant="outline" size="sm" className="rounded-lg h-10 border-amber-500/30 text-amber-500 hover:bg-amber-500/10" onClick={handleAutoApprove}>
              <Clock className="h-4 w-4 mr-2" />
              Auto-aprovar ({pendingCount})
            </Button>
          )}
          <Button onClick={() => setShowCreateModal(true)} className="rounded-lg h-10 shadow-lg shadow-primary/20" data-testid="new-os-btn">
            <Plus className="h-4 w-4 mr-2" />
            Nova OS
          </Button>
        </div>
      </div>

      {/* Pending Reviews Banner */}
      {canReviewOS && pendingCount > 0 && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-amber-500/8 border border-amber-500/15 animate-slide-in-bottom">
          <div className="flex items-center gap-2.5">
            <Shield className="h-5 w-5 text-amber-500" />
            <span className="text-sm font-medium text-amber-600 dark:text-amber-400">
              {pendingCount} OS aguardando sua revisão (SLA: 24h)
            </span>
          </div>
          <Button size="sm" variant="outline" className="rounded-lg h-8 border-amber-500/30 text-amber-500" onClick={() => setFilterStatus("aguardando_revisao")}>
            Ver pendentes
          </Button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por número ou descrição..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 h-10 rounded-lg bg-card"
            data-testid="search-os-input"
          />
        </div>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[180px] rounded-lg h-10" data-testid="filter-status-select">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            {Object.entries(statusConfig).map(([k, v]) => (
              <SelectItem key={k} value={k}>{v.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterTipo} onValueChange={setFilterTipo}>
          <SelectTrigger className="w-[150px] rounded-lg h-10" data-testid="filter-tipo-select">
            <SelectValue placeholder="Tipo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="corretiva">Corretiva</SelectItem>
            <SelectItem value="preventiva">Preventiva</SelectItem>
            <SelectItem value="preditiva">Preditiva</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* OS Cards */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : filteredOrdens.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Wrench className="h-10 w-10 mb-3 opacity-40" />
          <p className="font-medium">Nenhuma OS encontrada</p>
        </div>
      ) : (
        <div className="space-y-3 stagger-children">
          {filteredOrdens.map((os) => {
            const sc = statusConfig[os.status] || statusConfig.aberta;
            const StatusIcon = sc.icon;
            const tc = tipoConfig[os.tipo] || tipoConfig.corretiva;
            const pc = prioridadeConfig[os.prioridade] || prioridadeConfig.media;
            const nextAction = getNextAction(os);

            return (
              <div
                key={os.id}
                className={`border border-border/50 rounded-xl bg-card p-4 card-hover group cursor-pointer transition-all ${
                  os.status === 'aguardando_revisao' ? 'border-l-4 border-l-amber-500' :
                  os.prioridade === 'critica' && os.status !== 'fechada' ? 'border-l-4 border-l-red-500' : ''
                }`}
                onClick={() => viewOSDetail(os.id)}
                data-testid={`os-row-${os.numero}`}
              >
                <div className="flex items-center gap-4">
                  {/* Number + Status */}
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-center">
                      <span className="font-mono text-lg font-bold leading-none">#{os.numero}</span>
                      {os.reincidente && (
                        <div className="mt-1">
                          <span className="text-[9px] font-bold text-orange-500 bg-orange-500/10 px-1.5 py-0.5 rounded">🔁 REINC.</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-medium truncate">
                        {os.equipamento_nome || getEquipamentoNome(os.equipamento_id)}
                      </span>
                      <Badge className={`${tc.color} text-[10px] border rounded`}>{tc.label}</Badge>
                      <Badge className={`${pc.color} text-[10px] border rounded`}>{pc.label}</Badge>
                      {!os.dentro_sla && os.status !== "fechada" && (
                        <Badge className="bg-red-500 text-white text-[10px] rounded">SLA</Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{os.descricao}</p>
                  </div>

                  {/* Downtime Cost */}
                  <div className="hidden md:flex flex-col items-end shrink-0">
                    {os.custo_parada != null && os.custo_parada > 0 ? (
                      <div className="text-right">
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <TrendingDown className="h-3 w-3 text-red-500" /> Parada
                        </span>
                        <span className="font-mono text-sm font-bold text-red-500">
                          R$ {os.custo_parada.toLocaleString('pt-BR', { minimumFractionDigits: 0 })}
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </div>

                  {/* Status + Quick Action */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge className={`${sc.color} rounded-lg px-2.5 py-1 text-xs border`}>
                      <StatusIcon className="h-3 w-3 mr-1" />
                      {sc.label}
                    </Badge>
                    {nextAction && (
                      <Button
                        size="sm"
                        className="h-8 rounded-lg text-xs px-3 shadow-sm"
                        onClick={(e) => { e.stopPropagation(); handleStatusChange(os, nextAction.next); }}
                      >
                        <ArrowRight className="h-3 w-3 mr-1" />
                        {nextAction.nextLabel}
                      </Button>
                    )}
                  </div>
                </div>

                {/* Review deadline warning */}
                {os.status === "aguardando_revisao" && os.review_deadline && (
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <Timer className="h-3 w-3 text-amber-500" />
                    <span className={`${new Date(os.review_deadline) < new Date() ? 'text-red-500 font-semibold' : 'text-amber-500'}`}>
                      Prazo revisão: {new Date(os.review_deadline).toLocaleString('pt-BR')}
                      {new Date(os.review_deadline) < new Date() && " — EXPIRADO"}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ===== OS Detail Drawer ===== */}
      {detailOS && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setDetailOS(null)}>
          <div className="bg-card border-l border-border w-full max-w-lg h-full overflow-y-auto shadow-2xl animate-slide-in-right" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-10 bg-card/95 backdrop-blur-xl border-b border-border/50 px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-heading text-xl font-bold">OS #{detailOS.numero}</span>
                  <Badge className={`${statusConfig[detailOS.status]?.color} rounded-lg text-xs border`}>
                    {statusConfig[detailOS.status]?.label}
                  </Badge>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDetailOS(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Quick Actions — LARGE BUTTONS */}
              {(() => {
                const next = getNextAction(detailOS);
                if (!next) return null;
                return (
                  <Button
                    className="w-full h-12 rounded-xl text-base font-semibold shadow-lg shadow-primary/20"
                    onClick={() => handleStatusChange(detailOS, next.next)}
                  >
                    <ArrowRight className="h-5 w-5 mr-2" />
                    {next.nextLabel} OS
                  </Button>
                );
              })()}

              {/* Info Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-muted/30">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Equipamento</p>
                  <p className="text-sm font-medium mt-1 truncate">{getEquipamentoNome(detailOS.equipamento_id)}</p>
                </div>
                <div className="p-3 rounded-xl bg-muted/30">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Tipo</p>
                  <Badge className={`${tipoConfig[detailOS.tipo]?.color} text-xs border rounded mt-1`}>
                    {tipoConfig[detailOS.tipo]?.label}
                  </Badge>
                </div>
                <div className="p-3 rounded-xl bg-muted/30">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Prioridade</p>
                  <Badge className={`${prioridadeConfig[detailOS.prioridade]?.color} text-xs border rounded mt-1`}>
                    {prioridadeConfig[detailOS.prioridade]?.label}
                  </Badge>
                </div>
                <div className="p-3 rounded-xl bg-muted/30">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">SLA</p>
                  <Badge className={`text-xs border rounded mt-1 ${detailOS.dentro_sla ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-red-500/10 text-red-500 border-red-500/20'}`}>
                    {detailOS.dentro_sla ? '✅ Dentro' : '❌ Fora'}
                  </Badge>
                </div>
              </div>

              {/* Recurrence Warning */}
              {detailOS.reincidente && (
                <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-orange-500/8 border border-orange-500/15">
                  <AlertTriangle className="h-5 w-5 text-orange-500" />
                  <div>
                    <p className="text-sm font-semibold text-orange-600 dark:text-orange-400">Falha Reincidente</p>
                    <p className="text-xs text-muted-foreground">Mesma falha detectada nos últimos 30 dias</p>
                  </div>
                </div>
              )}

              {/* Description */}
              <div>
                <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1">Descrição</p>
                <p className="text-sm leading-relaxed">{detailOS.descricao}</p>
              </div>

              {detailOS.solucao && (
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1">Solução</p>
                  <p className="text-sm leading-relaxed">{detailOS.solucao}</p>
                </div>
              )}

              {/* Downtime Cost */}
              {detailOS.custo_parada != null && detailOS.custo_parada > 0 && (
                <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/15">
                  <p className="text-xs font-semibold text-red-500 flex items-center gap-1.5 mb-2">
                    <TrendingDown className="h-4 w-4" /> Impacto Financeiro (Máquina Parada)
                  </p>
                  <p className="text-2xl font-heading font-bold text-red-500">
                    R$ {detailOS.custo_parada.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </p>
                  {detailOS.tempo_total && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {(detailOS.tempo_total / 60).toFixed(1)}h de máquina parada
                    </p>
                  )}
                </div>
              )}

              {/* Review Section */}
              {(detailOS.status === "aguardando_revisao" || detailOS.status === "revisada") && (
                <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/15 space-y-2">
                  <p className="text-xs font-semibold text-amber-500 flex items-center gap-1.5">
                    <Shield className="h-4 w-4" /> Revisão de Qualidade
                  </p>
                  {detailOS.revisor_nome && (
                    <p className="text-sm"><span className="text-muted-foreground">Revisor:</span> {detailOS.revisor_nome}</p>
                  )}
                  {detailOS.review_deadline && (
                    <p className="text-sm">
                      <span className="text-muted-foreground">Prazo:</span>{" "}
                      {new Date(detailOS.review_deadline).toLocaleString('pt-BR')}
                      {detailOS.status === "aguardando_revisao" && new Date(detailOS.review_deadline) < new Date() && (
                        <Badge className="ml-2 bg-red-500/10 text-red-500 text-[10px] rounded border border-red-500/20">Expirado</Badge>
                      )}
                    </p>
                  )}
                  {detailOS.auto_approved && (
                    <Badge className="bg-amber-500/10 text-amber-500 text-[10px] rounded border border-amber-500/20">Auto-aprovada (24h expirado)</Badge>
                  )}
                  {detailOS.review_notes && (
                    <p className="text-sm"><span className="text-muted-foreground">Notas:</span> {detailOS.review_notes}</p>
                  )}
                </div>
              )}

              {/* Failure Analysis */}
              {detailOS.tipo === "corretiva" && (detailOS.falha_tipo || detailOS.falha_modo || detailOS.falha_causa) && (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Tipo Falha", value: detailOS.falha_tipo },
                    { label: "Modo", value: detailOS.falha_modo },
                    { label: "Causa", value: detailOS.falha_causa },
                  ].map((f, i) => (
                    <div key={i} className="p-3 bg-muted/30 rounded-xl">
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">{f.label}</p>
                      <p className="text-sm mt-0.5">{f.value || '—'}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Timing */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Resposta", value: detailOS.tempo_resposta ? `${detailOS.tempo_resposta} min` : '—' },
                  { label: "Reparo", value: detailOS.tempo_reparo ? `${detailOS.tempo_reparo} min` : '—' },
                  { label: "Total", value: detailOS.tempo_total ? `${detailOS.tempo_total} min` : '—' },
                ].map((t, i) => (
                  <div key={i} className="p-3 bg-muted/30 rounded-xl text-center">
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">{t.label}</p>
                    <p className="text-lg font-heading font-bold mt-1">{t.value}</p>
                  </div>
                ))}
              </div>

              {/* Costs */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Custos</p>
                  {canEditOS && detailOS.status !== "fechada" && (
                    <Button size="sm" variant="outline" className="h-7 rounded-lg text-xs" onClick={() => setShowCustoModal(true)}>
                      <Plus className="h-3 w-3 mr-1" /> Adicionar
                    </Button>
                  )}
                </div>
                {detailCustos.length > 0 ? (
                  <div className="space-y-2">
                    {detailCustos.map((c) => (
                      <div key={c.id} className="flex items-center justify-between p-2.5 rounded-lg bg-muted/30">
                        <div>
                          <Badge className="text-[10px] rounded mb-0.5">{c.tipo}</Badge>
                          <p className="text-xs">{c.descricao}</p>
                        </div>
                        <span className="font-mono text-sm font-semibold">
                          R$ {(c.valor * c.quantidade).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    ))}
                    <div className="flex justify-between p-3 rounded-xl bg-muted/50 font-semibold text-sm">
                      <span>Total Manutenção</span>
                      <span className="font-mono">
                        R$ {detailCustos.reduce((a, c) => a + c.valor * c.quantidade, 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    {detailOS.custo_parada != null && detailOS.custo_parada > 0 && (
                      <div className="flex justify-between p-3 rounded-xl bg-primary/5 border border-primary/10 font-bold text-sm">
                        <span>Impacto Total</span>
                        <span className="font-mono text-primary">
                          R$ {(detailCustos.reduce((a, c) => a + c.valor * c.quantidade, 0) + detailOS.custo_parada).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground text-center py-4">Nenhum custo registrado</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===== Create OS Modal ===== */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setShowCreateModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-lg shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-heading font-bold text-lg">Nova Ordem de Serviço</h2>
              <Button variant="ghost" size="icon" onClick={() => setShowCreateModal(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label>Equipamento *</Label>
                <Select value={formData.equipamento_id} onValueChange={(v) => setFormData({ ...formData, equipamento_id: v })}>
                  <SelectTrigger className="rounded-lg h-10" data-testid="os-equipamento-select">
                    <SelectValue placeholder="Selecione" />
                  </SelectTrigger>
                  <SelectContent>
                    {equipamentos.map((eq) => (
                      <SelectItem key={eq.id} value={eq.id}>{eq.codigo} - {eq.nome}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {Object.entries(tipoConfig).map(([k, v]) => (
                      <button key={k} type="button"
                        className={`text-xs px-2 py-2 rounded-lg border transition-all font-medium ${formData.tipo === k ? 'bg-primary text-primary-foreground border-primary' : 'border-border bg-muted/50 hover:bg-muted'}`}
                        onClick={() => setFormData({ ...formData, tipo: k })}
                      >{v.label}</button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Prioridade</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {Object.entries(prioridadeConfig).map(([k, v]) => (
                      <button key={k} type="button"
                        className={`text-xs px-2 py-2 rounded-lg border transition-all font-medium ${formData.prioridade === k ? 'bg-primary text-primary-foreground border-primary' : 'border-border bg-muted/50 hover:bg-muted'}`}
                        onClick={() => setFormData({ ...formData, prioridade: k })}
                      >{v.label}</button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Descrição *</Label>
                <Textarea
                  value={formData.descricao}
                  onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                  placeholder="Descreva o problema ou serviço"
                  className="rounded-lg"
                  rows={3}
                  data-testid="os-descricao-input"
                />
              </div>

              {formData.tipo === "corretiva" && (
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { key: "falha_tipo", label: "Tipo Falha", ph: "Mecânica" },
                    { key: "falha_modo", label: "Modo", ph: "Desgaste" },
                    { key: "falha_causa", label: "Causa", ph: "Uso" },
                  ].map((f) => (
                    <div key={f.key} className="space-y-1">
                      <Label className="text-xs">{f.label}</Label>
                      <Input
                        value={formData[f.key]}
                        onChange={(e) => setFormData({ ...formData, [f.key]: e.target.value })}
                        placeholder={f.ph}
                        className="rounded-lg h-9 text-xs"
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2 pt-2">
                <Button type="button" variant="outline" className="flex-1 rounded-lg" onClick={() => setShowCreateModal(false)}>Cancelar</Button>
                <Button type="submit" className="flex-1 rounded-lg" disabled={creating} data-testid="save-os-btn">
                  {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}
                  Criar OS
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Add Cost Modal ===== */}
      {showCustoModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setShowCustoModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-heading font-bold mb-4">Adicionar Custo</h3>
            <form onSubmit={handleAddCusto} className="space-y-3">
              <div className="space-y-1">
                <Label className="text-xs">Tipo</Label>
                <Select value={custoForm.tipo} onValueChange={(v) => setCustoForm({ ...custoForm, tipo: v })}>
                  <SelectTrigger className="rounded-lg h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="consumo">Consumo</SelectItem>
                    <SelectItem value="substituicao">Substituição</SelectItem>
                    <SelectItem value="mao_obra">Mão de Obra</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Descrição *</Label>
                <Input value={custoForm.descricao} onChange={(e) => setCustoForm({ ...custoForm, descricao: e.target.value })} className="rounded-lg h-9" placeholder="Ex: Rolamento" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-xs">Valor (R$) *</Label>
                  <Input type="number" step="0.01" value={custoForm.valor} onChange={(e) => setCustoForm({ ...custoForm, valor: e.target.value })} className="rounded-lg h-9" placeholder="100" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Qtd</Label>
                  <Input type="number" value={custoForm.quantidade} onChange={(e) => setCustoForm({ ...custoForm, quantidade: e.target.value })} className="rounded-lg h-9" />
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <Button type="button" variant="outline" className="flex-1 rounded-lg h-9" onClick={() => setShowCustoModal(false)}>Cancelar</Button>
                <Button type="submit" className="flex-1 rounded-lg h-9">Salvar</Button>
              </div>
            </form>
          </div>
        </div>
      )}

      <UpgradeDialog open={upgradeOpen} onClose={closeUpgrade} message={upgradeMessage} />
    </div>
  );
}
