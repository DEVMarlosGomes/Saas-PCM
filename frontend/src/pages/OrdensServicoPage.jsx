import { useState, useEffect } from "react";
import {
  getOrdensServico, createOrdemServico, updateOrdemServico, getEquipamentos,
  getCustos, createCusto, deleteCusto, getPendingReviews, autoApproveExpired, buscarPorCracha,
  getOSEquipe, addOSEquipeMembro, removeOSEquipeMembro, getOSHistorico, lookupColaborador,
  reassinarTecnico, getOSExceoesArea, addOSExcecaoArea, removeOSExcecaoArea,
  getPecasOS, consumirPecaOS, getPecas, getDepositos,
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
  Trash2, Activity, HardHat, ClipboardCheck, RefreshCw,
} from "lucide-react";
import { HelpTooltip } from "../components/shared/HelpTooltip";

// ─── Áreas de manutenção ─────────────────────────────────────────────────────

// Áreas de topo (top-level)
const AREAS_MANUTENCAO = {
  eletrica:   "Elétrica",
  mecanica:   "Mecânica",
  civil:      "Civil",
  utilidades: "Utilidades",
  predial:    "Predial",
  geral:      "Geral (qualquer área)",
};

// Subáreas por área de topo
const SUBAREAS_MANUTENCAO = {
  eletrica: [
    { value: "eletrica_predial",    label: "Elétrica Predial" },
    { value: "energia_aterramento", label: "Energia / Aterramento" },
    { value: "automacao_clp",       label: "Automação / CLP" },
    { value: "instrumentacao",      label: "Instrumentação" },
    { value: "motores",             label: "Motores" },
    { value: "eletrica_industrial", label: "Elétrica Industrial" },
    { value: "estrutura_eletrica",  label: "Estrutura Elétrica" },
  ],
  mecanica: [
    { value: "mecanica_industrial", label: "Mecânica Industrial" },
    { value: "maquinas",            label: "Máquinas" },
    { value: "hidraulica",          label: "Hidráulica" },
    { value: "pneumatica",          label: "Pneumática" },
    { value: "lubrificacao",        label: "Lubrificação" },
    { value: "solda_calderaria",    label: "Solda / Calderaria" },
    { value: "usinagem_ajustagem",  label: "Usinagem / Ajustagem" },
    { value: "frota",               label: "Frota" },
  ],
};

// Map inverso: subárea → área de topo (para lookup)
const SUBAREA_PARA_AREA = Object.entries(SUBAREAS_MANUTENCAO).reduce((acc, [area, subs]) => {
  subs.forEach((s) => { acc[s.value] = area; });
  return acc;
}, {});

// Label de subárea
const SUBAREA_LABEL = Object.values(SUBAREAS_MANUTENCAO).flat().reduce((acc, s) => {
  acc[s.value] = s.label;
  return acc;
}, {});

// Keywords para verificação de compatibilidade de área (técnico vs. OS)
// hidraulica, pneumatica, instrumentacao agora são subáreas de mecanica/eletrica
const AREAS_KEYWORDS = {
  eletrica:   ["eletric", "electr"],
  mecanica:   ["mecanic", "mechan", "hidraul", "hydraul", "pneumat"],
  civil:      ["civil"],
  utilidades: ["utilidad"],
  predial:    ["predial"],
  geral:      [],
};

function stripAccents(s) {
  return s.normalize("NFD").replace(/\p{Mn}/gu, "");
}

function areaCompativel(areaOs, setor, cargo) {
  if (!areaOs || areaOs === "geral") return true;
  const keywords = AREAS_KEYWORDS[areaOs] || [];
  if (!keywords.length) return true;
  const haystack = stripAccents(`${setor || ""} ${cargo || ""}`).toLowerCase();
  return keywords.some((kw) => haystack.includes(stripAccents(kw).toLowerCase()));
}

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
        <div className="flex-1 space-y-1">
          <Label htmlFor="sol-cracha" className="text-xs flex items-center">
            Crachá / ID
            <HelpTooltip text="Número do crachá ou matrícula do operador que está abrindo a OS. Cadastre colaboradores na aba Funcionários para busca automática." side="right" />
          </Label>
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
  const FORM_RESET = { equipamento_id: "", tipo: "corretiva", prioridade: "media", descricao: "", falha_tipo: "", falha_modo: "", falha_causa: "", failure_group: "", area_manutencao: "", subarea_manutencao: "" };
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
  // Fase 1 — Peças do Almoxarifado
  const [detailPecas, setDetailPecas] = useState({ itens: [], custo_total_pecas: 0 });
  const [loadingPecas, setLoadingPecas] = useState(false);
  const [showConsumoModal, setShowConsumoModal] = useState(false);
  const [consumoForm, setConsumoForm] = useState({ peca_id: '', deposito_id: '', quantidade: '', motivo: '' });
  const [pecasCatalogo, setPecasCatalogo] = useState([]);
  const [depositosCatalogo, setDepositosCatalogo] = useState([]);
  const [loadingConsumo, setLoadingConsumo] = useState(false);
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

  // Modal de matrícula (Iniciar / Concluir OS)
  const [showMatriculaModal, setShowMatriculaModal] = useState(false);
  const [matriculaOS, setMatriculaOS]     = useState(null);
  const [matriculaTarget, setMatriculaTarget] = useState(null);
  const [matriculaInput, setMatriculaInput] = useState("");
  const [matriculaBuscando, setMatriculaBuscando] = useState(false);
  const [matriculaColaborador, setMatriculaColaborador] = useState(null);
  const [matriculaConfirmada, setMatriculaConfirmada] = useState(null);
  const [submittingMatricula, setSubmittingMatricula] = useState(false);

  // Autorizações de área (excecoes_area) — seção no drawer
  const [detailExcecoes, setDetailExcecoes] = useState([]);
  const [loadingExcecoes, setLoadingExcecoes] = useState(false);
  const [excecaoInput, setExcecaoInput] = useState("");
  const [addingExcecao, setAddingExcecao] = useState(false);
  const [removingExcecao, setRemovingExcecao] = useState(null);

  // Modal de reassinalação (Trocar Técnico — admin/líder)
  const [showReatribuirModal, setShowReatribuirModal] = useState(false);
  const [reatribuirInput, setReatribuirInput]         = useState("");
  const [reatribuirColaborador, setReatribuirColaborador] = useState(null);
  const [reatribuirBuscando, setReatribuirBuscando]   = useState(false);
  const [reatribuirMotivo, setReatribuirMotivo]       = useState("");
  const [submittingReatribuir, setSubmittingReatribuir] = useState(false);

  const canEditOS    = user?.role === "admin" || user?.role === "lider" || user?.role === "tecnico" || GRUPO_MANUTENCAO.includes(user?.role);
  const canReviewOS  = user?.role === "admin" || user?.role === "lider";
  // Líderes especializados também acessam revisão (filtrada pela área deles no backend)
  const canSeeReviews = canReviewOS || user?.role === "lider_manutencao_eletrica" || user?.role === "lider_manutencao_mecanica";
  const userCanReviewOS = (os) => {
    if (!os) return false;
    if (canReviewOS) return true;
    if (user?.role === "lider_manutencao_eletrica") return os.area_manutencao === "eletrica";
    if (user?.role === "lider_manutencao_mecanica") return os.area_manutencao === "mecanica";
    return false;
  };
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
      if (canSeeReviews) {
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
    if (!formData.equipamento_id) { toast.error("Selecione o equipamento"); return; }
    if (formData.descricao.trim().length < 35) { toast.error("Descrição deve ter no mínimo 35 caracteres"); return; }
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

  // ─── Abre modal de matrícula antes de transições críticas ────────────────
  const abrirModalMatricula = (os, newStatus) => {
    setMatriculaOS(os);
    setMatriculaTarget(newStatus);
    setMatriculaInput("");
    setMatriculaColaborador(null);
    setMatriculaConfirmada(null);
    setShowMatriculaModal(true);
  };

  // ─── Lookup de colaborador pelo input de matrícula ────────────────────────
  const handleLookupMatricula = async () => {
    if (!matriculaInput.trim()) return;
    setMatriculaBuscando(true);
    setMatriculaColaborador(null);
    try {
      const res = await lookupColaborador(matriculaInput.trim());
      setMatriculaColaborador(res.data);
      if (!res.data.encontrado) toast.warning("Matrícula não encontrada no cadastro de colaboradores");
    } catch {
      toast.error("Erro ao buscar matrícula");
    } finally {
      setMatriculaBuscando(false);
    }
  };

  // ─── Confirmar matrícula e prosseguir com a transição ─────────────────────
  const handleConfirmarMatricula = async () => {
    if (!matriculaColaborador?.encontrado) { toast.error("Confirme uma matrícula válida antes de prosseguir"); return; }
    setMatriculaConfirmada(matriculaInput.trim());
    setShowMatriculaModal(false);

    if (matriculaTarget === "aguardando_revisao") {
      // Vai para o modal de relatório com a matrícula já capturada
      setRelatorioOS(matriculaOS);
      setRelatorioTargetStatus(matriculaTarget);
      setRelForm({ o_que: "", analise: "" });
      setShowRelatorioModal(true);
    } else {
      // Transição direta (ex: em_atendimento)
      setSubmittingMatricula(true);
      try {
        await updateOrdemServico(matriculaOS.id, {
          status: matriculaTarget,
          matricula_tecnico: matriculaInput.trim(),
          area_tecnico: matriculaColaborador?.setor || matriculaColaborador?.cargo || null,
        });
        toast.success("OS aceita — técnico identificado!");
        setMatriculaConfirmada(null);
        loadData();
        if (detailOS?.id === matriculaOS.id) viewOSDetail(matriculaOS.id);
      } catch { toast.error("Erro ao atualizar status"); }
      finally { setSubmittingMatricula(false); }
    }
  };

  // ─── Busca colaborador para reassinalação ────────────────────────────────
  const handleBuscarReatribuir = async () => {
    if (!reatribuirInput.trim()) return;
    setReatribuirBuscando(true);
    setReatribuirColaborador(null);
    try {
      const res = await lookupColaborador(reatribuirInput.trim());
      setReatribuirColaborador(res.data);
      if (!res.data.encontrado) toast.warning("Matrícula não encontrada no cadastro de colaboradores");
    } catch {
      toast.error("Erro ao buscar matrícula");
    } finally {
      setReatribuirBuscando(false);
    }
  };

  // ─── Confirmar reassinalação de técnico ──────────────────────────────────
  const handleConfirmarReatribuir = async () => {
    if (!reatribuirColaborador?.encontrado) { toast.error("Confirme uma matrícula válida"); return; }
    setSubmittingReatribuir(true);
    try {
      await reassinarTecnico(detailOS.id, {
        nova_matricula: reatribuirInput.trim(),
        motivo: reatribuirMotivo.trim() || null,
      });
      toast.success("Técnico reatribuído com sucesso!");
      setShowReatribuirModal(false);
      setReatribuirInput("");
      setReatribuirColaborador(null);
      setReatribuirMotivo("");
      loadData();
      viewOSDetail(detailOS.id);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao reatribuir técnico");
    } finally {
      setSubmittingReatribuir(false);
    }
  };

  // ─── Autorizações de área ─────────────────────────────────────────────────
  const handleAddExcecao = async () => {
    if (!excecaoInput.trim()) return;
    setAddingExcecao(true);
    try {
      await addOSExcecaoArea(detailOS.id, excecaoInput.trim());
      toast.success("Crachá autorizado!");
      setExcecaoInput("");
      const [excRes] = await Promise.all([getOSExceoesArea(detailOS.id)]);
      setDetailExcecoes(excRes.data || []);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao autorizar crachá");
    } finally {
      setAddingExcecao(false);
    }
  };

  const handleRemoveExcecao = async (matricula) => {
    setRemovingExcecao(matricula);
    try {
      await removeOSExcecaoArea(detailOS.id, matricula);
      toast.success("Autorização removida");
      const excRes = await getOSExceoesArea(detailOS.id);
      setDetailExcecoes(excRes.data || []);
      loadData();
    } catch {
      toast.error("Erro ao remover autorização");
    } finally {
      setRemovingExcecao(null);
    }
  };

  // ─── Mudança de status (com interceptação para matrícula + relatório) ─────
  const handleStatusChange = async (os, newStatus) => {
    // Transições que exigem identificação do técnico
    if (
      (newStatus === "em_atendimento" && os.status === "aberta") ||
      (newStatus === "aguardando_revisao" && os.status === "em_atendimento")
    ) {
      abrirModalMatricula(os, newStatus);
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
        ...(matriculaConfirmada ? { matricula_tecnico: matriculaConfirmada } : {}),
      });
      toast.success("OS concluída com sucesso!");
      setShowRelatorioModal(false);
      setMatriculaConfirmada(null);
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

    // Fase 1 — Peças utilizadas
    setLoadingPecas(true);
    try {
      const [rPecas, rDep, rPecasOS] = await Promise.all([
        getPecas().catch(() => ({ data: [] })),
        getDepositos().catch(() => ({ data: [] })),
        getPecasOS(osId).catch(() => ({ data: { itens: [], custo_total_pecas: 0 } })),
      ]);
      setPecasCatalogo(rPecas.data || []);
      setDepositosCatalogo(rDep.data || []);
      setDetailPecas(rPecasOS.data || { itens: [], custo_total_pecas: 0 });
    } catch { setDetailPecas({ itens: [], custo_total_pecas: 0 }); }
    finally { setLoadingPecas(false); }

    // Equipe (apenas prev/pred)
    if (os.tipo === "preventiva" || os.tipo === "preditiva") {
      setLoadingEquipe(true);
      try { const eq = await getOSEquipe(osId); setDetailEquipe(eq.data || []); } catch { setDetailEquipe([]); }
      finally { setLoadingEquipe(false); }
    } else { setDetailEquipe([]); }

    // Excecoes de área (revisores de área)
    if (canSeeReviews) {
      setLoadingExcecoes(true);
      try { const excRes = await getOSExceoesArea(osId); setDetailExcecoes(excRes.data || []); } catch { setDetailExcecoes([]); }
      finally { setLoadingExcecoes(false); }
    }
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
    if (os.status === "aguardando_revisao" && !userCanReviewOS(os)) return null;
    if (os.status === "revisada"           && !userCanReviewOS(os)) return null;
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
          {canSeeReviews && pendingCount > 0 && (
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
      {canSeeReviews && pendingCount > 0 && (
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

              {/* Trocar Técnico — admin/lider */}
              {canReviewOS && ["aberta", "em_atendimento", "aguardando_peca"].includes(detailOS.status) && (
                <Button
                  variant="outline"
                  className="w-full h-9 rounded-xl text-sm font-medium border-amber-500/30 text-amber-500 hover:bg-amber-500/10 hover:border-amber-500/50"
                  onClick={() => {
                    setReatribuirInput("");
                    setReatribuirColaborador(null);
                    setReatribuirMotivo("");
                    setShowReatribuirModal(true);
                  }}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Trocar Técnico Responsável
                </Button>
              )}

              {/* Info Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Equipamento</p><p className="text-sm font-medium mt-1 truncate">{getEquipamentoNome(detailOS.equipamento_id)}</p></div>
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Tipo</p><Badge className={`${tipoConfig[detailOS.tipo]?.color} text-xs border rounded mt-1`}>{tipoConfig[detailOS.tipo]?.label}</Badge></div>
                <div className="p-3 rounded-xl bg-muted/30"><p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Prioridade</p><Badge className={`${prioridadeConfig[detailOS.prioridade]?.color} text-xs border rounded mt-1`}>{prioridadeConfig[detailOS.prioridade]?.label}</Badge></div>
                <div className="p-3 rounded-xl bg-muted/30">
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider flex items-center">
                    SLA
                    <HelpTooltip text="Service Level Agreement — prazo máximo acordado para resolução da OS. 'Fora' indica que o tempo foi excedido." side="top" />
                  </p>
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

              {/* ── Área de manutenção + autorizações (revisores) ─────────────── */}
              {canSeeReviews && (
                <div className="rounded-xl border border-border/50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2.5 bg-muted/30 border-b border-border/50">
                    <div className="flex items-center gap-2">
                      <HardHat className="h-3.5 w-3.5 text-primary" />
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Área de manutenção</p>
                    </div>
                    {detailOS.area_manutencao && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-primary/10 text-primary">
                        {AREAS_MANUTENCAO[detailOS.area_manutencao] || detailOS.area_manutencao}
                        {detailOS.subarea_manutencao && SUBAREA_LABEL[detailOS.subarea_manutencao] && (
                          <span className="text-primary/60 font-normal"> › {SUBAREA_LABEL[detailOS.subarea_manutencao]}</span>
                        )}
                      </span>
                    )}
                  </div>
                  <div className="px-4 py-4 space-y-3">
                    {!detailOS.area_manutencao && (
                      <p className="text-xs text-muted-foreground italic">Sem restrição de área — qualquer técnico pode atender.</p>
                    )}
                    {/* Lista de exceções */}
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-2">
                        Crachás autorizados fora da área
                      </p>
                      {loadingExcecoes ? (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Carregando...
                        </div>
                      ) : detailExcecoes.length === 0 ? (
                        <p className="text-xs text-muted-foreground italic">Nenhuma autorização adicional.</p>
                      ) : (
                        <div className="space-y-1.5">
                          {detailExcecoes.map((exc) => (
                            <div key={exc.matricula} className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-muted/30 border border-border/50">
                              <div className="min-w-0">
                                <p className="text-sm font-semibold truncate">{exc.colaborador_nome || exc.matricula}</p>
                                <p className="text-[10px] text-muted-foreground">
                                  Mat. <span className="font-mono">{exc.matricula}</span>
                                  {exc.autorizado_por_nome && ` · Autorizado por ${exc.autorizado_por_nome}`}
                                </p>
                              </div>
                              <button
                                className="p-1.5 rounded-lg text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors shrink-0"
                                onClick={() => handleRemoveExcecao(exc.matricula)}
                                disabled={removingExcecao === exc.matricula}
                                title="Remover autorização"
                              >
                                {removingExcecao === exc.matricula ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    {/* Adicionar novo crachá autorizado — apenas admin/lider */}
                    {canReviewOS && (
                      <div className="flex gap-2 pt-1">
                        <Input
                          placeholder="Matrícula do técnico a autorizar"
                          value={excecaoInput}
                          onChange={(e) => setExcecaoInput(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleAddExcecao()}
                          className="font-mono text-sm h-8 flex-1"
                        />
                        <Button
                          type="button"
                          size="sm"
                          className="h-8 px-3 shrink-0"
                          disabled={!excecaoInput.trim() || addingExcecao}
                          onClick={handleAddExcecao}
                        >
                          {addingExcecao ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              )}

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

              {/* ── Fase 1: Peças utilizadas (Almoxarifado) ──────────────────── */}
              {pecasCatalogo.length > 0 && (
                <div className="rounded-xl border border-border/50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2.5 bg-muted/30 border-b border-border/50">
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider flex items-center gap-1.5">
                      📦 Peças Utilizadas
                      {detailPecas.itens?.length > 0 && (
                        <span className="bg-amber-500/20 text-amber-500 text-[9px] font-bold px-1.5 py-0.5 rounded">
                          {detailPecas.itens.length}
                        </span>
                      )}
                    </p>
                    {['em_atendimento', 'aguardando_revisao'].includes(detailOS.status) && (
                      <button onClick={() => setShowConsumoModal(true)}
                        className="text-[10px] text-amber-500 hover:text-amber-400 px-2 py-1 rounded hover:bg-amber-500/10">
                        + Registrar uso
                      </button>
                    )}
                  </div>
                  <div className="px-4 py-3">
                    {loadingPecas ? (
                      <div className="flex items-center justify-center py-3">
                        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                      </div>
                    ) : detailPecas.itens?.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-2">
                        Nenhuma peça registrada para esta OS.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {detailPecas.itens.map((p, i) => (
                          <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-border/30 last:border-0">
                            <div className="flex-1 min-w-0">
                              <span className="font-mono text-amber-500 text-xs mr-1">{p.peca_codigo}</span>
                              <span className="text-foreground text-xs truncate">{p.peca_descricao}</span>
                              <div className="text-[10px] text-muted-foreground mt-0.5">
                                {p.quantidade} {p.unidade} × R$ {parseFloat(p.custo_unitario).toFixed(2)} — {p.deposito}
                              </div>
                            </div>
                            <span className="font-mono text-sm font-medium shrink-0 ml-2">
                              R$ {parseFloat(p.custo_total).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                        ))}
                        <div className="flex items-center justify-between pt-1">
                          <span className="text-xs text-muted-foreground font-semibold">Total Peças</span>
                          <span className="font-mono font-bold text-amber-500">
                            R$ {parseFloat(detailPecas.custo_total_pecas || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

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

      {/* ===== Modal Identificação do Técnico (Matrícula) ===== */}
      {showMatriculaModal && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setShowMatriculaModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
                <UserCheck className="h-5 w-5 text-emerald-500" />
              </div>
              <div>
                <h3 className="font-heading font-bold text-base">
                  {matriculaTarget === "em_atendimento" ? "Aceitar Ordem de Serviço" : "Confirmar Conclusão"}
                </h3>
                <p className="text-xs text-muted-foreground">
                  {matriculaTarget === "em_atendimento" ? "Identifique-se para iniciar o atendimento" : "Identifique-se para registrar a conclusão"}
                </p>
              </div>
            </div>

            {/* Resumo da OS */}
            {matriculaOS && (
              <div className="mb-4 rounded-lg border border-border/60 bg-muted/20 p-3">
                <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1">OS #{matriculaOS.numero}</p>
                <p className="text-sm font-semibold leading-snug">
                  {matriculaOS.equipamento_nome || getEquipamentoNome(matriculaOS.equipamento_id)}
                </p>
                {matriculaOS.descricao && (
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{matriculaOS.descricao}</p>
                )}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <Label className="text-xs font-semibold text-muted-foreground">Matrícula / Registro</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    placeholder="Ex: TEC-001 ou 12345"
                    value={matriculaInput}
                    onChange={(e) => { setMatriculaInput(e.target.value); setMatriculaColaborador(null); }}
                    onKeyDown={(e) => e.key === "Enter" && handleLookupMatricula()}
                    className="font-mono flex-1"
                    autoFocus
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 px-3"
                    disabled={!matriculaInput.trim() || matriculaBuscando}
                    onClick={handleLookupMatricula}
                  >
                    {matriculaBuscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {matriculaColaborador && (() => {
                const areaOs = matriculaTarget === "em_atendimento" ? matriculaOS?.area_manutencao : null;
                const naturalOk = areaCompativel(areaOs, matriculaColaborador?.setor, matriculaColaborador?.cargo);
                const isExcecao = (matriculaOS?.excecoes_area_matriculas || []).includes(matriculaInput.trim());
                const showAreaWarn = matriculaColaborador.encontrado && !!areaOs && areaOs !== "geral" && !naturalOk;
                const areaOk = !showAreaWarn || isExcecao;
                return (
                  <div className="space-y-2">
                    <div className={`rounded-lg p-3 border ${matriculaColaborador.encontrado
                      ? areaOk ? "bg-emerald-500/10 border-emerald-500/20" : "bg-amber-500/10 border-amber-500/20"
                      : "bg-red-500/10 border-red-500/20 text-red-400 text-sm"
                    }`}>
                      {matriculaColaborador.encontrado ? (
                        <div>
                          <p className={`font-bold text-base ${areaOk ? "text-emerald-400" : "text-amber-400"}`}>
                            {matriculaColaborador.nome}
                          </p>
                          {(matriculaColaborador.cargo || matriculaColaborador.setor) && (
                            <p className={`text-xs mt-0.5 ${areaOk ? "text-emerald-500/80" : "text-amber-500/80"}`}>
                              {[matriculaColaborador.cargo, matriculaColaborador.setor].filter(Boolean).join(" · ")}
                            </p>
                          )}
                        </div>
                      ) : (
                        <p>Matrícula não encontrada. Verifique o cadastro de colaboradores.</p>
                      )}
                    </div>
                    {showAreaWarn && !isExcecao && (
                      <div className="rounded-lg p-3 border border-amber-500/20 bg-amber-500/5 text-xs text-amber-400 space-y-1">
                        <p className="font-semibold">⚠ Área incompatível — acesso bloqueado</p>
                        <p>Esta OS requer manutenção <strong>{AREAS_MANUTENCAO[areaOs] || areaOs}</strong>. Área registrada do técnico: <strong>{matriculaColaborador.setor || matriculaColaborador.cargo || "não definida"}</strong>.</p>
                        <p className="text-amber-500/70">Solicite ao líder técnico ou admin para adicionar seu crachá nas autorizações desta OS.</p>
                      </div>
                    )}
                    {showAreaWarn && isExcecao && (
                      <div className="rounded-lg p-3 border border-emerald-500/20 bg-emerald-500/5 text-xs text-emerald-400">
                        ✓ Liberado pelo líder/admin para atender esta OS fora da área habitual
                      </div>
                    )}

                    <div className="flex gap-3 pt-1">
                      <Button type="button" variant="outline" className="flex-1" onClick={() => setShowMatriculaModal(false)}>
                        Cancelar
                      </Button>
                      <Button
                        className="flex-1"
                        disabled={!matriculaColaborador?.encontrado || submittingMatricula || !areaOk}
                        onClick={handleConfirmarMatricula}
                      >
                        {submittingMatricula && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                        {matriculaTarget === "em_atendimento" ? "Aceitar e Iniciar OS" : "Confirmar Conclusão"}
                      </Button>
                    </div>
                  </div>
                );
              })()}

              {!matriculaColaborador && (
                <div className="flex gap-3 pt-1">
                  <Button type="button" variant="outline" className="flex-1" onClick={() => setShowMatriculaModal(false)}>
                    Cancelar
                  </Button>
                  <Button className="flex-1" disabled onClick={handleConfirmarMatricula}>
                    {matriculaTarget === "em_atendimento" ? "Aceitar e Iniciar OS" : "Confirmar Conclusão"}
                  </Button>
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
                <div className="space-y-2">
                  <Label className="flex items-center">
                    Tipo
                    <HelpTooltip text="Corretiva: falha já ocorreu. Preventiva: manutenção agendada para prevenir falhas. Preditiva: baseada em monitoramento de condição." />
                  </Label>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(tipoConfig).filter(([k]) => tiposPermitidos.includes(k)).map(([k, v]) => (<button key={k} type="button" data-testid={`os-tipo-${k}`} className={`text-xs px-3 py-2 rounded-lg border transition-all font-medium ${formData.tipo === k ? "bg-primary text-primary-foreground border-primary" : "border-border bg-muted/50 hover:bg-muted"}`} onClick={() => setFormData({ ...formData, tipo: k })}>{v.label}</button>))}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="flex items-center">
                    Prioridade
                    <HelpTooltip text="Crítica: parada total de produção. Alta: risco iminente. Média: degradação de desempenho. Baixa: sem impacto imediato." />
                  </Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {Object.entries(prioridadeConfig).map(([k, v]) => (<button key={k} type="button" className={`text-xs px-2 py-2 rounded-lg border transition-all font-medium ${formData.prioridade === k ? "bg-primary text-primary-foreground border-primary" : "border-border bg-muted/50 hover:bg-muted"}`} onClick={() => setFormData({ ...formData, prioridade: k })}>{v.label}</button>))}
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <Label className="flex items-center">
                  Descrição *
                  <HelpTooltip text="Descreva o problema ou serviço com clareza suficiente para o técnico entender a ocorrência sem precisar perguntar. Mínimo 35, máximo 500 caracteres." />
                </Label>
                <Textarea
                  value={formData.descricao}
                  onChange={(e) => setFormData({ ...formData, descricao: e.target.value.slice(0, 500) })}
                  placeholder="Descreva o problema ou serviço com detalhes: local, sintoma observado, quando ocorreu..."
                  className="rounded-lg"
                  rows={3}
                  maxLength={500}
                  data-testid="os-descricao-input"
                />
                <p className={`text-[11px] flex justify-between ${formData.descricao.length < 35 ? "text-destructive" : "text-muted-foreground"}`}>
                  <span>{formData.descricao.length < 35 ? `Faltam ${35 - formData.descricao.length} para o mínimo` : "✓ Mínimo atingido"}</span>
                  <span>{formData.descricao.length} / 500</span>
                </p>
              </div>
              <div className="space-y-2"><Label className="flex items-center">Grupo de Falha *{" "}{!formData.failure_group && <span className="text-destructive text-xs font-normal ml-1">(obrigatório)</span>}<HelpTooltip text="Classifica a natureza da falha para evitar que duas OS do mesmo grupo coexistam no mesmo equipamento. Usado em análises de confiabilidade." /></Label>
                <div className="flex flex-wrap gap-2" data-testid="failure-group-chips">
                  {FAILURE_GROUPS.map((fg) => (<button key={fg.value} type="button" data-testid={`fg-chip-${fg.value}`} style={formData.failure_group === fg.value ? { background: `${fg.color}22`, borderColor: fg.color, color: fg.color } : {}} className={`text-xs px-3 py-1.5 rounded-lg border transition-all font-semibold ${formData.failure_group === fg.value ? "" : "border-border bg-muted/50 hover:bg-muted text-foreground"}`} onClick={() => setFormData({ ...formData, failure_group: fg.value })}>{fg.label}</button>))}
                </div>
              </div>
              <div className="space-y-2">
                <Label className="flex items-center text-xs font-semibold">
                  Área de manutenção
                  <HelpTooltip text="Define qual área técnica deve resolver esta OS. Técnicos de outras áreas serão bloqueados ao tentar aceitar, salvo autorização do líder ou admin." />
                  <span className="text-muted-foreground font-normal ml-1">(opcional)</span>
                </Label>
                {/* Passo 1 — área de topo */}
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(AREAS_MANUTENCAO).map(([k, v]) => (
                    <button
                      key={k}
                      type="button"
                      className={`text-xs px-3 py-1.5 rounded-lg border transition-all font-medium ${formData.area_manutencao === k
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border bg-muted/50 hover:bg-muted text-foreground"}`}
                      onClick={() => setFormData({
                        ...formData,
                        area_manutencao: formData.area_manutencao === k ? "" : k,
                        subarea_manutencao: "",
                      })}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                {/* Passo 2 — subárea (apenas se área selecionada tiver subáreas) */}
                {formData.area_manutencao && SUBAREAS_MANUTENCAO[formData.area_manutencao] && (
                  <div className="pl-3 border-l-2 border-primary/30 mt-1">
                    <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider mb-1.5">
                      Subárea de {AREAS_MANUTENCAO[formData.area_manutencao]}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {SUBAREAS_MANUTENCAO[formData.area_manutencao].map((s) => (
                        <button
                          key={s.value}
                          type="button"
                          className={`text-xs px-3 py-1.5 rounded-lg border transition-all font-medium ${formData.subarea_manutencao === s.value
                            ? "bg-primary/80 text-primary-foreground border-primary/80"
                            : "border-border bg-muted/30 hover:bg-muted text-foreground"}`}
                          onClick={() => setFormData({
                            ...formData,
                            subarea_manutencao: formData.subarea_manutencao === s.value ? "" : s.value,
                          })}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
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

      {/* ===== Modal Reassinalação de Técnico ===== */}
      {showReatribuirModal && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={() => setShowReatribuirModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm shadow-2xl animate-slide-in-bottom" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
                <RefreshCw className="h-5 w-5 text-amber-500" />
              </div>
              <div>
                <h3 className="font-heading font-bold text-base">Trocar Técnico Responsável</h3>
                <p className="text-xs text-muted-foreground">
                  OS #{detailOS?.numero} · {detailOS && (detailOS.equipamento_nome || getEquipamentoNome(detailOS.equipamento_id))}
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <Label className="text-xs font-semibold text-muted-foreground">Matrícula do novo técnico</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    placeholder="Ex: TEC-001 ou 12345"
                    value={reatribuirInput}
                    onChange={(e) => { setReatribuirInput(e.target.value); setReatribuirColaborador(null); }}
                    onKeyDown={(e) => e.key === "Enter" && handleBuscarReatribuir()}
                    className="font-mono flex-1"
                    autoFocus
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 px-3"
                    disabled={!reatribuirInput.trim() || reatribuirBuscando}
                    onClick={handleBuscarReatribuir}
                  >
                    {reatribuirBuscando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {reatribuirColaborador && (
                <div className={`rounded-lg p-3 border ${reatribuirColaborador.encontrado
                  ? "bg-emerald-500/10 border-emerald-500/20"
                  : "bg-red-500/10 border-red-500/20 text-red-400 text-sm"
                }`}>
                  {reatribuirColaborador.encontrado ? (
                    <div>
                      <p className="font-bold text-base text-emerald-400">{reatribuirColaborador.nome}</p>
                      {(reatribuirColaborador.cargo || reatribuirColaborador.setor) && (
                        <p className="text-xs text-emerald-500/80 mt-0.5">
                          {[reatribuirColaborador.cargo, reatribuirColaborador.setor].filter(Boolean).join(" · ")}
                        </p>
                      )}
                    </div>
                  ) : (
                    <p>Matrícula não encontrada. Verifique o cadastro de colaboradores.</p>
                  )}
                </div>
              )}

              <div>
                <Label className="text-xs font-semibold text-muted-foreground">
                  Motivo da troca <span className="font-normal text-muted-foreground/60">(opcional)</span>
                </Label>
                <Input
                  className="mt-1 text-sm"
                  placeholder="Ex: categoria de manutenção incorreta"
                  value={reatribuirMotivo}
                  onChange={(e) => setReatribuirMotivo(e.target.value)}
                />
              </div>

              <div className="flex gap-3 pt-1">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setShowReatribuirModal(false)}>
                  Cancelar
                </Button>
                <Button
                  className="flex-1"
                  disabled={!reatribuirColaborador?.encontrado || submittingReatribuir}
                  onClick={handleConfirmarReatribuir}
                >
                  {submittingReatribuir && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  Confirmar Troca
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {bloqueioModal && <BloqueioModal data={bloqueioModal} onClose={() => setBloqueioModal(null)} onConfirm={handleBloqueioConfirm} />}
      <UpgradeDialog open={upgradeOpen} onClose={closeUpgrade} message={upgradeMessage} />

      {/* ===== Modal Consumo de Peça em OS (Almoxarifado Fase 1) ===== */}
      {showConsumoModal && (
        <div className="fixed inset-0 z-[65] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setShowConsumoModal(false)}>
          <div className="bg-card border border-border rounded-xl p-6 w-full max-w-sm shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <h2 className="text-base font-semibold mb-4">📦 Registrar Uso de Peça</h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Peça *</label>
                <select className="w-full bg-background border border-border rounded-lg px-3 py-2 text-foreground text-sm"
                  value={consumoForm.peca_id}
                  onChange={e => setConsumoForm(f => ({ ...f, peca_id: e.target.value }))}>
                  <option value="">Selecione a peça…</option>
                  {pecasCatalogo.map(p => (
                    <option key={p.id} value={p.id}>{p.codigo} — {p.descricao} (saldo: {p.saldo_total} {p.unidade})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Depósito *</label>
                <select className="w-full bg-background border border-border rounded-lg px-3 py-2 text-foreground text-sm"
                  value={consumoForm.deposito_id}
                  onChange={e => setConsumoForm(f => ({ ...f, deposito_id: e.target.value }))}>
                  <option value="">Selecione o depósito…</option>
                  {depositosCatalogo.map(d => <option key={d.id} value={d.id}>{d.nome}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Quantidade *</label>
                <input type="number" step="0.001" min="0.001"
                  className="w-full bg-background border border-border rounded-lg px-3 py-2 text-foreground text-sm"
                  value={consumoForm.quantidade}
                  onChange={e => setConsumoForm(f => ({ ...f, quantidade: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs text-muted-foreground mb-1 block">Motivo (opcional)</label>
                <input className="w-full bg-background border border-border rounded-lg px-3 py-2 text-foreground text-sm"
                  placeholder="Ex: Substituição de rolamento…"
                  value={consumoForm.motivo}
                  onChange={e => setConsumoForm(f => ({ ...f, motivo: e.target.value }))} />
              </div>
              <div className="flex gap-2 pt-2">
                <button onClick={() => setShowConsumoModal(false)}
                  className="flex-1 px-4 py-2 rounded-lg border border-border text-muted-foreground hover:bg-muted text-sm">
                  Cancelar
                </button>
                <button disabled={loadingConsumo || !consumoForm.peca_id || !consumoForm.deposito_id || !consumoForm.quantidade}
                  onClick={async () => {
                    if (!consumoForm.peca_id || !consumoForm.deposito_id || !consumoForm.quantidade) return;
                    setLoadingConsumo(true);
                    try {
                      await consumirPecaOS(detailOS.id, {
                        peca_id: consumoForm.peca_id,
                        deposito_id: consumoForm.deposito_id,
                        quantidade: parseFloat(consumoForm.quantidade),
                        motivo: consumoForm.motivo || undefined,
                      });
                      setShowConsumoModal(false);
                      setConsumoForm({ peca_id: '', deposito_id: '', quantidade: '', motivo: '' });
                      // Recarrega peças da OS
                      const rPecasOS = await getPecasOS(detailOS.id);
                      setDetailPecas(rPecasOS.data || { itens: [], custo_total_pecas: 0 });
                      toast.success('Peça registrada com sucesso!');
                    } catch (e) {
                      toast.error(e.response?.data?.detail || 'Erro ao registrar peça.');
                    } finally {
                      setLoadingConsumo(false);
                    }
                  }}
                  className="flex-1 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium disabled:opacity-50">
                  {loadingConsumo ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : 'Confirmar'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
