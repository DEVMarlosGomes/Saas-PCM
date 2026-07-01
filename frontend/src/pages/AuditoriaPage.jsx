import { useState, useEffect, useCallback } from "react";
import { getOrdensServico, getOSAuditDossier } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import {
  Shield, Search, Loader2, RefreshCw, Wrench, Clock, CheckCircle2,
  AlertTriangle, FileCheck, ArrowRight, DollarSign, Users, Bell,
  ClipboardList, FileText, TrendingDown, X, ChevronRight,
  Activity, HardHat, Timer, BarChart2, Package, Zap, Filter,
  User, CalendarClock, Gauge, BookOpen, StickyNote,
} from "lucide-react";
import { HelpTooltip } from "../components/shared/HelpTooltip";

// ─── helpers ──────────────────────────────────────────────────────────────────

const fmt = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};
const fmtDate = (iso) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR");
};
const fmtMoney = (v) => v != null ? `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "—";
const fmtMin = (m) => {
  if (m == null) return "—";
  if (m < 60) return `${m}min`;
  const h = Math.floor(m / 60), r = m % 60;
  return r > 0 ? `${h}h ${r}min` : `${h}h`;
};

const STATUS_CFG = {
  aberta:             { label: "Aberta",         color: "bg-blue-500/10 text-blue-400 border-blue-500/20",       dot: "bg-blue-400" },
  em_atendimento:     { label: "Em Atendimento", color: "bg-amber-500/10 text-amber-400 border-amber-500/20",    dot: "bg-amber-400" },
  aguardando_peca:    { label: "Ag. Peça",       color: "bg-orange-500/10 text-orange-400 border-orange-500/20", dot: "bg-orange-400" },
  aguardando_revisao: { label: "Ag. Revisão",    color: "bg-purple-500/10 text-purple-400 border-purple-500/20", dot: "bg-purple-400" },
  revisada:           { label: "Revisada",        color: "bg-teal-500/10 text-teal-400 border-teal-500/20",       dot: "bg-teal-400" },
  fechada:            { label: "Fechada",         color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", dot: "bg-emerald-400" },
};
const TIPO_CFG = {
  corretiva:  { color: "bg-red-500/10 text-red-400 border-red-500/20" },
  preventiva: { color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  preditiva:  { color: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
};
const PRIO_CFG = {
  baixa:   { color: "text-slate-400", bar: "bg-slate-400" },
  media:   { color: "text-yellow-400", bar: "bg-yellow-400" },
  alta:    { color: "text-orange-400", bar: "bg-orange-400" },
  critica: { color: "text-red-400", bar: "bg-red-400" },
};
const TIMELINE_STATUS_CFG = {
  aberta:             { dot: "bg-blue-500",    icon: AlertTriangle, label: "OS Aberta" },
  em_atendimento:     { dot: "bg-amber-500",   icon: Wrench,        label: "Início do Atendimento" },
  aguardando_peca:    { dot: "bg-orange-500",  icon: Package,       label: "Aguardando Peça" },
  aguardando_revisao: { dot: "bg-purple-500",  icon: ClipboardList, label: "Enviada para Revisão" },
  revisada:           { dot: "bg-teal-500",    icon: CheckCircle2,  label: "Revisada" },
  fechada:            { dot: "bg-emerald-500", icon: FileCheck,     label: "Fechada" },
};
const CUSTO_TIPO_CFG = {
  consumo:      { label: "Consumível",    icon: Package, color: "text-amber-400" },
  substituicao: { label: "Substituição",  icon: Zap,     color: "text-blue-400" },
  mao_obra:     { label: "Mão de Obra",   icon: HardHat, color: "text-emerald-400" },
};
const NOTIF_CFG = {
  revisao_pendente: { color: "text-purple-400", label: "Revisão Pendente" },
  os_revisada:      { color: "text-teal-400",   label: "OS Revisada" },
  os_concluida:     { color: "text-emerald-400", label: "OS Concluída" },
  sla_expirando:    { color: "text-red-400",    label: "SLA Expirando" },
};

// ─── Componente principal ─────────────────────────────────────────────────────
export default function AuditoriaPage() {
  const [ordens, setOrdens] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterTipo, setFilterTipo] = useState("all");
  const [selectedOS, setSelectedOS] = useState(null);
  const [dossier, setDossier] = useState(null);
  const [loadingDossier, setLoadingDossier] = useState(false);
  const [activeTab, setActiveTab] = useState("timeline");

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await getOrdensServico();
      setOrdens(res.data || []);
    } catch { toast.error("Erro ao carregar ordens de serviço"); }
    finally { setLoadingList(false); }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  const selectOS = async (os) => {
    setSelectedOS(os);
    setDossier(null);
    setActiveTab("timeline");
    setLoadingDossier(true);
    try {
      const res = await getOSAuditDossier(os.id);
      setDossier(res.data);
    } catch { toast.error("Erro ao carregar dossier da OS"); }
    finally { setLoadingDossier(false); }
  };

  // ── filtered list ──────────────────────────────────────────────────────────
  const filtered = ordens.filter((o) => {
    const q = search.toLowerCase();
    const matchQ = !q ||
      String(o.numero).includes(q) ||
      (o.equipamento_nome || "").toLowerCase().includes(q) ||
      (o.equipamento_codigo || "").toLowerCase().includes(q) ||
      (o.descricao || "").toLowerCase().includes(q) ||
      (o.tecnico_nome || "").toLowerCase().includes(q);
    const matchS = filterStatus === "all" || o.status === filterStatus;
    const matchT = filterTipo === "all" || o.tipo === filterTipo;
    return matchQ && matchS && matchT;
  });

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-[calc(100vh-7rem)]" data-testid="auditoria-page">

      {/* ── Painel esquerdo: lista de OS ──────────────────────────────────── */}
      <div className="lg:w-[340px] shrink-0 flex flex-col gap-3 lg:overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-heading text-xl font-bold flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              Auditoria
            </h1>
            <p className="text-xs text-muted-foreground">{ordens.length} ordens de serviço</p>
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={loadList}>
            <RefreshCw className={`h-4 w-4 ${loadingList ? "animate-spin" : ""}`} />
          </Button>
        </div>

        {/* Filters */}
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Buscar OS, equipamento, técnico..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {[["all","Todos"],["aberta","Abertas"],["em_atendimento","Em Atend."],["fechada","Fechadas"]].map(([v,l]) => (
              <button
                key={v}
                onClick={() => setFilterStatus(v)}
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border transition-colors ${
                  filterStatus === v
                    ? "bg-primary/20 text-primary border-primary/30"
                    : "text-muted-foreground border-border/50 hover:border-border"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {[["all","Todos Tipos"],["corretiva","Corretiva"],["preventiva","Preventiva"],["preditiva","Preditiva"]].map(([v,l]) => (
              <button
                key={v}
                onClick={() => setFilterTipo(v)}
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border transition-colors ${
                  filterTipo === v
                    ? "bg-primary/20 text-primary border-primary/30"
                    : "text-muted-foreground border-border/50 hover:border-border"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        {/* OS List */}
        <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
          {loadingList ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-xs">Nenhuma OS encontrada</div>
          ) : filtered.map((os) => {
            const sc = STATUS_CFG[os.status] || STATUS_CFG.aberta;
            const tc = TIPO_CFG[os.tipo] || {};
            const isSelected = selectedOS?.id === os.id;
            return (
              <button
                key={os.id}
                onClick={() => selectOS(os)}
                className={`w-full text-left rounded-lg p-3 border transition-all hover:border-primary/40 ${
                  isSelected ? "border-primary/50 bg-primary/5 ring-1 ring-primary/20" : "border-border/50 bg-card hover:bg-muted/30"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="font-mono font-bold text-xs text-primary">#{os.numero}</span>
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${tc.color || ""}`}>
                      {os.tipo}
                    </span>
                    <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                  </div>
                </div>
                <p className="text-xs font-medium truncate">{os.equipamento_nome}</p>
                <p className="text-[10px] text-muted-foreground truncate mt-0.5">{os.descricao}</p>
                <div className="flex items-center justify-between mt-1.5">
                  <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded border ${sc.color}`}>{sc.label}</span>
                  <span className="text-[9px] text-muted-foreground">{fmtDate(os.created_at)}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Painel direito: dossier ───────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {!selectedOS ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-4">
              <Shield className="h-8 w-8 text-primary/50" />
            </div>
            <p className="font-heading font-bold text-lg text-muted-foreground">Selecione uma OS</p>
            <p className="text-sm text-muted-foreground/60 mt-1 max-w-xs">
              Clique em qualquer ordem de serviço para ver o dossier completo de auditoria
            </p>
          </div>
        ) : loadingDossier ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="h-7 w-7 animate-spin text-primary" />
          </div>
        ) : dossier ? (
          <OSDossier dossier={dossier} activeTab={activeTab} setActiveTab={setActiveTab} />
        ) : null}
      </div>
    </div>
  );
}

// ─── Dossier completo da OS ───────────────────────────────────────────────────
function OSDossier({ dossier, activeTab, setActiveTab }) {
  const { os, historico, custos, equipe, notificacoes, audit_logs } = dossier;
  const sc = STATUS_CFG[os.status] || STATUS_CFG.aberta;
  const tc = TIPO_CFG[os.tipo] || {};
  const pc = PRIO_CFG[os.prioridade] || PRIO_CFG.media;

  const totalMateriais = custos
    .filter((c) => c.tipo !== "mao_obra")
    .reduce((s, c) => s + c.total, 0);
  const totalMaoObra = os.custo_mao_obra || 0;
  const totalCustos = totalMateriais + totalMaoObra + (os.custo_parada || 0);

  const tabs = [
    { id: "timeline", label: "Timeline", icon: Activity, count: historico.length + custos.length + notificacoes.length },
    { id: "financeiro", label: "Financeiro", icon: DollarSign, count: custos.length },
    { id: "equipe", label: "Equipe", icon: Users, count: equipe.length },
    { id: "relatorio", label: "Relatório", icon: BookOpen, count: os.relatorio_o_que_foi_realizado ? 1 : 0 },
    { id: "logs", label: "Logs", icon: FileText, count: audit_logs.length },
  ];

  return (
    <div className="space-y-4">
      {/* ── Header da OS ──────────────────────────────────────────────────── */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
              <Wrench className="h-5 w-5 text-primary" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-heading font-bold text-xl text-primary">OS #{os.numero}</span>
                <Badge className={`${tc.color} text-[10px] border`}>{os.tipo}</Badge>
                <Badge className={`${sc.color} text-[10px] border`}>{sc.label}</Badge>
                {os.reincidente && (
                  <Badge className="bg-red-500/10 text-red-400 border-red-500/20 text-[10px] border">Reincidente</Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-0.5">
                <span className="font-semibold text-foreground">{os.equipamento_nome}</span>
                {os.equipamento_codigo && <span className="ml-1 text-xs">· {os.equipamento_codigo}</span>}
                {os.equipamento_localizacao && <span className="ml-1 text-xs opacity-70">· {os.equipamento_localizacao}</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`text-xs font-bold ${pc.color}`}>{(os.prioridade || "").toUpperCase()}</span>
            {os.dentro_sla === false && (
              <Badge className="bg-red-500/10 text-red-400 border-red-500/20 text-[10px] border">SLA Excedido</Badge>
            )}
            {os.dentro_sla === true && (
              <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-[10px] border">SLA OK</Badge>
            )}
          </div>
        </div>

        {/* KPIs rápidos */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <KpiCard icon={CalendarClock} label="Abertura" value={fmtDate(os.created_at)}
            tooltip="Data em que a OS foi registrada no sistema." />
          <KpiCard icon={Timer} label="Tempo Resposta" value={fmtMin(os.tempo_resposta)}
            tooltip="Tempo entre a abertura da OS e o início do atendimento pelo técnico." />
          <KpiCard icon={Gauge} label="Tempo Reparo" value={fmtMin(os.tempo_reparo)}
            tooltip="Tempo entre o início do atendimento e a conclusão efetiva do reparo." />
          <KpiCard icon={TrendingDown} label="Custo Total" value={fmtMoney(totalCustos || null)} highlight
            tooltip="Soma de materiais/peças + mão de obra do técnico + custo de parada de máquina." />
        </div>

        {/* Partes envolvidas */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
          <InfoRow icon={User} label="Solicitante" value={os.solicitante_nome} sub={os.solicitante_cracha ? `#${os.solicitante_cracha}` : null} />
          <InfoRow icon={HardHat} label="Técnico" value={os.tecnico_nome || (os.technician_employee_id ? `Matrícula ${os.technician_employee_id}` : null)} sub={os.technician_employee_id ? `Matrícula: ${os.technician_employee_id}` : null} />
          <InfoRow icon={CheckCircle2} label="Revisor" value={os.revisor_nome} sub={os.revisado_at ? fmtDate(os.revisado_at) : null} />
        </div>

        {/* Descrição */}
        <div className="mt-3 p-3 rounded-lg bg-muted/30 border border-border/50">
          <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Descrição</p>
          <p className="text-sm">{os.descricao}</p>
        </div>

        {/* Diagnóstico */}
        {(os.failure_group || os.falha_tipo || os.falha_modo || os.falha_causa) && (
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {os.failure_group && <DiagChip label="Grupo de Falha" value={os.failure_group} />}
            {os.falha_tipo    && <DiagChip label="Tipo"           value={os.falha_tipo} />}
            {os.falha_modo    && <DiagChip label="Modo"           value={os.falha_modo} />}
            {os.falha_causa   && <DiagChip label="Causa"          value={os.falha_causa} />}
          </div>
        )}
      </div>

      {/* ── Tabs ──────────────────────────────────────────────────────────── */}
      <div className="flex gap-1 overflow-x-auto border-b border-border/50 pb-0">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors ${
              activeTab === t.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
            {t.count > 0 && (
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                activeTab === t.id ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
              }`}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab Content ──────────────────────────────────────────────────── */}
      {activeTab === "timeline" && <TabTimeline os={os} historico={historico} custos={custos} notificacoes={notificacoes} audit_logs={audit_logs} equipe={equipe} />}
      {activeTab === "financeiro" && <TabFinanceiro os={os} custos={custos} totalMateriais={totalMateriais} totalMaoObra={totalMaoObra} totalCustos={totalCustos} />}
      {activeTab === "equipe" && <TabEquipe equipe={equipe} />}
      {activeTab === "relatorio" && <TabRelatorio os={os} />}
      {activeTab === "logs" && <TabLogs audit_logs={audit_logs} />}
    </div>
  );
}

// ─── Timeline ─────────────────────────────────────────────────────────────────
function TabTimeline({ os, historico, custos, notificacoes, audit_logs, equipe }) {
  // Merge all events into a single sorted array
  const events = [
    // Status changes
    ...historico.map((h) => ({
      _ts: h.timestamp,
      type: "status",
      status: h.status_novo,
      label: h.etapa_label,
      actor: h.user_nome,
    })),
    // Costs added
    ...custos.filter((c) => c.created_at).map((c) => ({
      _ts: c.created_at,
      type: "custo",
      custo: c,
    })),
    // Team added
    ...equipe.filter((m) => m.adicionado_em).map((m) => ({
      _ts: m.adicionado_em,
      type: "equipe",
      membro: m,
    })),
    // Notifications
    ...notificacoes.map((n) => ({
      _ts: n.criada_em,
      type: "notificacao",
      notif: n,
    })),
    // Report submitted
    ...(os.relatorio_preenchido_em ? [{
      _ts: os.relatorio_preenchido_em,
      type: "relatorio",
      actor: null,
    }] : []),
    // Audit logs (non-status)
    ...audit_logs.filter((l) => l.acao !== "create" && l.acao !== "status_change").map((l) => ({
      _ts: l.created_at,
      type: "audit",
      log: l,
    })),
  ].sort((a, b) => new Date(a._ts) - new Date(b._ts));

  return (
    <div className="space-y-0 relative">
      <div className="absolute left-[18px] top-0 bottom-0 w-px bg-border/40" />
      {events.length === 0 && (
        <div className="text-center py-10 text-muted-foreground text-sm">Nenhum evento registrado</div>
      )}
      {events.map((ev, i) => (
        <TimelineEvent key={i} ev={ev} />
      ))}
    </div>
  );
}

function TimelineEvent({ ev }) {
  const ts = fmt(ev._ts);

  if (ev.type === "status") {
    const cfg = TIMELINE_STATUS_CFG[ev.status] || { dot: "bg-slate-500", icon: Activity, label: ev.label };
    const Icon = cfg.icon;
    return (
      <div className="flex gap-4 pb-5 relative pl-2">
        <div className={`w-9 h-9 rounded-full ${cfg.dot}/20 border border-current flex items-center justify-center shrink-0 z-10 mt-0.5`}
          style={{ borderColor: cfg.dot.replace("bg-", "").replace("-500", "") }}>
          <Icon className="h-4 w-4" style={{ color: "inherit" }} />
        </div>
        <div className="flex-1 pt-1 min-w-0">
          <p className="text-sm font-bold">{ev.label}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />{ts}
            {ev.actor && <><span className="opacity-40">·</span><User className="h-3 w-3" />{ev.actor}</>}
          </p>
        </div>
      </div>
    );
  }

  if (ev.type === "custo") {
    const c = ev.custo;
    const cfg = CUSTO_TIPO_CFG[c.tipo] || CUSTO_TIPO_CFG.consumo;
    const Icon = cfg.icon;
    return (
      <div className="flex gap-4 pb-5 relative pl-2">
        <div className="w-9 h-9 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center shrink-0 z-10 mt-0.5">
          <DollarSign className="h-4 w-4 text-amber-400" />
        </div>
        <div className="flex-1 pt-1 min-w-0">
          <div className="flex items-center justify-between flex-wrap gap-1">
            <p className="text-sm font-semibold">
              Custo adicionado — <span className={`text-xs ${cfg.color}`}>{cfg.label}</span>
            </p>
            <span className="font-mono font-bold text-sm text-amber-400">{fmtMoney(c.total)}</span>
          </div>
          <p className="text-xs text-muted-foreground">{c.descricao}{c.quantidade > 1 ? ` · Qtd: ${c.quantidade}` : ""}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />{ts}
            {c.criado_por_nome && <><span className="opacity-40">·</span><User className="h-3 w-3" />{c.criado_por_nome}</>}
          </p>
        </div>
      </div>
    );
  }

  if (ev.type === "equipe") {
    const m = ev.membro;
    return (
      <div className="flex gap-4 pb-5 relative pl-2">
        <div className="w-9 h-9 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center shrink-0 z-10 mt-0.5">
          <Users className="h-4 w-4 text-blue-400" />
        </div>
        <div className="flex-1 pt-1">
          <p className="text-sm font-semibold">Membro adicionado à equipe</p>
          <p className="text-xs text-muted-foreground">{m.nome_membro}{m.especialidade ? ` · ${m.especialidade}` : ""}{m.cracha ? ` · #${m.cracha}` : ""}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />{ts}
            {m.adicionado_por_nome && <><span className="opacity-40">·</span><User className="h-3 w-3" />{m.adicionado_por_nome}</>}
          </p>
        </div>
      </div>
    );
  }

  if (ev.type === "notificacao") {
    const n = ev.notif;
    const cfg = NOTIF_CFG[n.tipo] || { color: "text-slate-400", label: n.tipo };
    return (
      <div className="flex gap-4 pb-5 relative pl-2">
        <div className="w-9 h-9 rounded-full bg-purple-500/10 border border-purple-500/30 flex items-center justify-center shrink-0 z-10 mt-0.5">
          <Bell className="h-4 w-4 text-purple-400" />
        </div>
        <div className="flex-1 pt-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold">{n.titulo}</p>
            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 ${cfg.color}`}>{cfg.label}</span>
          </div>
          <p className="text-xs text-muted-foreground">{n.mensagem}</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />{ts}
            {n.destinatario_nome && <><span className="opacity-40">→</span><User className="h-3 w-3" />{n.destinatario_nome}</>}
            {n.lida && <span className="text-emerald-400 text-[9px] font-bold">LIDA {n.lida_em ? fmt(n.lida_em) : ""}</span>}
          </p>
        </div>
      </div>
    );
  }

  if (ev.type === "relatorio") {
    return (
      <div className="flex gap-4 pb-5 relative pl-2">
        <div className="w-9 h-9 rounded-full bg-teal-500/10 border border-teal-500/30 flex items-center justify-center shrink-0 z-10 mt-0.5">
          <StickyNote className="h-4 w-4 text-teal-400" />
        </div>
        <div className="flex-1 pt-1">
          <p className="text-sm font-semibold">Relatório de execução preenchido</p>
          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />{ts}
          </p>
        </div>
      </div>
    );
  }

  if (ev.type === "audit") {
    const l = ev.log;
    return (
      <div className="flex gap-4 pb-5 relative pl-2">
        <div className="w-9 h-9 rounded-full bg-slate-500/10 border border-slate-500/30 flex items-center justify-center shrink-0 z-10 mt-0.5">
          <FileText className="h-4 w-4 text-slate-400" />
        </div>
        <div className="flex-1 pt-1">
          <p className="text-sm font-semibold capitalize">{l.acao.replace(/_/g, " ")}</p>
          {l.dados_novos && (
            <pre className="text-[10px] text-muted-foreground bg-muted/30 rounded p-2 mt-1 overflow-x-auto max-h-20">
              {typeof l.dados_novos === "string" ? l.dados_novos : JSON.stringify(l.dados_novos, null, 2)}
            </pre>
          )}
          <p className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
            <Clock className="h-3 w-3" />{ts}
            {l.user_nome && <><span className="opacity-40">·</span><User className="h-3 w-3" />{l.user_nome}</>}
          </p>
        </div>
      </div>
    );
  }
  return null;
}

// ─── Tab Financeiro ───────────────────────────────────────────────────────────
function TabFinanceiro({ os, custos, totalMateriais, totalMaoObra, totalCustos }) {
  const porTipo = custos.reduce((acc, c) => {
    acc[c.tipo] = (acc[c.tipo] || 0) + c.total;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {/* Resumo financeiro */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <FinCard label="Materiais" value={fmtMoney(totalMateriais)} color="text-amber-400" />
        <FinCard label="Mão de Obra" value={fmtMoney(totalMaoObra)} color="text-blue-400" />
        <FinCard label="Custo de Parada" value={fmtMoney(os.custo_parada)} color="text-red-400" />
        <FinCard label="Total Geral" value={fmtMoney(totalCustos)} color="text-primary" highlight />
      </div>

      {/* Detalhes mão de obra */}
      {(os.horas_trabalhadas || os.valor_hora_tecnico) && (
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <HardHat className="h-3.5 w-3.5" /> Mão de Obra
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div><p className="text-[10px] text-muted-foreground">Horas Trabalhadas</p><p className="font-bold">{os.horas_trabalhadas ? `${Number(os.horas_trabalhadas).toFixed(1)}h` : "—"}</p></div>
            <div><p className="text-[10px] text-muted-foreground">Valor/Hora</p><p className="font-bold">{fmtMoney(os.valor_hora_tecnico)}</p></div>
            <div><p className="text-[10px] text-muted-foreground">Total M.O.</p><p className="font-bold text-blue-400">{fmtMoney(os.custo_mao_obra)}</p></div>
          </div>
        </div>
      )}

      {/* Lista de custos */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">Itens de Custo ({custos.length})</span>
        </div>
        {custos.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground text-sm">Nenhum custo lançado</div>
        ) : (
          <div className="divide-y divide-border/30">
            {custos.map((c) => {
              const cfg = CUSTO_TIPO_CFG[c.tipo] || CUSTO_TIPO_CFG.consumo;
              const Icon = cfg.icon;
              return (
                <div key={c.id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/20 transition-colors">
                  <div className={`w-8 h-8 rounded-lg bg-muted/40 flex items-center justify-center shrink-0`}>
                    <Icon className={`h-4 w-4 ${cfg.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{c.descricao}</p>
                    <p className={`text-[10px] font-semibold ${cfg.color}`}>{cfg.label}{c.quantidade > 1 ? ` · Qtd: ${c.quantidade}` : ""}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-mono font-bold text-sm">{fmtMoney(c.total)}</p>
                    {c.quantidade > 1 && <p className="text-[10px] text-muted-foreground">{fmtMoney(c.valor)} × {c.quantidade}</p>}
                  </div>
                </div>
              );
            })}
            {/* Total row */}
            <div className="flex items-center justify-between px-4 py-3 bg-muted/20">
              <span className="text-sm font-bold">Total Materiais</span>
              <span className="font-mono font-bold text-primary">{fmtMoney(totalMateriais)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Tab Equipe ───────────────────────────────────────────────────────────────
function TabEquipe({ equipe }) {
  const espLabels = {
    eletrica: "Elétrica", mecanica: "Mecânica", civil: "Civil",
    instrumentacao: "Instrumentação", ti: "TI / Automação", outro: "Outro",
  };
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
        <Users className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">Equipe da OS ({equipe.length})</span>
      </div>
      {equipe.length === 0 ? (
        <div className="text-center py-10 text-muted-foreground text-sm">Nenhum membro registrado</div>
      ) : (
        <div className="divide-y divide-border/30">
          {equipe.map((m) => (
            <div key={m.id} className="flex items-center gap-3 px-4 py-3">
              <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0 text-sm font-bold text-primary">
                {(m.nome_membro || "?")[0].toUpperCase()}
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">{m.nome_membro}</p>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  {m.especialidade && <span className="text-[10px] text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">{espLabels[m.especialidade] || m.especialidade}</span>}
                  {m.cracha && <span className="text-[10px] font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded">#{m.cracha}</span>}
                </div>
              </div>
              <div className="text-right">
                <p className="text-[10px] text-muted-foreground">{fmt(m.adicionado_em)}</p>
                {m.adicionado_por_nome && <p className="text-[10px] text-muted-foreground">por {m.adicionado_por_nome}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Tab Relatório ────────────────────────────────────────────────────────────
function TabRelatorio({ os }) {
  if (!os.relatorio_o_que_foi_realizado && !os.relatorio_analise_problema) {
    return (
      <div className="bg-card border border-border rounded-xl p-8 text-center">
        <StickyNote className="h-8 w-8 text-muted-foreground mx-auto mb-3 opacity-40" />
        <p className="text-muted-foreground text-sm">Relatório de execução não preenchido</p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {os.relatorio_o_que_foi_realizado && (
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <ClipboardList className="h-3.5 w-3.5" /> O que foi realizado
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{os.relatorio_o_que_foi_realizado}</p>
        </div>
      )}
      {os.relatorio_analise_problema && (
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5" /> Análise do problema
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{os.relatorio_analise_problema}</p>
        </div>
      )}
      {os.review_notes && (
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" /> Notas de Revisão
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{os.review_notes}</p>
        </div>
      )}
      {os.solucao && (
        <div className="bg-card border border-border rounded-xl p-5">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5" /> Solução aplicada
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{os.solucao}</p>
        </div>
      )}
    </div>
  );
}

// ─── Tab Logs ─────────────────────────────────────────────────────────────────
function TabLogs({ audit_logs }) {
  const ACAO_CFG = {
    create:       { label: "Criação",        color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
    update:       { label: "Atualização",    color: "bg-blue-500/10 text-blue-400 border-blue-500/20" },
    delete:       { label: "Exclusão",       color: "bg-red-500/10 text-red-400 border-red-500/20" },
    auto_approve: { label: "Auto-Aprovação", color: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  };

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">Logs de Auditoria ({audit_logs.length})</span>
      </div>
      {audit_logs.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground text-sm">Nenhum log registrado</div>
      ) : (
        <div className="divide-y divide-border/30">
          {audit_logs.map((l) => {
            const cfg = ACAO_CFG[l.acao] || ACAO_CFG.update;
            let parsed = null;
            try { parsed = l.dados_novos ? JSON.parse(l.dados_novos) : null; } catch {}
            return (
              <div key={l.id} className="px-4 py-3 space-y-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <Badge className={`${cfg.color} text-[10px] border`}>{cfg.label}</Badge>
                    {l.user_nome && <span className="text-xs text-muted-foreground">{l.user_nome}</span>}
                  </div>
                  <span className="text-[10px] text-muted-foreground">{fmt(l.created_at)}</span>
                </div>
                {parsed && typeof parsed === "object" && Object.keys(parsed).length > 0 && (
                  <div className="space-y-1">
                    {Object.entries(parsed).map(([field, value]) => (
                      <div key={field} className="flex items-start gap-2 text-xs rounded bg-muted/30 px-2.5 py-1.5">
                        <span className="font-semibold text-muted-foreground min-w-[80px] shrink-0">{field}</span>
                        {typeof value === "object" && value?.de !== undefined ? (
                          <span className="flex items-center gap-1.5 min-w-0 flex-wrap">
                            <span className="bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded line-through">{String(value.de || "(vazio)")}</span>
                            <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                            <span className="bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded">{String(value.para)}</span>
                          </span>
                        ) : (
                          <span className="text-foreground/80 break-all">{typeof value === "string" ? value : JSON.stringify(value)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Micro-componentes ────────────────────────────────────────────────────────
function KpiCard({ icon: Icon, label, value, highlight, tooltip }) {
  return (
    <div className={`rounded-lg p-3 border ${highlight ? "border-primary/30 bg-primary/5" : "border-border/50 bg-muted/20"}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="h-3 w-3 text-muted-foreground" />
        <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center">
          {label}
          {tooltip && <HelpTooltip text={tooltip} />}
        </p>
      </div>
      <p className={`font-bold text-sm ${highlight ? "text-primary" : ""}`}>{value}</p>
    </div>
  );
}

function InfoRow({ icon: Icon, label, value, sub }) {
  return (
    <div className="flex items-start gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30">
      <Icon className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p className="text-[9px] font-semibold text-muted-foreground uppercase">{label}</p>
        <p className="text-xs font-medium truncate">{value || "—"}</p>
        {sub && value !== sub && <p className="text-[9px] text-muted-foreground">{sub}</p>}
      </div>
    </div>
  );
}

function DiagChip({ label, value }) {
  return (
    <div className="p-2 rounded-lg bg-muted/30 border border-border/40">
      <p className="text-[9px] font-semibold text-muted-foreground uppercase mb-0.5">{label}</p>
      <p className="text-xs font-medium capitalize">{value}</p>
    </div>
  );
}

function FinCard({ label, value, color, highlight }) {
  return (
    <div className={`rounded-xl p-4 border ${highlight ? "border-primary/30 bg-primary/5" : "border-border bg-card"}`}>
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
      <p className={`font-bold text-lg font-mono ${color || ""}`}>{value}</p>
    </div>
  );
}
