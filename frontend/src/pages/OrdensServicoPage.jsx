import { useState, useEffect } from "react";
import { getOrdensServico, createOrdemServico, updateOrdemServico, getEquipamentos, getGrupos, getCustos, createCusto } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";
import {
  Plus,
  Search,
  Wrench,
  Clock,
  AlertTriangle,
  CheckCircle,
  Eye,
  Play,
  FileCheck,
  DollarSign,
  Filter
} from "lucide-react";

const statusConfig = {
  aberta: { label: "Aberta", color: "status-aberta", icon: AlertTriangle },
  em_atendimento: { label: "Em Atendimento", color: "status-em-atendimento", icon: Wrench },
  aguardando_revisao: { label: "Aguardando Revisão", color: "status-aguardando-revisao", icon: Clock },
  revisada: { label: "Revisada", color: "status-revisada", icon: CheckCircle },
  fechada: { label: "Fechada", color: "status-fechada", icon: FileCheck }
};

const prioridadeConfig = {
  baixa: { label: "Baixa", color: "priority-baixa" },
  media: { label: "Média", color: "priority-media" },
  alta: { label: "Alta", color: "priority-alta" },
  critica: { label: "Crítica", color: "priority-critica" }
};

const tipoConfig = {
  corretiva: { label: "Corretiva", color: "bg-red-500/10 text-red-600 dark:text-red-400" },
  preventiva: { label: "Preventiva", color: "bg-green-500/10 text-green-600 dark:text-green-400" },
  preditiva: { label: "Preditiva", color: "bg-blue-500/10 text-blue-600 dark:text-blue-400" }
};

export default function OrdensServicoPage() {
  const { user } = useAuth();
  const [ordens, setOrdens] = useState([]);
  const [equipamentos, setEquipamentos] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterTipo, setFilterTipo] = useState("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [detailDialog, setDetailDialog] = useState({ open: false, os: null, custos: [] });
  const [custoDialog, setCustoDialog] = useState({ open: false, os_id: null });
  
  const [formData, setFormData] = useState({
    equipamento_id: "",
    tipo: "corretiva",
    prioridade: "media",
    descricao: "",
    falha_tipo: "",
    falha_modo: "",
    falha_causa: ""
  });

  const [custoForm, setCustoForm] = useState({
    tipo: "consumo",
    descricao: "",
    valor: "",
    quantidade: "1"
  });

  const canCreateOS = true; // Todos podem criar OS
  const canEditOS = user?.role === "admin" || user?.role === "lider" || user?.role === "tecnico";
  const canReviewOS = user?.role === "admin" || user?.role === "lider";

  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterStatus && filterStatus !== "all") params.status = filterStatus;
      if (filterTipo && filterTipo !== "all") params.tipo = filterTipo;
      
      const [osRes, eqRes, grRes] = await Promise.all([
        getOrdensServico(params),
        getEquipamentos(),
        getGrupos()
      ]);
      console.log("OS data loaded:", osRes.data?.length, "orders");
      setOrdens(osRes.data || []);
      setEquipamentos(eqRes.data || []);
      setGrupos(grRes.data || []);
    } catch (error) {
      console.error("Error loading OS:", error);
      toast.error("Erro ao carregar ordens de serviço");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [filterStatus, filterTipo]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.equipamento_id || !formData.descricao) {
      toast.error("Preencha equipamento e descrição");
      return;
    }
    try {
      await createOrdemServico(formData);
      toast.success("OS criada com sucesso");
      setDialogOpen(false);
      setFormData({
        equipamento_id: "",
        tipo: "corretiva",
        prioridade: "media",
        descricao: "",
        falha_tipo: "",
        falha_modo: "",
        falha_causa: ""
      });
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao criar OS");
    }
  };

  const handleStatusChange = async (os, newStatus) => {
    try {
      await updateOrdemServico(os.id, { status: newStatus });
      toast.success("Status atualizado");
      loadData();
      if (detailDialog.open) {
        viewOSDetail(os.id);
      }
    } catch (error) {
      toast.error("Erro ao atualizar status");
    }
  };

  const viewOSDetail = async (osId) => {
    const os = ordens.find(o => o.id === osId);
    try {
      const custosRes = await getCustos({ ordem_servico_id: osId });
      setDetailDialog({ open: true, os, custos: custosRes.data });
    } catch (error) {
      setDetailDialog({ open: true, os, custos: [] });
    }
  };

  const handleAddCusto = async (e) => {
    e.preventDefault();
    if (!custoForm.descricao || !custoForm.valor) {
      toast.error("Preencha descrição e valor");
      return;
    }
    try {
      await createCusto({
        ordem_servico_id: custoDialog.os_id,
        tipo: custoForm.tipo,
        descricao: custoForm.descricao,
        valor: parseFloat(custoForm.valor),
        quantidade: parseFloat(custoForm.quantidade) || 1
      });
      toast.success("Custo adicionado");
      setCustoDialog({ open: false, os_id: null });
      setCustoForm({ tipo: "consumo", descricao: "", valor: "", quantidade: "1" });
      if (detailDialog.open) {
        viewOSDetail(detailDialog.os.id);
      }
    } catch (error) {
      toast.error("Erro ao adicionar custo");
    }
  };

  const filteredOrdens = ordens.filter(os => 
    os.numero.toString().includes(search) ||
    os.descricao.toLowerCase().includes(search.toLowerCase())
  );

  const getEquipamentoNome = (id) => {
    const eq = equipamentos.find(e => e.id === id);
    return eq ? `${eq.codigo} - ${eq.nome}` : id;
  };

  return (
    <div className="space-y-6" data-testid="ordens-servico-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold">Ordens de Serviço</h1>
          <p className="text-muted-foreground">{ordens.length} ordens encontradas</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-sm" data-testid="new-os-btn">
              <Plus className="h-4 w-4 mr-2" />
              Nova OS
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-heading">Nova Ordem de Serviço</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="equipamento">Equipamento *</Label>
                <Select
                  value={formData.equipamento_id}
                  onValueChange={(v) => setFormData({ ...formData, equipamento_id: v })}
                >
                  <SelectTrigger className="rounded-sm" data-testid="os-equipamento-select">
                    <SelectValue placeholder="Selecione o equipamento" />
                  </SelectTrigger>
                  <SelectContent>
                    {equipamentos.map((eq) => (
                      <SelectItem key={eq.id} value={eq.id}>
                        {eq.codigo} - {eq.nome}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select
                    value={formData.tipo}
                    onValueChange={(v) => setFormData({ ...formData, tipo: v })}
                  >
                    <SelectTrigger className="rounded-sm" data-testid="os-tipo-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="corretiva">Corretiva</SelectItem>
                      <SelectItem value="preventiva">Preventiva</SelectItem>
                      <SelectItem value="preditiva">Preditiva</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Prioridade</Label>
                  <Select
                    value={formData.prioridade}
                    onValueChange={(v) => setFormData({ ...formData, prioridade: v })}
                  >
                    <SelectTrigger className="rounded-sm" data-testid="os-prioridade-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="baixa">Baixa</SelectItem>
                      <SelectItem value="media">Média</SelectItem>
                      <SelectItem value="alta">Alta</SelectItem>
                      <SelectItem value="critica">Crítica</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="descricao">Descrição *</Label>
                <Textarea
                  id="descricao"
                  value={formData.descricao}
                  onChange={(e) => setFormData({ ...formData, descricao: e.target.value })}
                  placeholder="Descreva o problema ou serviço necessário"
                  className="rounded-sm"
                  rows={3}
                  data-testid="os-descricao-input"
                />
              </div>

              {formData.tipo === "corretiva" && (
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-2">
                    <Label className="text-xs">Tipo de Falha</Label>
                    <Input
                      value={formData.falha_tipo}
                      onChange={(e) => setFormData({ ...formData, falha_tipo: e.target.value })}
                      placeholder="Mecânica"
                      className="rounded-sm text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Modo de Falha</Label>
                    <Input
                      value={formData.falha_modo}
                      onChange={(e) => setFormData({ ...formData, falha_modo: e.target.value })}
                      placeholder="Desgaste"
                      className="rounded-sm text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Causa</Label>
                    <Input
                      value={formData.falha_causa}
                      onChange={(e) => setFormData({ ...formData, falha_causa: e.target.value })}
                      placeholder="Uso"
                      className="rounded-sm text-sm"
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setDialogOpen(false)} className="rounded-sm">
                  Cancelar
                </Button>
                <Button type="submit" className="rounded-sm" data-testid="save-os-btn">
                  Criar OS
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por número ou descrição..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 rounded-sm"
            data-testid="search-os-input"
          />
        </div>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[180px] rounded-sm" data-testid="filter-status-select">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="aberta">Aberta</SelectItem>
            <SelectItem value="em_atendimento">Em Atendimento</SelectItem>
            <SelectItem value="aguardando_revisao">Aguardando Revisão</SelectItem>
            <SelectItem value="revisada">Revisada</SelectItem>
            <SelectItem value="fechada">Fechada</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filterTipo} onValueChange={setFilterTipo}>
          <SelectTrigger className="w-[150px] rounded-sm" data-testid="filter-tipo-select">
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

      {/* Table */}
      <div className="border border-border rounded-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full table-dense">
            <thead className="bg-muted">
              <tr>
                <th className="text-left font-medium p-3">Nº</th>
                <th className="text-left font-medium p-3">Equipamento</th>
                <th className="text-center font-medium p-3">Tipo</th>
                <th className="text-center font-medium p-3">Prioridade</th>
                <th className="text-center font-medium p-3">Status</th>
                <th className="text-left font-medium p-3 hidden lg:table-cell">Data</th>
                <th className="text-right font-medium p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center p-8 text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : filteredOrdens.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center p-8 text-muted-foreground">
                    Nenhuma OS encontrada
                  </td>
                </tr>
              ) : (
                filteredOrdens.map((os) => (
                  <tr key={os.id} className="border-t border-border hover:bg-muted/50" data-testid={`os-row-${os.numero}`}>
                    <td className="p-3">
                      <span className="font-mono font-medium">#{os.numero}</span>
                      {os.reincidente && (
                        <Badge className="ml-2 bg-orange-500/10 text-orange-600 rounded-sm text-xs">
                          Reincidente
                        </Badge>
                      )}
                    </td>
                    <td className="p-3">
                      <div className="text-sm truncate max-w-[200px]">{getEquipamentoNome(os.equipamento_id)}</div>
                      <div className="text-xs text-muted-foreground truncate max-w-[200px]">{os.descricao}</div>
                    </td>
                    <td className="p-3 text-center">
                      <Badge className={`${tipoConfig[os.tipo]?.color} rounded-sm`}>
                        {tipoConfig[os.tipo]?.label}
                      </Badge>
                    </td>
                    <td className="p-3 text-center">
                      <Badge className={`${prioridadeConfig[os.prioridade]?.color} rounded-sm`}>
                        {prioridadeConfig[os.prioridade]?.label}
                      </Badge>
                    </td>
                    <td className="p-3 text-center">
                      <Badge className={`${statusConfig[os.status]?.color} rounded-sm`}>
                        {statusConfig[os.status]?.label}
                      </Badge>
                      {!os.dentro_sla && os.status !== "fechada" && (
                        <Badge className="ml-1 bg-red-500 text-white rounded-sm text-xs">SLA</Badge>
                      )}
                    </td>
                    <td className="p-3 hidden lg:table-cell text-sm text-muted-foreground">
                      {new Date(os.created_at).toLocaleDateString('pt-BR')}
                    </td>
                    <td className="p-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => viewOSDetail(os.id)}
                          data-testid={`view-os-${os.numero}`}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {canEditOS && os.status === "aberta" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleStatusChange(os, "em_atendimento")}
                            data-testid={`start-os-${os.numero}`}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Dialog */}
      <Dialog open={detailDialog.open} onOpenChange={(open) => setDetailDialog({ open, os: null, custos: [] })}>
        <DialogContent className="rounded-sm max-w-2xl max-h-[85vh] overflow-y-auto">
          {detailDialog.os && (
            <>
              <DialogHeader>
                <DialogTitle className="font-heading flex items-center gap-2">
                  OS #{detailDialog.os.numero}
                  <Badge className={`${statusConfig[detailDialog.os.status]?.color} rounded-sm`}>
                    {statusConfig[detailDialog.os.status]?.label}
                  </Badge>
                </DialogTitle>
              </DialogHeader>

              <Tabs defaultValue="info" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="info">Informações</TabsTrigger>
                  <TabsTrigger value="tempos">Tempos</TabsTrigger>
                  <TabsTrigger value="custos">Custos</TabsTrigger>
                </TabsList>

                <TabsContent value="info" className="space-y-4 mt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Equipamento</p>
                      <p className="font-medium">{getEquipamentoNome(detailDialog.os.equipamento_id)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Tipo</p>
                      <Badge className={`${tipoConfig[detailDialog.os.tipo]?.color} rounded-sm`}>
                        {tipoConfig[detailDialog.os.tipo]?.label}
                      </Badge>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Prioridade</p>
                      <Badge className={`${prioridadeConfig[detailDialog.os.prioridade]?.color} rounded-sm`}>
                        {prioridadeConfig[detailDialog.os.prioridade]?.label}
                      </Badge>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">SLA</p>
                      <Badge className={`rounded-sm ${detailDialog.os.dentro_sla ? 'bg-green-500/10 text-green-600' : 'bg-red-500/10 text-red-600'}`}>
                        {detailDialog.os.dentro_sla ? 'Dentro do SLA' : 'Fora do SLA'}
                      </Badge>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground">Descrição</p>
                    <p className="mt-1">{detailDialog.os.descricao}</p>
                  </div>

                  {detailDialog.os.solucao && (
                    <div>
                      <p className="text-xs text-muted-foreground">Solução</p>
                      <p className="mt-1">{detailDialog.os.solucao}</p>
                    </div>
                  )}

                  {detailDialog.os.tipo === "corretiva" && (detailDialog.os.falha_tipo || detailDialog.os.falha_modo || detailDialog.os.falha_causa) && (
                    <div className="grid grid-cols-3 gap-4 p-3 bg-muted rounded-sm">
                      <div>
                        <p className="text-xs text-muted-foreground">Tipo de Falha</p>
                        <p className="text-sm">{detailDialog.os.falha_tipo || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Modo</p>
                        <p className="text-sm">{detailDialog.os.falha_modo || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Causa</p>
                        <p className="text-sm">{detailDialog.os.falha_causa || '-'}</p>
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex flex-wrap gap-2 pt-4 border-t border-border">
                    {canEditOS && detailDialog.os.status === "aberta" && (
                      <Button size="sm" onClick={() => handleStatusChange(detailDialog.os, "em_atendimento")} className="rounded-sm">
                        <Play className="h-4 w-4 mr-2" />
                        Iniciar Atendimento
                      </Button>
                    )}
                    {canEditOS && detailDialog.os.status === "em_atendimento" && (
                      <Button size="sm" onClick={() => handleStatusChange(detailDialog.os, "aguardando_revisao")} className="rounded-sm">
                        <Clock className="h-4 w-4 mr-2" />
                        Enviar para Revisão
                      </Button>
                    )}
                    {canReviewOS && detailDialog.os.status === "aguardando_revisao" && (
                      <Button size="sm" onClick={() => handleStatusChange(detailDialog.os, "revisada")} className="rounded-sm">
                        <CheckCircle className="h-4 w-4 mr-2" />
                        Aprovar Revisão
                      </Button>
                    )}
                    {canReviewOS && detailDialog.os.status === "revisada" && (
                      <Button size="sm" onClick={() => handleStatusChange(detailDialog.os, "fechada")} className="rounded-sm">
                        <FileCheck className="h-4 w-4 mr-2" />
                        Fechar OS
                      </Button>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="tempos" className="space-y-4 mt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 border border-border rounded-sm">
                      <p className="text-xs text-muted-foreground">Abertura</p>
                      <p className="font-medium">{new Date(detailDialog.os.created_at).toLocaleString('pt-BR')}</p>
                    </div>
                    {detailDialog.os.inicio_atendimento && (
                      <div className="p-3 border border-border rounded-sm">
                        <p className="text-xs text-muted-foreground">Início Atendimento</p>
                        <p className="font-medium">{new Date(detailDialog.os.inicio_atendimento).toLocaleString('pt-BR')}</p>
                      </div>
                    )}
                    {detailDialog.os.fim_atendimento && (
                      <div className="p-3 border border-border rounded-sm">
                        <p className="text-xs text-muted-foreground">Fim Atendimento</p>
                        <p className="font-medium">{new Date(detailDialog.os.fim_atendimento).toLocaleString('pt-BR')}</p>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="p-3 bg-muted rounded-sm text-center">
                      <p className="text-xs text-muted-foreground">Tempo Resposta</p>
                      <p className="text-xl font-heading font-bold">
                        {detailDialog.os.tempo_resposta ? `${detailDialog.os.tempo_resposta} min` : '-'}
                      </p>
                    </div>
                    <div className="p-3 bg-muted rounded-sm text-center">
                      <p className="text-xs text-muted-foreground">Tempo Reparo</p>
                      <p className="text-xl font-heading font-bold">
                        {detailDialog.os.tempo_reparo ? `${detailDialog.os.tempo_reparo} min` : '-'}
                      </p>
                    </div>
                    <div className="p-3 bg-muted rounded-sm text-center">
                      <p className="text-xs text-muted-foreground">Tempo Total</p>
                      <p className="text-xl font-heading font-bold">
                        {detailDialog.os.tempo_total ? `${detailDialog.os.tempo_total} min` : '-'}
                      </p>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="custos" className="space-y-4 mt-4">
                  {canEditOS && detailDialog.os.status !== "fechada" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setCustoDialog({ open: true, os_id: detailDialog.os.id })}
                      className="rounded-sm"
                      data-testid="add-custo-btn"
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      Adicionar Custo
                    </Button>
                  )}

                  {detailDialog.custos.length === 0 ? (
                    <p className="text-muted-foreground text-center py-4">Nenhum custo registrado</p>
                  ) : (
                    <div className="space-y-2">
                      {detailDialog.custos.map((custo) => (
                        <div key={custo.id} className="flex items-center justify-between p-3 border border-border rounded-sm">
                          <div>
                            <Badge className="rounded-sm text-xs mb-1">{custo.tipo}</Badge>
                            <p className="text-sm">{custo.descricao}</p>
                          </div>
                          <div className="text-right">
                            <p className="font-heading font-bold">
                              R$ {(custo.valor * custo.quantidade).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {custo.quantidade} x R$ {custo.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                            </p>
                          </div>
                        </div>
                      ))}
                      <div className="flex justify-between p-3 bg-muted rounded-sm">
                        <p className="font-medium">Total</p>
                        <p className="font-heading font-bold">
                          R$ {detailDialog.custos.reduce((acc, c) => acc + c.valor * c.quantidade, 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </p>
                      </div>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Custo Dialog */}
      <Dialog open={custoDialog.open} onOpenChange={(open) => setCustoDialog({ open, os_id: null })}>
        <DialogContent className="rounded-sm">
          <DialogHeader>
            <DialogTitle className="font-heading">Adicionar Custo</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddCusto} className="space-y-4">
            <div className="space-y-2">
              <Label>Tipo de Custo</Label>
              <Select
                value={custoForm.tipo}
                onValueChange={(v) => setCustoForm({ ...custoForm, tipo: v })}
              >
                <SelectTrigger className="rounded-sm" data-testid="custo-tipo-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="consumo">Consumo</SelectItem>
                  <SelectItem value="substituicao">Substituição</SelectItem>
                  <SelectItem value="mao_obra">Mão de Obra</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="custo_descricao">Descrição *</Label>
              <Input
                id="custo_descricao"
                value={custoForm.descricao}
                onChange={(e) => setCustoForm({ ...custoForm, descricao: e.target.value })}
                placeholder="Descrição do custo"
                className="rounded-sm"
                data-testid="custo-descricao-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="custo_valor">Valor Unitário (R$) *</Label>
                <Input
                  id="custo_valor"
                  type="number"
                  step="0.01"
                  value={custoForm.valor}
                  onChange={(e) => setCustoForm({ ...custoForm, valor: e.target.value })}
                  placeholder="100.00"
                  className="rounded-sm"
                  data-testid="custo-valor-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="custo_quantidade">Quantidade</Label>
                <Input
                  id="custo_quantidade"
                  type="number"
                  step="1"
                  value={custoForm.quantidade}
                  onChange={(e) => setCustoForm({ ...custoForm, quantidade: e.target.value })}
                  className="rounded-sm"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setCustoDialog({ open: false, os_id: null })} className="rounded-sm">
                Cancelar
              </Button>
              <Button type="submit" className="rounded-sm" data-testid="save-custo-btn">
                Salvar
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
