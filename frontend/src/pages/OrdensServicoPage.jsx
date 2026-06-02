import { useState, useEffect } from "react";
import {
  getOrdensServico, createOrdemServico, updateOrdemServico, getEquipamentos,
  getCustos, createCusto, deleteCusto, getPendingReviews, autoApproveExpired, buscarPorCracha,
  getOSEquipe, addOSEquipeMembro, removeOSEquipeMembro, getOSHistorico,
} from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { useAuth } from "../contexts/AuthContext";
import { useFinancialAccess, BlurredMoney } from "../components/shared/FinancialGuard";
import UpgradeDialog from "../components/UpgradeDialog";
import { useUpgradeDialog } from "../hooks/useUpgradeDialog";
import {
  Plus, Search, Wrench, Clock, AlertTriangle, CheckCircle,
  FileCheck, Filter, X, Loader2, TrendingDown, Shield,
  ArrowRight, Timer, Zap, Ban, UserCheck, UserX, Users,
  Trash2, Activity, HardHat, ClipboardCheck,
} from "lucide-react";

// ─── Configurações ────────────────────────────────────────────────────────────

const statusConfig = {
  aberta:             { label: "Aberta",          color: "status-aberta",             icon: AlertTriangle, next: "em_atendimento",   nextLabel: "Iniciar" },
  em_atendimento:     { label: "Em Atendimento",  color: "status-em-atendimento",     icon: Wrench,        next: "aguardando_revisao", nextLabel: "Concluir",
    alts: [{ next: "aguardando_peca", nextLabel: "Aguardar Peça" }] },
  aguardando_peca:    { label: "Ag. Peça",        color: "status-aguardando-peca",    icon: Clock,         next: "em_atendimento",   nextLabel: "Retomar"  },
  aguardando_revisao: { label: "Ag. Revisão",     color: "status-aguardando-revisao", icon: Clock,         next: "revisada",         nextLabel: "Aprovar"  },
  revisada:           { label: "Revisada",         color: "status-revisada",           icon: CheckCircle,   next: "fechada",          nextLabel: "Fechar"   },
  fechada:            { label: "Fechada",          color: "status-fechada",            icon: FileCheck },
};

const prioridadeConfig = {
  baixa:   { label: "Baixa",   color: "priority-baixa"   },
  media:   { label: "Média",   color: "priority-media"   },
  alta:    { label: "Alta",    color: "priority-alta"    },
  critica: { label: "Crítica", color: "priority-critica" },
};

const tipoConfig = {
  corretiva:  { label: "Corretiva",  color: "bg-red-500/10 text-red-500 border-red-500/20"              },
  preventiva: { label: "Preventiva", color: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"  },
  preditiva:  { label: "Preditiva",  color: "bg-blue-500/10 text-blue-500 border-blue-500/20"           },
};

const FAILURE_GROUPS = [
  { value: "eletrico",       label: "Elétrico",       color: "#3B82F6" },
  { value: "hidraulico",     label: "Hidráulico",     color: "#F59E0B" },
  { value: "mecanico",       label: "Mecânico",       color: "#6B7280" },
  { value: "pneumatico",     label: "Pneumático",     color: "#0D9488" },
  { value: "instrumentacao", label: "Instrumentação", color: "#8B5CF6" },
  { value: "estrutural",     label: "Estrutural",     color: "#FB923C" },
  { value: "outro",          label: "Outro",          color: "#64748B" },
];

const ESPECIALIDADES = [
  { value: "eletrica",       label: "Elétrica",           Icon: Zap,      color: "#3B82F6" },
  { value: "mecanica",       label: "Mecânica",           Icon: Wrench,   color: "#6B7280" },
  { value: "civil",          label: "Civil / Infraestrutura", Icon: HardHat, color: "#FB923C" },
  { value: "instrumentacao", label: "Instrumentação",     Icon: Activity, color: "#8B5CF6" },
  { value: "ti",             label: "TI / Automação",     Icon: Zap,      color: "#0D9488" },
  { value: "outro",          label: "Outro",              Icon: Wrench,   color: "#64748B" },
];

// Config de cor por etapa para a timeline
const HISTORICO_CONFIG = {
  aberta:             { color: "#3B82F6", dot: "bg-blue-500",    line: "border-blue-200 dark:border-blue-900" },
  em_atendimento:     { color: "#F59E0B", dot: "bg-amber-500",   line: "border-amber-200 dark:border-amber-900" },
  aguardando_peca:    { color: "#F97316", dot: "bg-orange-500",  line: "border-orange-200 dark:border-orange-900" },
  aguardando_revisao: { color: "#F59E0B", dot: "bg-amber-500",   line: "border-amber-200 dark:border-amber-900" },
  revisada:           { color: "#10B981", dot: "bg-emerald-500", line: "border-emerald-200 dark:border-emerald-900" },
  fechada:            { color: "#10B981", dot: "bg-emerald-500", line: "border-emerald-200 dark:border-emerald-900" },
  cancelada:          { color: "#EF4444", dot: "bg-red-500",     line: "border-red-200 dark:border-red-900" },
};

const STATUS_LABELS_MAP = {
  aberta: "Aberta", em_atendimento: "Em Atendimento",
  aguardando_peca: "Ag. Peça", aguardando_revisao: "Ag. Revisão", revisada: "Revisada",
};

const STATUSES_EM_ATENDIMENTO = ["em_atendimento", "aguardando_peca", "aguardando_revisao", "revisada", "fechada"];

const GRUPO_PRODUCAO  = ["operador", "lider_producao", "supervisor_producao", "lider"];
const GRUPO_MANUTENCAO = [
  "tecnico", "lider_manutencao_eletrica", "lider_manutencao_mecanica",
  "supervisor_manutencao", "analista_manutencao", "engenheiro_manutencao", "gerente_industrial",
];

const getEspecialidadeInfo = (val) => ESPECIALIDADES.find((e) => e.value === val) || ESPECIALIDADES.find((e) => e.value === "outro");

// ─── BloqueioModal ────────────────────────────────────────────────────────────
function BloqueioModal({ data, onClose, onConfirm }) {
  const [selectedGroup, setSelectedGroup] = useState(data.grupos_disponiveis?.[0] || "");
  const getLabel = (val) => FAILURE_GROUPS.find((g) => g.value === val)?.label || val;
  const getColor = (val) => FAILURE_GROUPS.find((g) => g.value === val)?.color || "#64748B";
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-2xl" onClick={(e) => e.stopPropagation()} data-testid="bloqueio-modal">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0"><Ban className="h-5 w-5 text-amber-500" /></div>
          <div>
            <h3 className="font-heading font-bold text-base">Bloqueio por Grupo de Falha</h3>
            <p className="text-xs text-muted-foreground">Já existe uma OS aberta neste grupo para o equipamento</p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mb-4 leading-relaxed">{data.message}</p>
        {data.os_bloqueante && (
          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 mb-4">
            <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1.5">OS bloqueante</p>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono font-bold text-sm">#{data.os_bloqueante.numero}</span>
              <Badge className="text-[10px] rounded border bg-amber-500/10 text-amber-500 border-amber-500/20">{STATUS_LABELS_MAP[data.os_bloqueante.status] || data.os_bloqueante.status}</Badge>
              <span className="text-xs text-muted-foreground">[{getLabel(data.os_bloqueante.failure_group)}]</span>
            </div>
          </div>
        )}
        {data.grupos_disponiveis?.length > 0 ? (
          <div className="mb-6">
            <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-3">Selecione um grupo disponível:</p>
            <div className="flex flex-wrap gap-2">
              {data.grupos_disponiveis.map((g) => { const color = getColor(g); const isSelected = selectedGroup === g; return (
                <button key={g} type="button" data-testid={`bloqueio-group-${g}`} onClick={() => setSelectedGroup(g)}
                  style={isSelected ? { background: `${color}22`, borderColor: color, color } : {}}
                  className={`text-sm px-3 py-1.5 rounded-lg border transition-all font-semibold ${isSelected ? "" : "border-border bg-muted/50 hover:bg-muted text-foreground"}`}
                >{getLabel(g)}</button>
              ); })}
            </div>
          </div>
        ) : (
          <div className="mb-6 p-3 rounded-lg bg-destructive/5 border border-destructive/15"><p className="text-sm text-destructive font-medium">Todos os grupos de falha estão ocupados para este equipamento.</p></div>
        )}
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1 rounded-lg" onClick={onClose} data-testid="bloqueio-cancelar">Cancelar</Button>
          {data.grupos_disponiveis?.length > 0 && (
            <Button className="flex-1 rounded-lg" onClick={() => onConfirm(selectedGroup)} disabled={!selectedGroup} data-testid="bloqueio-confirmar">
              <ArrowRight className="h-4 w-4 mr-2" />Usar {getLabel(selectedGroup)}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── SolicitanteSection ───────────────────────────────────────────────────────
function SolicitanteSection({ cracha, onCrachaChange, nome, onNomeChange, status, onBuscar, buscando }) {
  const hk = (e) => { if (e.key === "Enter") { e.preventDefault(); onBuscar(); } };
  return (
    <div className="rounded-xl border border-border/60 bg-muted/20 p-4 space-y-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Solicitante</p>
      <div className="flex gap-2">
        <div className="flex-1 space-y-1"><Label htmlFor="sol-cracha" className="text-xs">Crachá / ID</Label>
          <Input id="sol-cracha" value={cracha} onChange={(e) => onCrachaChange(e.target.value)} onKeyDown={hk} placeholder="Ex: 12345" className="rounded-lg h-9 text-sm" data-testid="sol-cracha-input" />
        </div>
        <div className="flex items-end">
          <Button type="button" variant="outline" size="sm" className="h-9 rounded-lg px-3" onClick={onBuscar} disabled={buscando || !cracha.trim()} data-testid="sol-buscar-btn">
            {buscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}<span className="ml-1.5 text-xs">Buscar</span>
          </Button>
        </div>
      </div>
      {status === "found" && (<div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/8 border border-emerald-500/20"><UserCheck className="h-4 w-4 text-emerald-500 shrink-0" /><span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{nome}</span></div>)}
      {status === "not_found" && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/8 border border-amber-500/20"><UserX className="h-4 w-4 text-amber-500 shrink-0" /><span className="text-xs text-amber-600 dark:text-amber-400">Crachá não cadastrado — informe o nome manualmente</span></div>
          <div className="space-y-1"><Label htmlFor="sol-nome-manual" className="text-xs">Nome do solicitante *</Label>
            <Input id="sol-nome-manual" value={nome} onChange={(e) => onNomeChange(e.target.value)} placeholder="Nome completo" className="rounded-lg h-9 text-sm" data-testid="sol-nome-manual-input" />
          </div>
        </div>
      )}
      {status === null && (
        <div className="space-y-1"><Label htmlFor="sol-nome-direto" className="text-xs">Nome do solicitante *<span className="text-muted-foreground font-normal ml-1">(ou busque pelo crachá acima)</span></Label>
          <Input id="sol-nome-direto" value={nome} onChange={(e) => onNomeChange(e.target.value)} placeholder="Nome completo" className="rounded-lg h-9 text-sm" data-testid="sol-nome-direto-input" />
        </div>
      )}
    </div>
  );
}

// ─── CrachaLookupInline ───────────────────────────────────────────────────────
function CrachaLookupInline({ cracha, onCrachaChange, nome, onNomeChange, status, onBuscar, buscando }) {
  const hk = (e) => { if (e.key === "Enter") { e.preventDefault(); onBuscar(); } };
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <div className="flex-1 space-y-1"><Label className="text-xs">Crachá / ID</Label>
          <Input value={cracha} onChange={(e) => onCrachaChange(e.target.value)} onKeyDown={hk} placeholder="Ex: 12345" className="rounded-lg h-9 text-sm" />
        </div>
        <div className="flex items-end">
          <Button type="button" variant="outline" size="sm" className="h-9 rounded-lg px-3" onClick={onBuscar} disabled={buscando || !cracha.trim()}>
            {buscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}<span className="ml-1.5 text-xs">Buscar</span>
          </Button>
        </div>
      </div>
      {status === "found" && (<div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/8 border border-emerald-500/20"><UserCheck className="h-4 w-4 text-emerald-500 shrink-0" /><span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{nome}</span></div>)}
      {(status === "not_found" || status === null) && (
        <div className="space-y-1">
          {status === "not_found" && (<div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-amber-500/8 border border-amber-500/20 text-xs text-amber-600 dark:text-amber-400"><UserX className="h-3.5 w-3.5 shrink-0" />Crachá não encontrado — informe o nome manualmente</div>)}
          <div className="space-y-1"><Label className="text-xs">Nome *</Label>
            <Input value={nome} onChange={(e) => onNomeChange(e.target.value)} placeholder="Nome completo" className="rounded-lg h-9 text-sm" />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── OSTimeline ───────────────────────────────────────────────────────────────
function OSTimeline({ historico }) {
  if (!historico || historico.length === 0) {
    return <p className="text-xs text-muted-foreground text-center py-3">Nenhum registro de histórico</p>;
  }
  return (
    <div className="space-y-0">
      {historico.map((entry, idx) => {
        const cfg = HISTORICO_CONFIG[entry.status_novo] || HISTORICO_CONFIG.aberta;
        const isLast = idx === historico.length - 1;
        const ts = new Date(entry.timestamp).toLocaleString("pt-BR");
        return (
          <div key={entry.id} className="flex gap-3">
            {/* Vertical connector */}
            <div className="flex flex-col items-center">
              <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-0.5 ${cfg.dot}`} />
              {!isLast && <div className="w-px flex-1 min-h-[28px] border-l-2 border-dashed border-border/50 my-1" />}
            </div>
            {/* Content */}
            <div className={`pb-4 ${isLast ? "pb-0" : ""} min-w-0`}>
              <p className="text-sm font-semibold leading-tight" style={{ color: cfg.color }}>{entry.etapa_label}</p>
              <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                <span className="text-[11px] text-muted-foreground font-mono">{ts}</span>
                {entry.user_nome && (
                  <span className="text-[11px] text-muted-foreground">· {entry.user_nome}</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────
export default function OrdensServicoPage() {
  const { user } = useAuth();
  const { upgradeOpen, upgradeMessage, handleApiError, closeUpgrade } = useUpgradeDialog();

  const canSeeFinancial = (setor) => {
    if (!user) return false;
    if (user.role === "admin") return true;
    if (user.role === "lider" && setor && user.setor && setor.toUpperCase() === user.setor.toUpperCase()) return true;
    return false;
  };

  const podeAbrirOS     = user?.role === "admin" || GRUPO_PRODUCAO.includes(user?.role);
  const podeGerenciarEquipe = user?.role === "admin" || GRUPO_MANUTENCAO.includes(user?.role);
  const tiposPermitidos = (() => {
    if (!user) return ["corretiva"];
    if (user.role === "admin" || GRUPO_MANUTENCAO.includes(user.role)) return ["corretiva", "preventiva", "preditiva"];
    return ["corretiva"];
  })();

  // ─── Estado ───────────────────────────────────────────────────────────────
  const [ordens, setOrdens]         = useState([]);
  const [equipamentos, setEquipamentos] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterTipo, setFilterTipo] = useState("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [bloqueioModal, setBloqueioModal] = useState(null);

  // Formulário nova OS
  const FORM_RESET = { equipamento_id: "", tipo: "corretiva", prioridade: "media", descricao: "", falha_tipo: "", falha_modo: "", falha_causa: "", failure_group: "" };
  const [formData, setFormData]     = useState(FORM_RESET);
  const [solCracha, setSolCracha]   = useState("");
  const [solNome, setSolNome]       = useState("");
  const [solStatus, setSolStatus]   = useState(null);
  const [buscandoCracha, setBuscandoCracha] = useState(false);
  const [creating, setCreating]     = useState(false);

  // Detalhe OS
  const [detailOS, setDetailOS]         = useState(null);
  const [detailCustos, setDetailCustos] = useState([]);
  const [detailEquipe, setDetailEquipe] = useState([]);
  const [detailHistorico, setDetailHistorico] = useState([]);
  const [loadingEquipe, setLoadingEquipe] = useState(false);
  const [loadingHistorico, setLoadingHistorico] = useState(false);
  const [showCustoModal, setShowCustoModal] = useState(false);
  const [custoForm, setCustoForm]           = useState({ tipo: "consumo", descricao: "", valor: "", quantidade: "1" });
  const [deletingCustoId, setDeletingCustoId] = useState(null);  // id do custo sendo excluído (confirmação)
  const [confirmDeleteCusto, setConfirmDeleteCusto] = useState(null); // custo objeto

  // Modal equipe
  const [showAddMembroModal, setShowAddMembroModal] = useState(false);
  const [membroCracha, setMembroCracha] = useState("");
  const [membroNome, setMembroNome]     = useState("");
  const [membroStatus, setMembroStatus] = useState(null);
  const [membroBuscando, setMembroBuscando] = useState(false);
  const [membroEspecialidade, setMembroEspecialidade] = useState("");
  const [adicionandoMembro, setAdicionandoMembro] = useState(false);

  // Modal relatório de execução
  const [showRelatorioModal, setShowRelatorioModal] = useState(false);
  const [relatorioOS, setRelatorioOS]   = useState(null);        // OS que vai ser concluída
  const [relatorioTargetStatus, setRelatorioTargetStatus] = useState(null);
  const [relForm, setRelForm]           = useState({ o_que: "", analise: "" });
  const [submittingRelatorio, setSubmittingRelatorio] = useState(false);

  const canEditOS    = user?.role === "admin" || user?.role === "lider" || user?.role === "tecnico" || GRUPO_MANUTENCAO.includes(user?.role);
  const canReviewOS  = user?.role === "admin" || user?.role === "lider";
  // Pode ver breakdown financeiro completo (materiais + mão de obra + parada)
  const podeCustoCompleto = user?.role === "admin" || GRUPO_MANUTENCAO.includes(user?.role);

  // ─── Load ─────────────────────────────────────────────────────────────────
  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterStatus !== "all") params.status = filterStatus;
      if (filterTipo   !== "all") params.tipo   = filterTipo;
      const [osRes, eqRes] = await Promise.all([getOrdensServico(params), getEquipamentos()]);
      setOrdens(osRes.data || []);
      setEquipamentos(eqRes.data || []);
      if (canReviewOS) {
        try { const pr = await getPendingReviews(); setPendingCount(pr.data?.length || 0); } catch { setPendingCount(0); }
      }
    } catch { toast.error("Erro ao carregar ordens de serviço"); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadData(); }, [filterStatus, filterTipo]); // eslint-disable-line

  const resetForm = () => { setFormData(FORM_RESET); setSolCracha(""); setSolNome(""); setSolStatus(null); };
  const handleOpenCreate = () => { resetForm(); setShowCreateModal(true); };

  // ─── Busca crachá ─────────────────────────────────────────────────────────
  const mkBuscar = (setCracha_, setNome_, setStatus_, setBuscando_) => async () => {
    setBuscando_(true);
    const cracha = setCracha_.current;
    try {
      const res = await buscarPorCracha(cracha.trim());
      if (res.data.encontrado) { setNome_(res.data.nome_completo); setStatus_("found"); }
      else { setNome_(""); setStatus_("not_found"); }
    } catch { setNome_(""); setStatus_("not_found"); }
    finally { setBuscando_(false); }
  };

  const solCrachaRef = { current: solCracha };
  const membroCrachaRef = { current: membroCracha };

  const handleBuscarCracha = async () => {
    if (!solCracha.trim()) return;
    setBuscandoCracha(true);
    try {
      const res = await buscarPorCracha(solCracha.trim());
      if (res.data.encontrado) { setSolNome(res.data.nome_completo); setSolStatus("found"); }
      else { setSolNome(""); setSolStatus("not_found"); }
    } catch { setSolNome(""); setSolStatus("not_found"); }
    finally { setBuscandoCracha(false); }
  };

  const handleBuscarMembroCracha = async () => {
    if (!membroCracha.trim()) return;
    setMembroBuscando(true);
    try {
      const res = await buscarPorCracha(membroCracha.trim());
      if (res.data.encontrado) { setMembroNome(res.data.nome_completo); setMembroStatus("found"); }
      else { setMembroNome(""); setMembroStatus("not_found"); }
    } catch { setMembroNome(""); setMembroStatus("not_found"); }
    finally { setMembroBuscando(false); }
  };

  // ─── Nova OS ──────────────────────────────────────────────────────────────
  const handleBloqueioConfirm = (sg) => { setBloqueioModal(null); setFormData((p) => ({ ...p, failure_group: sg })); setShowCreateModal(true); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.equipamento_id || !formData.descricao) { toast.error("Preencha equipamento e descrição"); return; }
    if (!formData.failure_group) { toast.error("Selecione o grupo de falha"); return; }
    if (!solNome.trim()) { toast.error("Informe o nome do solicitante"); return; }
    setCreating(true);
    try {
      await createOrdemServico({ ...formData, solicitante_cracha: solCracha.trim() || null, solicitante_nome: solNome.trim() });
      toast.success("OS criada com sucesso!");
      setShowCreateModal(false); resetForm(); loadData();
    } catch (error) {
      if (error.response?.status === 409) { const d = error.response.data?.detail; if (d?.error === "bloqueio_grupo_falha") { setShowCreateModal(false); setBloqueioModal(d); return; } }
      if (error.response?.status === 403) { const d = error.response.data?.detail; if (d?.error === "tipo_os_nao_permitido") { toast.error(d.message); return; } }
      if (!handleApiError(error)) toast.error(error.response?.data?.detail || "Erro ao criar OS");
    } finally { setCreating(false); }
  };

  // ─── Mudança de status (com interceptação para relatório) ──────────────────
  const handleStatusChange = async (os, newStatus) => {
    // Intercepta transição "Concluir" para exibir modal de relatório
    if (newStatus === "aguardando_revisao" && os.status === "em_atendimento") {
      setRelatorioOS(os);
      setRelatorioTargetStatus(newStatus);
      setRelForm({ o_que: "", analise: "" });
      setShowRelatorioModal(true);
      return;
    }
    try {
      await updateOrdemServico(os.id, { status: newStatus });
      toast.success("Status atualizado!");
      loadData();
      if (detailOS?.id === os.id) viewOSDetail(os.id);
    } catch { toast.error("Erro ao atualizar status"); }
  };

  // ─── Submeter relatório + concluir ────────────────────────────────────────
  const handleSubmitRelatorio = async (e) => {
    e.preventDefault();
    if (relForm.o_que.trim().length < 30) { toast.error("\"O que foi realizado\" precisa ter pelo menos 30 caracteres."); return; }
    if (relForm.analise.trim().length < 30) { toast.error("\"Análise do problema\" precisa ter pelo menos 30 caracteres."); return; }
    setSubmittingRelatorio(true);
    try {
      await updateOrdemServico(relatorioOS.id, {
        status: relatorioTargetStatus,
        relatorio_o_que_foi_realizado: relForm.o_que.trim(),
        relatorio_analise_problema: relForm.analise.trim(),
      });
      toast.success("OS concluída com sucesso!");
      setShowRelatorioModal(false);
      loadData();
      if (detailOS?.id === relatorioOS.id) viewOSDetail(relatorioOS.id);
    } catch (error) {
      const d = error.response?.data?.detail;
      if (d?.error === "relatorio_obrigatorio") { toast.error(d.message); }
      else { toast.error("Erro ao concluir OS"); }
    } finally { setSubmittingRelatorio(false); }
  };

  const handleAutoApprove = async () => {
    try {
      const res = await autoApproveExpired();
      if (res.data.auto_approved > 0) toast.success(`${res.data.auto_approved} OS auto-aprovadas`);
      else toast.info("Nenhuma OS expirada para auto-aprovar");
      loadData();
    } catch { toast.error("Erro ao auto-aprovar"); }
  };

  // ─── Detalhe OS ───────────────────────────────────────────────────────────
  const viewOSDetail = async (osId) => {
    const os = ordens.find((o) => o.id === osId);
    if (!os) return;
    try { const custosRes = await getCustos({ ordem_servico_id: osId }); setDetailCustos(custosRes.data || []); } catch { setDetailCustos([]); }
    setDetailOS(os);

    // Histórico
    setLoadingHistorico(true);
    try { const hRes = await getOSHistorico(osId); setDetailHistorico(hRes.data || []); } catch { setDetailHistorico([]); }
    finally { setLoadingHistorico(false); }

    // Equipe (apenas prev/pred)
    if (os.tipo === "preventiva" || os.tipo === "preditiva") {
      setLoadingEquipe(true);
      try { const eq = await getOSEquipe(osId); setDetailEquipe(eq.data || []); } catch { setDetailEquipe([]); }
      finally { setLoadingEquipe(false); }
    } else { setDetailEquipe([]); }
  };

  // ─── Equipe ───────────────────────────────────────────────────────────────
  const handleOpenAddMembro = () => { setMembroCracha(""); setMembroNome(""); setMembroStatus(null); setMembroEspecialidade(""); setShowAddMembroModal(true); };

  const handleAddMembro = async (e) => {
    e.preventDefault();
    if (!membroNome.trim()) { toast.error("Informe o nome do membro"); return; }
    if (!membroEspecialidade) { toast.error("Selecione a especialidade"); return; }
    setAdicionandoMembro(true);
    try {
      await addOSEquipeMembro(detailOS.id, { cracha: membroCracha.trim() || null, nome_membro: membroNome.trim(), especialidade: membroEspecialidade });
      toast.success("Membro adicionado!");
      setShowAddMembroModal(false);
      const eq = await getOSEquipe(detailOS.id); setDetailEquipe(eq.data || []);
    } catch (error) { toast.error(error.response?.data?.detail || "Erro ao adicionar membro"); }
    finally { setAdicionandoMembro(false); }
  };

  const handleRemoveMembro = async (membroId) => {
    try { await removeOSEquipeMembro(detailOS.id, membroId); toast.success("Membro removido"); setDetailEquipe((p) => p.filter((m) => m.id !== membroId)); }
    catch { toast.error("Erro ao remover membro"); }
  };

  // ─── Custo ────────────────────────────────────────────────────────────────
  const handleConfirmDeleteCusto = (custo) => setConfirmDeleteCusto(custo);

  const handleDeleteCusto = async () => {
    if (!confirmDeleteCusto) return;
    setDeletingCustoId(confirmDeleteCusto.id);
    try {
      await deleteCusto(confirmDeleteCusto.id);
      toast.success("Item removido");
      setDetailCustos((prev) => prev.filter((c) => c.id !== confirmDeleteCusto.id));
      setConfirmDeleteCusto(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao remover item");
    } finally {
      setDeletingCustoId(null);
    }
  };

  const handleAddCusto = async (e) => {
    e.preventDefault();
    if (!custoForm.descricao || !custoForm.valor) { toast.error("Preencha descrição e valor"); return; }
    try {
      await createCusto({ ordem_servico_id: detailOS.id, tipo: custoForm.tipo, descricao: custoForm.descricao, valor: parseFloat(custoForm.valor), quantidade: parseFloat(custoForm.quantidade) || 1 });
      toast.success("Custo adicionado!");
      setShowCustoModal(false); setCustoForm({ tipo: "consumo", descricao: "", valor: "", quantidade: "1" });
      if (detailOS) viewOSDetail(detailOS.id);
    } catch { toast.error("Erro ao adicionar custo"); }
  };

  const filteredOrdens = ordens.filter((os) => os.numero?.toString().includes(search) || os.descricao?.toLowerCase().includes(search.toLowerCase()));
  const getEquipamentoNome = (id) => { const eq = equipamentos.find((e) => e.id === id); return eq ? `${eq.codigo} - ${eq.nome}` : id; };
  const getNextAction = (os) => {
    const cfg = statusConfig[os.status]; if (!cfg?.next) return null;
    if (os.status === "aberta"             && !canEditOS)   return null;
    if (os.status === "em_atendimento"     && !canEditOS)   return null;
    if (os.status === "aguardando_peca"    && !canEditOS)   return null;
    if (os.status === "aguardando_revisao" && !canReviewOS) return null;
    if (os.status === "revisada"           && !canReviewOS) return null;
    return cfg;
  };

  return (
    <div className="space-y-6" data-testid="ordens-servico-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2"><Wrench className="h-6 w-6 text-primary" />Ordens de Serviço</h1>
          <p className="text-muted-foreground text-sm mt-1">{ordens.length} ordens encontradas</p>
        </div>
        <div className="flex gap-2">
          {canReviewOS && pendingCount > 0 && (
            <Button variant="outline" size="sm" className="rounded-lg h-10 border-amber-500/30 text-amber-500 hover:bg-amber-500/10" onClick={handleAutoApprove}>
              <Clock className="h-4 w-4 mr-2" />Auto-aprovar ({pendingCount})
            </Button>
          )}
          {podeAbrirOS && (
            <Button onClick={handleOpenCreate} className="rounded-lg h-10 shadow-lg shadow-primary/20" data-testid="new-os-btn">
              <Plus className="h-4 w-4 mr-2" />Abrir OS
            </Button>
          )}
        </div>
      </div>

      {/* Pending Reviews Banner */}
      {canReviewOS && pendingCount > 0 && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-amber-500/8 border border-amber-500/15">
          <div className="flex items-center gap-2.5"><Shield className="h-5 w-5 text-amber-500" /><span className="text-sm font-medium text-amber-600 dark:text-amber-400">{pendingCount} OS aguardando sua revisão (SLA: 24h)</span></div>
          <Button size="sm" variant="outline" className="rounded-lg h-8 border-amber-500/30 text-amber-500" onClick={() => setFilterStatus("aguardando_revisao")}>Ver pendentes</Button>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input placeholder="Buscar por número ou descrição..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10 h-10 rounded-lg bg-card" data-testid="search-os-input" />
        </div>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[180px] rounded-lg h-10" data-testid="filter-status-select"><Filter className="h-4 w-4 mr-2" /><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todos</SelectItem>{Object.entries(statusConfig).map(([k, v]) => (<SelectItem key={k} value={k}>{v.label}</SelectItem>))}</SelectContent>
        </Select>
        <Select value={filterTipo} onValueChange={setFilterTipo}>
          <SelectTrigger className="w-[150px] rounded-lg h-10" data-testid="filter-tipo-select"><SelectValue placeholder="Tipo" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todos</SelectItem><SelectItem value="corretiva">Corretiva</SelectItem><SelectItem value="preventiva">Preventiva</SelectItem><SelectItem value="preditiva">Preditiva</SelectItem></SelectContent>
        </Select>
      </div>

      {/* OS Cards */}
      {loading ? (
        <div className="flex items-center justify-center h-40"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
      ) : filteredOrdens.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground"><Wrench className="h-10 w-10 mb-3 opacity-40" /><p className="font-medium">Nenhuma OS encontrada</p></div>
      ) : (
        <div className="space-y-3 stagger-children">
          {filteredOrdens.map((os) => {
            const sc = statusConfig[os.status] || statusConfig.aberta;
            const StatusIcon = sc.icon;
            const tc = tipoConfig[os.tipo] || tipoConfig.corretiva;
            const pc = prioridadeConfig[os.prioridade] || prioridadeConfig.media;
            const nextAction = getNextAction(os);
            const emAtendimento = STATUSES_EM_ATENDIMENTO.includes(os.status);
            return (
              <div key={os.id}
                className={`border border-border/50 rounded-xl bg-card p-4 card-hover group cursor-pointer transition-all ${os.status === "aguardando_peca" ? "border-l-4 border-l-orange-500" : os.status === "aguardando_revisao" ? "border-l-4 border-l-amber-500" : os.prioridade === "critica" && os.status !== "fechada" ? "border-l-4 border-l-red-500" : ""}`}
                onClick={() => viewOSDetail(os.id)} data-testid={`os-row-${os.numero}`}>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-center"><span className="font-mono text-lg font-bold leading-none">#{os.numero}</span>
                      {os.reincidente && <div className="mt-1"><span className="text-[9px] font-bold text-orange-500 bg-orange-500/10 px-1.5 py-0.5 rounded">🔁 REINC.</span></div>}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-medium truncate">{os.equipamento_nome || getEquipamentoNome(os.equipamento_id)}</span>
                      <Badge className={`${tc.color} text-[10px] border rounded`}>{tc.label}</Badge>
                      <Badge className={`${pc.color} text-[10px] border rounded`}>{pc.label}</Badge>
                      {!os.dentro_sla && os.status !== "fechada" && <Badge className="bg-red-500 text-white text-[10px] rounded">SLA</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{os.descricao}</p>
                    <div className="flex flex-wrap gap-x-3 mt-0.5">
                      {os.solicitante_nome && (<p className="text-[10px] text-muted-foreground"><span className="text-muted-foreground/60">Aberto por:</span> <span className="font-medium">{os.solicitante_nome}</span>{os.solicitante_cracha && <span className="font-mono ml-1 text-muted-foreground/50">#{os.solicitante_cracha}</span>}</p>)}
                      {os.tecnico_nome && emAtendimento && (<p className="text-[10px] text-muted-foreground"><span className="text-muted-foreground/60">Atendendo:</span> <span className="font-medium">{os.tecnico_nome}</span>{os.tecnico_employee_id && <span className="font-mono ml-1 text-muted-foreground/50">· mat. {os.tecnico_employee_id}</span>}</p>)}
                    </div>
                  </div>
                  <div className="hidden md:flex flex-col items-end shrink-0">
                    {os.tempo_total > 0 ? (<div className="text-right"><span className="text-xs text-muted-foreground flex items-center gap-1 justify-end"><TrendingDown className="h-3 w-3 text-red-500" />Parada</span>{os.custo_parada != null ? <span className="font-mono text-sm font-bold text-red-500">R$ {os.custo_parada.toLocaleString("pt-BR", { minimumFractionDigits: 0 })}</span> : <BlurredMoney color="red" />}</div>) : <span className="text-xs text-muted-foreground">—</span>}
                  </div>
                  <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
                    <Badge className={`${sc.color} rounded-lg px-2.5 py-1 text-xs border`}><StatusIcon className="h-3 w-3 mr-1" />{sc.label}</Badge>
                    {nextAction && (<>{nextAction.alts?.map((alt) => (<Button key={alt.next} size="sm" variant="outline" className="h-8 rounded-lg text-xs px-3" onClick={(e) => { e.stopPropagation(); handleStatusChange(os, alt.next); }}>{alt.nextLabel}</Button>))}
                      <Button size="sm" className="h-8 rounded-lg text-xs px-3 shadow-sm" onClick={(e) => { e.stopPropagation(); handleStatusChange(os, nextAction.next); }}><ArrowRight className="h-3 w-3 mr-1" />{nextAction.nextLabel}</Button></>)}
                  </div>
                </div>
                {os.status === "aguardando_revisao" && os.review_deadline && (
                  <div className="mt-2 flex items-center gap-2 text-xs"><Timer className="h-3 w-3 text-amber-500" />
                    <span className={new Date(os.review_deadline) < new Date() ? "text-red-500 font-semibold" : "text-amber-500"}>Prazo revisão: {new Date(os.review_deadline).toLocaleString("pt-BR")}{new Date(os.review_deadline) < new Date() && " — EXPIRADO"}</span>
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
                <div className="flex items-center gap-3"><span className="font-heading text-xl font-bold">OS #{detailOS.numero}</span>
                  <Badge className={`${statusConfig[detailOS.status]?.color} rounded-lg text-xs border`}>{statusConfig[detailOS.status]?.label}</Badge>
                </div>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDetailOS(null)}><X className="h-4 w-4" /></Button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* Quick Actions */}
              {(() => { const next = getNextAction(detailOS); if (!next) return null; return (
                <div className="flex flex-col gap-2">
                  {next.alts?.map((alt) => (<Button key={alt.next} variant="outline" className="w-full h-11 rounded-xl text-sm font-semibold" onClick={() => handleStatusChange(detailOS, alt.next)}>{alt.nextLabel}</Button>))}
                  <Button className="w-full h-12 rounded-xl text-base font-semibold shadow-lg shadow-primary/20" onClick={() => handleStatusChange(detailOS, next.next)}>
                    <ArrowRight className="h-5 w-5 mr-2" />{next.nextLabel} OS
                  </Button>
                </div>
              ); })()}

              {/* Info Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Equipamento</p><p className="text-sm font-medium mt-1 truncate">{getEquipamentoNome(detailOS.equipamento_id)}</p></div>
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Tipo</p><Badge className={`${tipoConfig[detailOS.tipo]?.color} text-xs border rounded mt-1`}>{tipoConfig[detailOS.tipo]?.label}</Badge></div>
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Prioridade</p><Badge className={`${prioridadeConfig[detailOS.prioridade]?.color} text-xs border rounded mt-1`}>{prioridadeConfig[detailOS.prioridade]?.label}</Badge></div>
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">SLA</p>
                  <Badge className={`text-xs border rounded mt-1 ${detailOS.dentro_sla ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" : "bg-red-500/10 text-red-500 border-red-500/20"}`}>{detailOS.dentro_sla ? "✅ Dentro" : "❌ Fora"}</Badge>
                </div>
              </div>

              {/* Participantes — quem abriu e quem executou */}
              <div className="rounded-xl border border-border/50 overflow-hidden">
                <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider px-4 py-2.5 bg-muted/30 border-b border-border/50">
                  Participantes
                </p>

                {/* Quem abriu */}
                <div className="flex items-start gap-3 px-4 py-3 border-b border-border/30">
                  <UserCheck className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-0.5">Quem abriu</p>
                    {detailOS.solicitante_nome ? (
                      <>
                        <p className="text-sm font-semibold leading-tight">
                          {detailOS.solicitante_nome}
                          {detailOS.solicitante_cracha && (
                            <span className="font-mono text-xs text-muted-foreground ml-2">· Crachá {detailOS.solicitante_cracha}</span>
                          )}
                        </p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {new Date(detailOS.created_at).toLocaleString("pt-BR")}
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground italic">Não informado</p>
                    )}
                  </div>
                </div>

                {/* Quem executou / executores */}
                <div className="flex items-start gap-3 px-4 py-3">
                  <Wrench className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-0.5">
                      {detailEquipe.length > 1 ? "Executores" : "Quem executou"}
                    </p>

                    {detailOS.tecnico_nome && STATUSES_EM_ATENDIMENTO.includes(detailOS.status) ? (
                      <>
                        {/* Técnico responsável */}
                        <div className="flex items-baseline gap-2 flex-wrap">
                          <p className="text-sm font-semibold leading-tight">
                            {detailOS.tecnico_nome}
                            {detailOS.tecnico_employee_id && (
                              <span className="font-mono text-xs text-muted-foreground ml-2">· Mat. {detailOS.tecnico_employee_id}</span>
                            )}
                          </p>
                        </div>
                        {detailOS.inicio_atendimento && (
                          <p className="text-[11px] text-muted-foreground mt-0.5">
                            Início: {new Date(detailOS.inicio_atendimento).toLocaleString("pt-BR")}
                            {detailOS.fim_atendimento && (
                              <span className="ml-2">· Fim: {new Date(detailOS.fim_atendimento).toLocaleString("pt-BR")}</span>
                            )}
                          </p>
                        )}

                        {/* Membros da equipe (preventiva/preditiva) */}
                        {detailEquipe.length > 0 && (
                          <div className="mt-2 space-y-1.5 border-t border-border/30 pt-2">
                            {detailEquipe.map((m) => {
                              const esp = getEspecialidadeInfo(m.especialidade);
                              const EspIcon = esp?.Icon || Wrench;
                              return (
                                <div key={m.id} className="flex items-center gap-2">
                                  <span className="inline-flex items-center justify-center w-5 h-5 rounded shrink-0"
                                    style={{ background: `${esp?.color}22`, color: esp?.color }}>
                                    <EspIcon className="h-3 w-3" />
                                  </span>
                                  <span className="text-xs font-medium">{m.nome_membro}</span>
                                  {m.cracha && <span className="font-mono text-[10px] text-muted-foreground">Mat. {m.cracha}</span>}
                                  {m.especialidade && <span className="text-[10px] text-muted-foreground capitalize">· {esp?.label}</span>}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground italic">Aguardando aceite</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Equipe (preventiva/preditiva) */}
              {(detailOS.tipo === "preventiva" || detailOS.tipo === "preditiva") && (
                <div className="rounded-xl border border-border/50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2.5 bg-muted/30 border-b border-border/50">
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider flex items-center gap-1.5"><Users className="h-3.5 w-3.5" />Equipe de execução</p>
                    {podeGerenciarEquipe && detailOS.status !== "fechada" && (<Button size="sm" variant="ghost" className="h-7 rounded-lg text-xs px-2.5" onClick={handleOpenAddMembro}><Plus className="h-3.5 w-3.5 mr-1" />Add</Button>)}
                  </div>
                  {loadingEquipe ? (<div className="flex items-center justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>)
                  : detailEquipe.length === 0 ? (
                    <div className="px-4 py-4 text-center"><p className="text-xs text-muted-foreground">Nenhum membro na equipe</p>
                      {podeGerenciarEquipe && detailOS.status !== "fechada" && (<Button size="sm" variant="outline" className="mt-2 h-7 rounded-lg text-xs" onClick={handleOpenAddMembro}><Plus className="h-3 w-3 mr-1" />Adicionar primeiro membro</Button>)}
                    </div>
                  ) : (
                    <div className="divide-y divide-border/30">
                      {detailEquipe.map((m) => { const esp = getEspecialidadeInfo(m.especialidade); const EspIcon = esp?.Icon || Wrench; return (
                        <div key={m.id} className="flex items-center gap-3 px-4 py-3">
                          <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${esp?.color}22`, color: esp?.color }}><EspIcon className="h-3.5 w-3.5" /></div>
                          <div className="flex-1 min-w-0"><p className="text-sm font-semibold truncate">{m.nome_membro}</p>
                            <div className="flex items-center gap-2 flex-wrap">
                              {m.cracha && <span className="font-mono text-[10px] text-muted-foreground">Mat. {m.cracha}</span>}
                              {m.especialidade && <span className="text-[10px] font-medium capitalize" style={{ color: esp?.color }}>{esp?.label}</span>}
                            </div>
                          </div>
                          {podeGerenciarEquipe && (<button onClick={() => handleRemoveMembro(m.id)} className="p-1.5 rounded-lg text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors" title="Remover"><Trash2 className="h-3.5 w-3.5" /></button>)}
                        </div>
                      ); })}
                    </div>
                  )}
                </div>
              )}

              {/* Recurrence */}
              {detailOS.reincidente && (<div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-orange-500/8 border border-orange-500/15"><AlertTriangle className="h-5 w-5 text-orange-500" /><div><p className="text-sm font-semibold text-orange-600 dark:text-orange-400">Falha Reincidente</p><p className="text-xs text-muted-foreground">Mesma falha detectada nos últimos 30 dias</p></div></div>)}

              {/* Description */}
              <div><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1">Descrição</p><p className="text-sm leading-relaxed">{detailOS.descricao}</p></div>

              {detailOS.solucao && (<div><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1">Solução</p><p className="text-sm leading-relaxed">{detailOS.solucao}</p></div>)}

              {/* Downtime Cost */}
              {detailOS.tempo_total > 0 && (
                <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/15">
                  <p className="text-xs font-semibold text-red-500 flex items-center gap-1.5 mb-2"><TrendingDown className="h-4 w-4" />Impacto Financeiro (Máquina Parada)</p>
                  {detailOS.custo_parada != null ? <p className="text-2xl font-heading font-bold text-red-500">R$ {detailOS.custo_parada.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p> : <BlurredMoney size="lg" color="red" />}
                  <p className="text-xs text-muted-foreground mt-1">{(detailOS.tempo_total / 60).toFixed(1)}h de máquina parada</p>
                </div>
              )}

              {/* Review Section */}
              {(detailOS.status === "aguardando_revisao" || detailOS.status === "revisada") && (
                <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/15 space-y-2">
                  <p className="text-xs font-semibold text-amber-500 flex items-center gap-1.5"><Shield className="h-4 w-4" />Revisão de Qualidade</p>
                  {detailOS.revisor_nome && <p className="text-sm"><span className="text-muted-foreground">Revisor:</span> {detailOS.revisor_nome}</p>}
                  {detailOS.review_deadline && (
                    <p className="text-sm"><span className="text-muted-foreground">Prazo:</span> {new Date(detailOS.review_deadline).toLocaleString("pt-BR")}
                      {detailOS.status === "aguardando_revisao" && new Date(detailOS.review_deadline) < new Date() && <Badge className="ml-2 bg-red-500/10 text-red-500 text-[10px] rounded border border-red-500/20">Expirado</Badge>}
                    </p>
                  )}
                  {detailOS.auto_approved && <Badge className="bg-amber-500/10 text-amber-500 text-[10px] rounded border border-amber-500/20">Auto-aprovada (24h expirado)</Badge>}
                  {detailOS.review_notes && <p className="text-sm"><span className="text-muted-foreground">Notas:</span> {detailOS.review_notes}</p>}
                </div>
              )}

              {/* Failure Analysis */}
              {detailOS.tipo === "corretiva" && (detailOS.falha_tipo || detailOS.falha_modo || detailOS.falha_causa) && (
                <div className="grid grid-cols-3 gap-3">
                  {[{ label: "Tipo Falha", value: detailOS.falha_tipo }, { label: "Modo", value: detailOS.falha_modo }, { label: "Causa", value: detailOS.falha_causa }].map((f, i) => (
                    <div key={i} className="p-3 bg-muted/30 rounded-xl"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">{f.label}</p><p className="text-sm mt-0.5">{f.value || "—"}</p></div>
                  ))}
                </div>
              )}

              {/* ── Histórico dos Acontecimentos (após Solução, antes dos tempos) ── */}
              <div className="rounded-xl border border-border/50 overflow-hidden">
                <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider px-4 py-2.5 bg-muted/30 border-b border-border/50">
                  Histórico dos Acontecimentos
                </p>
                <div className="px-4 py-4">
                  {loadingHistorico ? (
                    <div className="flex items-center justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
                  ) : <OSTimeline historico={detailHistorico} />}
                </div>
              </div>

              {/* ── Relatório do técnico executor (após timeline, antes dos tempos) ── */}
              {detailOS.relatorio_o_que_foi_realizado && (
                <div className="rounded-xl border border-border/50 overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2.5 bg-muted/30 border-b border-border/50">
                    <ClipboardCheck className="h-3.5 w-3.5 text-primary" />
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Relatório do técnico executor</p>
                  </div>
                  <div className="px-4 py-4 space-y-4">
                    <div>
                      <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">O que foi realizado</p>
                      <p className="text-sm leading-relaxed">{detailOS.relatorio_o_que_foi_realizado}</p>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Análise do problema / Causa raiz</p>
                      <p className="text-sm leading-relaxed">{detailOS.relatorio_analise_problema}</p>
                    </div>
                    {(detailOS.relatorio_preenchido_por_nome || detailOS.relatorio_preenchido_em) && (
                      <p className="text-[11px] text-muted-foreground border-t border-border/40 pt-3">
                        Preenchido por{" "}
                        {detailOS.relatorio_preenchido_por_nome && <span className="font-semibold">{detailOS.relatorio_preenchido_por_nome}</span>}
                        {detailOS.relatorio_preenchido_em && (
                          <span className="ml-1">· {new Date(detailOS.relatorio_preenchido_em).toLocaleString("pt-BR")}</span>
                        )}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Cartões de tempo ──────────────────────────────────────────── */}
              <div className="grid grid-cols-3 gap-3">
                {[{ label: "Resposta", value: detailOS.tempo_resposta ? `${detailOS.tempo_resposta} min` : "—" }, { label: "Reparo", value: detailOS.tempo_reparo ? `${detailOS.tempo_reparo} min` : "—" }, { label: "Total", value: detailOS.tempo_total ? `${detailOS.tempo_total} min` : "—" }].map((t, i) => (
                  <div key={i} className="p-3 bg-muted/30 rounded-xl text-center"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">{t.label}</p><p className="text-lg font-heading font-bold mt-1">{t.value}</p></div>
                ))}
              </div>

              {/* Custos (materiais/peças) */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Peças e Materiais</p>
                  {canEditOS && user?.role === "admin" && detailOS.status !== "fechada" && (
                    <Button size="sm" variant="outline" className="h-7 rounded-lg text-xs" onClick={() => setShowCustoModal(true)}>
                      <Plus className="h-3 w-3 mr-1" />Adicionar
                    </Button>
                  )}
                </div>
                {canSeeFinancial(detailOS.equipamento_setor) ? (
                  detailCustos.length > 0 ? (
                    <div className="space-y-1.5">
                      {detailCustos.map((c) => {
                        const podeExcluirEste = podeCustoCompleto || (c.criado_por === user?.id);
                        return (
                          <div key={c.id} className="flex items-center justify-between p-2.5 rounded-lg bg-muted/30 group/item">
                            <div className="flex-1 min-w-0">
                              <Badge className="text-[10px] rounded mb-0.5">{c.tipo}</Badge>
                              <p className="text-xs truncate">{c.descricao}</p>
                            </div>
                            <div className="flex items-center gap-2 ml-2 shrink-0">
                              <span className="font-mono text-sm font-semibold">
                                {(c.valor * c.quantidade).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                              </span>
                              {podeExcluirEste && detailOS.status !== "fechada" && (
                                <button
                                  onClick={() => handleConfirmDeleteCusto(c)}
                                  className="p-1 rounded text-muted-foreground/30 hover:text-red-500 hover:bg-red-500/10 transition-colors"
                                  data-testid={`delete-custo-${c.id}`}
                                  title="Remover item"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : <p className="text-xs text-muted-foreground text-center py-3">Nenhuma peça/material registrado</p>
                ) : (
                  <div className="flex flex-col items-center gap-2 py-4 text-center"><BlurredMoney size="md" /><p className="text-xs text-muted-foreground">Valores restritos ao seu perfil</p></div>
                )}
              </div>

              {/* Breakdown financeiro completo */}
              {podeCustoCompleto && (
                <div className="rounded-xl border border-border/50 overflow-hidden">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider px-4 py-2.5 bg-muted/30 border-b border-border/50">
                    Impacto Financeiro da OS
                  </p>
                  <div className="px-4 py-3 space-y-2">
                    {/* Materiais */}
                    {(() => {
                      const totalMat = detailCustos.reduce((a, c) => a + c.valor * c.quantidade, 0);
                      return (
                        <div className="flex items-start justify-between text-sm">
                          <span className="text-muted-foreground">Custo de materiais/peças</span>
                          <span className="font-mono font-semibold shrink-0 ml-2">
                            {totalMat > 0 ? totalMat.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "—"}
                          </span>
                        </div>
                      );
                    })()}

                    {/* Mão de obra */}
                    <div className="flex items-start justify-between text-sm">
                      <div className="flex-1">
                        <span className="text-muted-foreground">Custo de mão de obra</span>
                        {detailOS.horas_trabalhadas != null && detailOS.valor_hora_tecnico != null ? (
                          <p className="text-[10px] text-muted-foreground/60 mt-0.5">
                            └ {detailOS.horas_trabalhadas.toFixed(1)}h × {(detailOS.valor_hora_tecnico).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}/h
                            {detailOS.tecnico_nome && <span className="ml-1">({detailOS.tecnico_nome})</span>}
                          </p>
                        ) : (
                          <p className="text-[10px] text-muted-foreground/50 mt-0.5">└ Calculado ao concluir a OS</p>
                        )}
                      </div>
                      <span className="font-mono font-semibold shrink-0 ml-2">
                        {detailOS.custo_mao_obra != null
                          ? detailOS.custo_mao_obra.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
                          : "—"}
                      </span>
                    </div>

                    {/* Parada de máquina */}
                    <div className="flex items-start justify-between text-sm">
                      <div className="flex-1">
                        <span className="text-muted-foreground">Custo de parada de máquina</span>
                        {detailOS.tempo_total != null && (
                          <p className="text-[10px] text-muted-foreground/60 mt-0.5">
                            └ {(detailOS.tempo_total / 60).toFixed(1)}h × valor/h ({detailOS.equipamento_nome || "equipamento"})
                          </p>
                        )}
                      </div>
                      <span className="font-mono font-semibold shrink-0 ml-2 text-red-500">
                        {detailOS.custo_parada != null
                          ? detailOS.custo_parada.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
                          : "—"}
                      </span>
                    </div>

                    {/* Total */}
                    <div className="border-t border-border/50 pt-2.5 mt-1">
                      {(() => {
                        const mat   = detailCustos.reduce((a, c) => a + c.valor * c.quantidade, 0);
                        const mo    = detailOS.custo_mao_obra || 0;
                        const parada = detailOS.custo_parada || 0;
                        const total = mat + mo + parada;
                        return (
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-bold uppercase tracking-wide">Impacto Total</span>
                            <span className="font-mono text-lg font-bold text-primary">
                              {total.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                            </span>
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ===== Modal Relatório de Execução ===== */}
      {showRelatorioModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setShowRelatorioModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-lg shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center"><ClipboardCheck className="h-5 w-5 text-primary" /></div>
                <div>
                  <h3 className="font-heading font-bold text-base">Relatório de Execução</h3>
                  <p className="text-xs text-muted-foreground">Obrigatório para concluir a OS</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowRelatorioModal(false)}><X className="h-4 w-4" /></Button>
            </div>
            <div className="my-4 border-t border-border/40" />
            <form onSubmit={handleSubmitRelatorio} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="rel-o-que">O que foi realizado? *</Label>
                <p className="text-[11px] text-muted-foreground -mt-1">Descreva as ações executadas, peças trocadas, ajustes feitos. Mínimo 30 caracteres.</p>
                <Textarea
                  id="rel-o-que"
                  value={relForm.o_que}
                  onChange={(e) => setRelForm((p) => ({ ...p, o_que: e.target.value }))}
                  placeholder="Ex: Substituído rolamento SKF 6205 do motor principal. Realizado alinhamento a laser e verificação de folga axial..."
                  className="rounded-lg min-h-[100px]"
                  data-testid="relatorio-o-que-input"
                />
                <p className={`text-[11px] text-right ${relForm.o_que.length < 30 ? "text-destructive" : "text-muted-foreground"}`}>{relForm.o_que.length} / 30 mín.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="rel-analise">Análise do problema *</Label>
                <p className="text-[11px] text-muted-foreground -mt-1">Qual a causa raiz? O que levou à falha? Mínimo 30 caracteres.</p>
                <Textarea
                  id="rel-analise"
                  value={relForm.analise}
                  onChange={(e) => setRelForm((p) => ({ ...p, analise: e.target.value }))}
                  placeholder="Ex: Desgaste por fadiga acelerada decorrente de desalinhamento do eixo. Provável causa: vibração excessiva não monitorada..."
                  className="rounded-lg min-h-[100px]"
                  data-testid="relatorio-analise-input"
                />
                <p className={`text-[11px] text-right ${relForm.analise.length < 30 ? "text-destructive" : "text-muted-foreground"}`}>{relForm.analise.length} / 30 mín.</p>
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="button" variant="outline" className="flex-1 rounded-lg" onClick={() => setShowRelatorioModal(false)}>Cancelar</Button>
                <Button type="submit" className="flex-1 rounded-lg" disabled={submittingRelatorio} data-testid="relatorio-concluir-btn">
                  {submittingRelatorio ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle className="h-4 w-4 mr-2" />}
                  Concluir OS
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Create OS Modal ===== */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setShowCreateModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5"><h2 className="font-heading font-bold text-lg">Nova Ordem de Serviço</h2><Button variant="ghost" size="icon" onClick={() => setShowCreateModal(false)}><X className="h-4 w-4" /></Button></div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <SolicitanteSection cracha={solCracha} onCrachaChange={(v) => { setSolCracha(v); setSolStatus(null); }} nome={solNome} onNomeChange={setSolNome} status={solStatus} onBuscar={handleBuscarCracha} buscando={buscandoCracha} />
              <div className="space-y-2"><Label>Equipamento *</Label>
                <Select value={formData.equipamento_id} onValueChange={(v) => setFormData({ ...formData, equipamento_id: v })}><SelectTrigger className="rounded-lg h-10" data-testid="os-equipamento-select"><SelectValue placeholder="Selecione" /></SelectTrigger>
                  <SelectContent>{equipamentos.map((eq) => (<SelectItem key={eq.id} value={eq.id}>{eq.codigo} - {eq.nome}</SelectItem>))}</SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2"><Label>Tipo</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(tipoConfig).filter(([k]) => tiposPermitidos.includes(k)).map(([k, v]) => (<button key={k} type="button" data-testid={`os-tipo-${k}`} className={`text-xs px-3 py-2 rounded-lg border transition-all font-medium ${formData.tipo === k ? "bg-primary text-primary-foreground border-primary" : "border-border bg-muted/50 hover:bg-muted"}`} onClick={() => setFormData({ ...formData, tipo: k })}>{v.label}</button>))}
                  </div>
                </div>
                <div className="space-y-2"><Label>Prioridade</Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {Object.entries(prioridadeConfig).map(([k, v]) => (<button key={k} type="button" className={`text-xs px-2 py-2 rounded-lg border transition-all font-medium ${formData.prioridade === k ? "bg-primary text-primary-foreground border-primary" : "border-border bg-muted/50 hover:bg-muted"}`} onClick={() => setFormData({ ...formData, prioridade: k })}>{v.label}</button>))}
                  </div>
                </div>
              </div>
              <div className="space-y-2"><Label>Descrição *</Label><Textarea value={formData.descricao} onChange={(e) => setFormData({ ...formData, descricao: e.target.value })} placeholder="Descreva o problema ou serviço" className="rounded-lg" rows={3} data-testid="os-descricao-input" /></div>
              <div className="space-y-2"><Label>Grupo de Falha *{" "}{!formData.failure_group && <span className="text-destructive text-xs font-normal">(obrigatório)</span>}</Label>
                <div className="flex flex-wrap gap-2" data-testid="failure-group-chips">
                  {FAILURE_GROUPS.map((fg) => (<button key={fg.value} type="button" data-testid={`fg-chip-${fg.value}`} style={formData.failure_group === fg.value ? { background: `${fg.color}22`, borderColor: fg.color, color: fg.color } : {}} className={`text-xs px-3 py-1.5 rounded-lg border transition-all font-semibold ${formData.failure_group === fg.value ? "" : "border-border bg-muted/50 hover:bg-muted text-foreground"}`} onClick={() => setFormData({ ...formData, failure_group: fg.value })}>{fg.label}</button>))}
                </div>
              </div>
              {formData.tipo === "corretiva" && (
                <div className="grid grid-cols-3 gap-2">
                  {[{ key: "falha_tipo", label: "Tipo Falha", ph: "Mecânica" }, { key: "falha_modo", label: "Modo", ph: "Desgaste" }, { key: "falha_causa", label: "Causa", ph: "Uso" }].map((f) => (
                    <div key={f.key} className="space-y-1"><Label className="text-xs">{f.label}</Label><Input value={formData[f.key]} onChange={(e) => setFormData({ ...formData, [f.key]: e.target.value })} placeholder={f.ph} className="rounded-lg h-9 text-xs" /></div>
                  ))}
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <Button type="button" variant="outline" className="flex-1 rounded-lg" onClick={() => setShowCreateModal(false)}>Cancelar</Button>
                <Button type="submit" className="flex-1 rounded-lg" disabled={creating} data-testid="save-os-btn">{creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Zap className="h-4 w-4 mr-2" />}Criar OS</Button>
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
              <div className="space-y-1"><Label className="text-xs">Tipo</Label><Select value={custoForm.tipo} onValueChange={(v) => setCustoForm({ ...custoForm, tipo: v })}><SelectTrigger className="rounded-lg h-9"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="consumo">Consumo</SelectItem><SelectItem value="substituicao">Substituição</SelectItem><SelectItem value="mao_obra">Mão de Obra</SelectItem></SelectContent></Select></div>
              <div className="space-y-1"><Label className="text-xs">Descrição *</Label><Input value={custoForm.descricao} onChange={(e) => setCustoForm({ ...custoForm, descricao: e.target.value })} className="rounded-lg h-9" placeholder="Ex: Rolamento" /></div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1"><Label className="text-xs">Valor (R$) *</Label><Input type="number" step="0.01" value={custoForm.valor} onChange={(e) => setCustoForm({ ...custoForm, valor: e.target.value })} className="rounded-lg h-9" placeholder="100" /></div>
                <div className="space-y-1"><Label className="text-xs">Qtd</Label><Input type="number" value={custoForm.quantidade} onChange={(e) => setCustoForm({ ...custoForm, quantidade: e.target.value })} className="rounded-lg h-9" /></div>
              </div>
              <div className="flex gap-2 pt-1"><Button type="button" variant="outline" className="flex-1 rounded-lg h-9" onClick={() => setShowCustoModal(false)}>Cancelar</Button><Button type="submit" className="flex-1 rounded-lg h-9">Salvar</Button></div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Add Membro Modal ===== */}
      {showAddMembroModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={() => setShowAddMembroModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4"><h3 className="font-heading font-bold text-base flex items-center gap-2"><Users className="h-4 w-4 text-primary" />Adicionar membro</h3><Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShowAddMembroModal(false)}><X className="h-4 w-4" /></Button></div>
            <form onSubmit={handleAddMembro} className="space-y-4">
              <CrachaLookupInline cracha={membroCracha} onCrachaChange={(v) => { setMembroCracha(v); setMembroStatus(null); }} nome={membroNome} onNomeChange={setMembroNome} status={membroStatus} onBuscar={handleBuscarMembroCracha} buscando={membroBuscando} />
              <div className="space-y-2"><Label className="text-xs">Especialidade *</Label>
                <div className="grid grid-cols-2 gap-1.5">
                  {ESPECIALIDADES.map((esp) => { const EspIcon = esp.Icon; const selected = membroEspecialidade === esp.value; return (
                    <button key={esp.value} type="button" style={selected ? { background: `${esp.color}22`, borderColor: esp.color, color: esp.color } : {}} className={`flex items-center gap-1.5 text-xs px-2.5 py-2 rounded-lg border transition-all font-medium text-left ${selected ? "" : "border-border bg-muted/50 hover:bg-muted text-foreground"}`} onClick={() => setMembroEspecialidade(esp.value)}><EspIcon className="h-3.5 w-3.5 shrink-0" />{esp.label}</button>
                  ); })}
                </div>
              </div>
              <div className="flex gap-2 pt-1"><Button type="button" variant="outline" className="flex-1 rounded-lg h-9" onClick={() => setShowAddMembroModal(false)}>Cancelar</Button><Button type="submit" className="flex-1 rounded-lg h-9" disabled={adicionandoMembro}>{adicionandoMembro && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Adicionar</Button></div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Confirm Delete Custo ===== */}
      {confirmDeleteCusto && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setConfirmDeleteCusto(null)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start gap-3 mb-4">
              <div className="w-9 h-9 rounded-full bg-red-500/10 flex items-center justify-center shrink-0"><Trash2 className="h-4 w-4 text-red-500" /></div>
              <div>
                <h3 className="font-heading font-bold text-sm">Remover item</h3>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Remover <span className="font-semibold text-foreground">{confirmDeleteCusto.descricao}</span>?
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1 rounded-lg h-9" onClick={() => setConfirmDeleteCusto(null)}>Cancelar</Button>
              <Button variant="destructive" className="flex-1 rounded-lg h-9" onClick={handleDeleteCusto} disabled={!!deletingCustoId}>
                {deletingCustoId ? <Loader2 className="h-4 w-4 animate-spin" /> : "Remover"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {bloqueioModal && <BloqueioModal data={bloqueioModal} onClose={() => setBloqueioModal(null)} onConfirm={handleBloqueioConfirm} />}
      <UpgradeDialog open={upgradeOpen} onClose={closeUpgrade} message={upgradeMessage} />
    </div>
  );
}
