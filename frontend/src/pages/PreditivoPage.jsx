import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Activity, Lock, Loader2, RefreshCw, CheckCircle2,
  X, Eye, Wrench, Settings, Plus,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from "recharts";
import {
  getPreditivoDashboard, getSaudeEquipamentos, getAlertasPreditivos,
  gerarOsAlerta, ignorarAlerta, getConfigsMonitoramento,
  createConfigMonitoramento, updateConfigMonitoramento,
  getHistoricoLeituras,
} from "../lib/api";

// ─── helpers ────────────────────────────────────────────────────────────────

const STATUS_COLOR = { NORMAL: "#22C55E", ATENCAO: "#F59E0B", CRITICO: "#EF4444" };
const SEV_COLOR = { ATENCAO: "#F59E0B", CRITICO: "#EF4444" };

function fmtRUL(d) {
  if (d == null) return "—";
  if (d === 0) return "CRÍTICO";
  return `${d}d`;
}

// ─── UpgradeGate ────────────────────────────────────────────────────────────

function UpgradeGate() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-5 text-center">
      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
        <Lock className="h-7 w-7 text-primary" />
      </div>
      <div className="max-w-sm space-y-1.5">
        <h2 className="font-heading text-xl font-bold">Análise Preditiva</h2>
        <p className="text-muted-foreground text-sm">
          Disponível a partir do plano <strong className="text-foreground">Profissional</strong>.
        </p>
      </div>
      <Button onClick={() => navigate("/billing")} className="rounded-lg shadow-lg shadow-primary/20"
        data-testid="upgrade-btn-preditivo">Ver planos</Button>
    </div>
  );
}

// ─── KpiCard ────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color }) {
  return (
    <div className="border border-border/50 rounded-xl bg-card p-5 space-y-1">
      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</p>
      <p className="text-3xl font-heading font-bold" style={{ color: color || "inherit" }}>{value ?? "—"}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

// ─── HealthCard ─────────────────────────────────────────────────────────────

function HealthCard({ equip, onSelect, selected }) {
  const saude = equip.status_saude || "NORMAL";
  const color = STATUS_COLOR[saude];
  return (
    <div
      onClick={() => onSelect(equip)}
      data-testid={`health-card-${equip.id}`}
      style={{ borderColor: color, borderWidth: 2, borderStyle: "solid" }}
      className={`relative rounded-xl bg-card p-4 cursor-pointer transition-all hover:shadow-lg
        ${selected ? "ring-2 ring-primary ring-offset-2 ring-offset-background" : ""}`}
    >
      {saude !== "NORMAL" && (
        <span className="absolute top-2 right-2 text-[10px] font-bold px-1.5 py-0.5 rounded-full"
          style={{ background: color + "22", color }}>
          {saude}
        </span>
      )}
      <p className="text-sm font-semibold truncate pr-12">{equip.nome}</p>
      <p className="text-[11px] text-muted-foreground">{equip.codigo}</p>
      {equip.monitoramento_ativo ? (
        <div className="mt-2 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
          <span className="text-[11px] text-muted-foreground">RUL: {fmtRUL(equip.rul_estimado_dias)}</span>
        </div>
      ) : (
        <p className="text-[10px] text-muted-foreground/40 mt-1">Sem monitoramento</p>
      )}
    </div>
  );
}

// ─── TrendDrawer ─────────────────────────────────────────────────────────────

function TrendDrawer({ equip, config, onClose }) {
  const [leituras, setLeituras] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!equip) return;
    setLoading(true);
    getHistoricoLeituras(equip.id, { parametro: config?.parametro_nome, dias: 30 })
      .then(r => setLeituras(r.data))
      .catch(() => toast.error("Erro ao carregar histórico"))
      .finally(() => setLoading(false));
  }, [equip, config]);

  const chartData = leituras.map(l => ({
    t: new Date(l.timestamp).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
    valor: l.valor,
  }));

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] z-50 bg-card border-l border-border shadow-2xl flex flex-col"
      data-testid="trend-drawer">
      <div className="flex items-center justify-between p-5 border-b border-border/50">
        <div>
          <h3 className="font-heading font-bold">{equip?.nome}</h3>
          <p className="text-xs text-muted-foreground">{equip?.codigo} · Tendência 30 dias</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} data-testid="btn-fechar-drawer">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {config && (
        <div className="px-5 py-2 flex gap-2 text-xs">
          <span className="px-2 py-1 rounded bg-amber-500/10 text-amber-500">
            Atenção: {config.threshold_atencao} {config.unidade}
          </span>
          <span className="px-2 py-1 rounded bg-red-500/10 text-red-500">
            Crítico: {config.threshold_critico} {config.unidade}
          </span>
        </div>
      )}

      <div className="flex-1 p-5 overflow-y-auto">
        {loading ? (
          <div className="flex justify-center items-center h-40">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : leituras.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center mt-10">Sem leituras nos últimos 30 dias</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="t" tick={{ fontSize: 10, fill: "#8DA4C4" }} />
              <YAxis tick={{ fontSize: 10, fill: "#8DA4C4" }} />
              <Tooltip
                contentStyle={{ background: "#0D1626", border: "1px solid #1E3054", borderRadius: 8 }}
                labelStyle={{ color: "#F0F6FF" }} itemStyle={{ color: "#2E90FA" }}
              />
              <Line type="monotone" dataKey="valor" stroke="#2E90FA" strokeWidth={2} dot={false} />
              {config && (
                <ReferenceLine y={config.threshold_atencao} stroke="#F59E0B" strokeDasharray="4 2"
                  label={{ value: "Atenção", fill: "#F59E0B", fontSize: 10 }} />
              )}
              {config && (
                <ReferenceLine y={config.threshold_critico} stroke="#EF4444" strokeDasharray="4 2"
                  label={{ value: "Crítico", fill: "#EF4444", fontSize: 10 }} />
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

// ─── ConfigModal ─────────────────────────────────────────────────────────────

function ConfigModal({ equip, existing, equipamentos, onClose, onSaved }) {
  const [form, setForm] = useState({
    equipamento_id: equip?.id || existing?.equipamento_id || "",
    parametro_nome: existing?.parametro_nome || "",
    unidade: existing?.unidade || "",
    threshold_atencao: existing?.threshold_atencao ?? "",
    threshold_critico: existing?.threshold_critico ?? "",
    tendencia_janela_dias: existing?.tendencia_janela_dias ?? 7,
  });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    if (!form.equipamento_id || !form.parametro_nome || form.threshold_atencao === "" || form.threshold_critico === "") {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form, threshold_atencao: +form.threshold_atencao, threshold_critico: +form.threshold_critico };
      if (existing) await updateConfigMonitoramento(existing.id, payload);
      else await createConfigMonitoramento(payload);
      toast.success("Configuração salva!");
      onSaved();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === "object" ? detail.mensagem : detail || "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  const params_sugeridos = ["temperatura_rolamento", "vibracao_rms", "corrente_motor", "pressao_oleo", "nivel_ruido"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      data-testid="config-modal">
      <div className="bg-card border border-border rounded-2xl w-full max-w-md p-6 space-y-4 m-4">
        <div className="flex items-center justify-between">
          <h3 className="font-heading font-bold">Configurar Monitoramento</h3>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>

        <div className="space-y-3">
          <div>
            <Label className="text-xs">Equipamento</Label>
            <select className="w-full h-10 rounded-lg border border-border bg-muted text-sm px-3 mt-1"
              value={form.equipamento_id} onChange={e => set("equipamento_id", e.target.value)}
              disabled={!!equip} data-testid="select-equipamento">
              <option value="">Selecione...</option>
              {equipamentos.map(e => <option key={e.id} value={e.id}>{e.nome}</option>)}
            </select>
          </div>

          <div>
            <Label className="text-xs">Parâmetro</Label>
            <select className="w-full h-10 rounded-lg border border-border bg-muted text-sm px-3 mt-1"
              value={form.parametro_nome} onChange={e => set("parametro_nome", e.target.value)}
              data-testid="select-parametro">
              <option value="">Selecione...</option>
              {params_sugeridos.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <Input className="h-9 rounded-lg mt-1 text-xs" placeholder="Ou digite o nome do parâmetro"
              value={form.parametro_nome} onChange={e => set("parametro_nome", e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Unidade</Label>
              <Input className="h-9 rounded-lg mt-1" placeholder="°C / mm/s / A"
                value={form.unidade} onChange={e => set("unidade", e.target.value)} />
            </div>
            <div>
              <Label className="text-xs">Janela tendência (dias)</Label>
              <Input type="number" min={3} max={30} className="h-9 rounded-lg mt-1"
                value={form.tendencia_janela_dias} onChange={e => set("tendencia_janela_dias", +e.target.value)} />
            </div>
            <div>
              <Label className="text-xs">Threshold Atenção *</Label>
              <Input type="number" className="h-9 rounded-lg mt-1" placeholder="Ex: 70"
                value={form.threshold_atencao} onChange={e => set("threshold_atencao", e.target.value)}
                data-testid="input-threshold-atencao" />
            </div>
            <div>
              <Label className="text-xs">Threshold Crítico *</Label>
              <Input type="number" className="h-9 rounded-lg mt-1" placeholder="Ex: 85"
                value={form.threshold_critico} onChange={e => set("threshold_critico", e.target.value)}
                data-testid="input-threshold-critico" />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancelar</Button>
          <Button size="sm" onClick={handleSave} disabled={saving} data-testid="btn-salvar-config">
            {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
            Salvar
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function PreditivoPage() {
  const { user } = useAuth();
  const [locked, setLocked] = useState(false);
  const [loading, setLoading] = useState(true);

  const [dashboard, setDashboard] = useState(null);
  const [equipamentos, setEquipamentos] = useState([]);
  const [alertas, setAlertas] = useState([]);
  const [configs, setConfigs] = useState([]);

  const [selectedEquip, setSelectedEquip] = useState(null);
  const [showDrawer, setShowDrawer] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [editConfig, setEditConfig] = useState(null);
  const [tab, setTab] = useState("saude");
  const [ignorandoId, setIgnorandoId] = useState(null);
  const [gerandoId, setGerandoId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, equips, alts, cfgs] = await Promise.all([
        getPreditivoDashboard().catch(() => ({ data: null })),
        getSaudeEquipamentos().catch(() => ({ data: [] })),
        getAlertasPreditivos().catch(() => ({ data: [] })),
        getConfigsMonitoramento().catch(() => ({ data: [] })),
      ]);
      setDashboard(dash.data);
      setEquipamentos(equips.data);
      setAlertas(alts.data);
      setConfigs(cfgs.data);
    } catch (err) {
      if (err.response?.status === 402 || err.response?.status === 403) setLocked(true);
      else toast.error("Erro ao carregar módulo preditivo");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.features?.modulo_preditivo === false) { setLocked(true); setLoading(false); return; }
    load();
  }, [load, user]);

  const handleIgnorar = async (alerta) => {
    const motivo = window.prompt("Motivo para ignorar este alerta (mínimo 10 caracteres):");
    if (!motivo || motivo.trim().length < 10) { toast.warning("Motivo insuficiente"); return; }
    setIgnorandoId(alerta.id);
    try {
      await ignorarAlerta(alerta.id, motivo);
      toast.success("Alerta ignorado");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro");
    } finally {
      setIgnorandoId(null);
    }
  };

  const handleGerarOS = async (alerta) => {
    setGerandoId(alerta.id);
    try {
      const r = await gerarOsAlerta(alerta.id);
      toast.success(r.data.mensagem);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao gerar OS");
    } finally {
      setGerandoId(null);
    }
  };

  const getConfigForEquip = (equipId) =>
    configs.find(c => c.equipamento_id === equipId) || null;

  if (locked) return <UpgradeGate />;

  if (loading) return (
    <div className="flex justify-center items-center h-64">
      <Loader2 className="h-7 w-7 animate-spin text-primary" />
    </div>
  );

  const isAdmin = user?.role === "admin" || user?.role === "lider";

  return (
    <div className="space-y-6" data-testid="preditivo-page">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Activity className="h-6 w-6 text-primary" />
          <div>
            <h1 className="font-heading text-2xl font-bold">Análise Preditiva</h1>
            <p className="text-muted-foreground text-sm">
              Motor de confiabilidade com threshold, tendência e z-score
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {isAdmin && (
            <Button variant="outline" size="sm" className="h-9 gap-2"
              onClick={() => { setEditConfig(null); setShowConfig(true); }}
              data-testid="btn-nova-config">
              <Plus className="h-3.5 w-3.5" /> Configurar monitoramento
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={load} className="h-9 gap-2"
            data-testid="btn-refresh-preditivo">
            <RefreshCw className="h-3.5 w-3.5" /> Atualizar
          </Button>
        </div>
      </div>

      {/* KPIs */}
      {dashboard && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard label="Monitorados" value={dashboard.total_equipamentos_monitorados}
            sub="equipamentos ativos" />
          <KpiCard label="Em Atenção" value={dashboard.equipamentos_atencao}
            color="#F59E0B" sub="threshold atenção violado" />
          <KpiCard label="Críticos" value={dashboard.equipamentos_critico}
            color="#EF4444" sub="ação imediata necessária" />
          <KpiCard label="Alertas abertos" value={dashboard.alertas_abertos}
            sub={`${dashboard.alertas_criticos_abertos} críticos`}
            color={dashboard.alertas_criticos_abertos > 0 ? "#EF4444" : undefined} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border/50">
        {[
          ["saude", "Saúde da Frota"],
          ["alertas", `Alertas (${alertas.length})`],
          ["config", "Configurações"],
        ].map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            data-testid={`tab-preditivo-${k}`}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
              ${tab === k
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {label}
          </button>
        ))}
      </div>

      {/* TAB: Saúde */}
      {tab === "saude" && (
        equipamentos.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground text-sm">
            Nenhum equipamento encontrado. Configure o monitoramento para começar.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {equipamentos.map(e => (
              <HealthCard key={e.id} equip={e}
                selected={selectedEquip?.id === e.id}
                onSelect={(eq) => { setSelectedEquip(eq); setShowDrawer(true); }} />
            ))}
          </div>
        )
      )}

      {/* TAB: Alertas */}
      {tab === "alertas" && (
        <div className="border border-border/50 rounded-xl overflow-hidden">
          {alertas.length === 0 ? (
            <div className="flex flex-col items-center py-12 gap-3 text-muted-foreground">
              <CheckCircle2 className="h-10 w-10 text-emerald-500" />
              <p className="text-sm">Nenhum alerta aberto. Frota saudável.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 bg-muted/30">
                    {["Equipamento", "Parâmetro", "Valor atual", "Tendência", "RUL", "Ações"].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {alertas.map(a => (
                    <tr key={a.id} className="border-b border-border/30 hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-3 font-medium">{a.equipamento_nome}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-mono">{a.parametro_nome}</span>
                        <span className="ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                          style={{ background: SEV_COLOR[a.severidade] + "22", color: SEV_COLOR[a.severidade] }}>
                          {a.severidade}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{a.valor_atual}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-semibold ${
                          a.tendencia === "CRITICA" ? "text-red-400"
                          : a.tendencia === "CRESCENTE" ? "text-amber-400"
                          : "text-emerald-400"}`}>
                          {a.tendencia}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs"
                        style={{ color: a.rul_estimado_dias != null && a.rul_estimado_dias < 3 ? "#EF4444" : undefined }}>
                        {fmtRUL(a.rul_estimado_dias)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1.5">
                          <Button size="sm" className="h-7 text-xs gap-1 px-2"
                            onClick={() => handleGerarOS(a)} disabled={gerandoId === a.id}
                            data-testid={`btn-gerar-os-${a.id}`}>
                            {gerandoId === a.id
                              ? <Loader2 className="h-3 w-3 animate-spin" />
                              : <Wrench className="h-3 w-3" />}
                            OS
                          </Button>
                          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 px-2 text-muted-foreground"
                            onClick={() => handleIgnorar(a)} disabled={ignorandoId === a.id}
                            data-testid={`btn-ignorar-${a.id}`}>
                            {ignorandoId === a.id
                              ? <Loader2 className="h-3 w-3 animate-spin" />
                              : <X className="h-3 w-3" />}
                            Ignorar
                          </Button>
                          <Button variant="outline" size="sm" className="h-7 text-xs gap-1 px-2"
                            onClick={() => {
                              const eq = equipamentos.find(e => e.id === a.equipamento_id)
                                || { id: a.equipamento_id, nome: a.equipamento_nome, codigo: "" };
                              setSelectedEquip(eq);
                              setShowDrawer(true);
                            }} data-testid={`btn-historico-${a.id}`}>
                            <Eye className="h-3 w-3" /> Ver
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB: Configurações */}
      {tab === "config" && (
        <div className="border border-border/50 rounded-xl overflow-hidden">
          {configs.length === 0 ? (
            <div className="flex flex-col items-center py-12 gap-3 text-muted-foreground">
              <Settings className="h-10 w-10 opacity-30" />
              <p className="text-sm">Nenhum monitoramento configurado ainda.</p>
              {isAdmin && (
                <Button size="sm" onClick={() => { setEditConfig(null); setShowConfig(true); }}
                  data-testid="btn-nova-config-empty">
                  <Plus className="h-4 w-4 mr-1" /> Configurar
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 bg-muted/30">
                    {["Equipamento", "Parâmetro", "Atenção", "Crítico", "Unidade", "Janela",
                      ...(isAdmin ? ["Ações"] : [])].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {configs.map(c => (
                    <tr key={c.id} className="border-b border-border/30 hover:bg-muted/20">
                      <td className="px-4 py-3 font-medium">{c.equipamento_nome}</td>
                      <td className="px-4 py-3 font-mono text-xs">{c.parametro_nome}</td>
                      <td className="px-4 py-3 text-amber-400 font-mono text-xs">{c.threshold_atencao}</td>
                      <td className="px-4 py-3 text-red-400 font-mono text-xs">{c.threshold_critico}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{c.unidade || "—"}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{c.tendencia_janela_dias}d</td>
                      {isAdmin && (
                        <td className="px-4 py-3">
                          <Button variant="ghost" size="sm" className="h-7 text-xs px-2"
                            onClick={() => { setEditConfig(c); setShowConfig(true); }}
                            data-testid={`btn-editar-config-${c.id}`}>
                            <Settings className="h-3 w-3 mr-1" /> Editar
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Drawer de tendência */}
      {showDrawer && selectedEquip && (
        <>
          <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setShowDrawer(false)} />
          <TrendDrawer
            equip={selectedEquip}
            config={getConfigForEquip(selectedEquip.id)}
            onClose={() => setShowDrawer(false)}
          />
        </>
      )}

      {/* Modal de configuração */}
      {showConfig && (
        <ConfigModal
          equip={selectedEquip}
          existing={editConfig}
          equipamentos={equipamentos}
          onClose={() => { setShowConfig(false); setEditConfig(null); }}
          onSaved={() => { setShowConfig(false); setEditConfig(null); load(); }}
        />
      )}
    </div>
  );
}
