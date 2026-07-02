import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getRelatorioOS, getRelatorioCustos, getRelatorioPareto, getRelatorioPreventivos, getRelatorioKPIs } from "../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ComposedChart, Line, Cell, Legend,
} from "recharts";
import {
  FileText, Download, Lock, Filter, TrendingUp, CheckCircle2,
  AlertTriangle, Clock, DollarSign, Wrench, BarChart2, Calendar, Loader2, Printer, Info,
} from "lucide-react";
import { HelpTooltip } from "../components/shared/HelpTooltip";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: "os",          label: "Ordens de Serviço", icon: Wrench },
  { id: "custos",      label: "Financeiro",         icon: DollarSign },
  { id: "pareto",      label: "Pareto de Falhas",   icon: BarChart2 },
  { id: "preventivos", label: "Preventivos",        icon: Calendar },
];

const STATUS_LABELS = {
  aberta: "Aberta", em_atendimento: "Em Atend.",
  aguardando_peca: "Ag. Peça", aguardando_revisao: "Ag. Revisão",
  revisada: "Revisada", fechada: "Fechada",
};

const STATUS_COLORS = {
  aberta:             "#3B82F6",   // azul
  em_atendimento:     "#F59E0B",   // âmbar
  aguardando_peca:    "#F97316",   // laranja
  aguardando_revisao: "#8B5CF6",   // roxo
  revisada:           "#10B981",   // verde
  fechada:            "#94A3B8",   // slate claro (visível em dark mode)
};

function exportCSV(filename, rows) {
  if (!rows || rows.length === 0) { toast.warning("Nenhum dado para exportar"); return; }
  const keys = Object.keys(rows[0]);
  const csv = [keys.join(";"), ...rows.map(r => keys.map(k => JSON.stringify(r[k] ?? "")).join(";"))].join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function exportPDF(title, rows, columns) {
  if (!rows || rows.length === 0) { toast.warning("Nenhum dado para exportar"); return; }
  const now = new Date().toLocaleDateString("pt-BR");
  const tableRows = rows.map(r =>
    `<tr>${columns.map(c => `<td>${r[c.key] ?? "—"}</td>`).join("")}</tr>`
  ).join("");
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
<style>
body{font-family:Arial,sans-serif;font-size:11px;color:#111;margin:20px}
h1{font-size:16px;margin-bottom:4px}
p.sub{color:#555;font-size:10px;margin:0 0 14px}
table{width:100%;border-collapse:collapse}
th{background:#1A6FE8;color:#fff;padding:6px 8px;text-align:left;font-size:10px}
td{padding:5px 8px;border-bottom:1px solid #e2e8f0;font-size:10px}
tr:nth-child(even) td{background:#f8fafc}
.footer{margin-top:16px;font-size:9px;color:#888;text-align:right}
</style></head><body>
<h1>AURIX — ${title}</h1>
<p class="sub">Gerado em ${now}</p>
<table><thead><tr>${columns.map(c => `<th>${c.label}</th>`).join("")}</tr></thead>
<tbody>${tableRows}</tbody></table>
<div class="footer">AURIX Tecnologia para Gestão Industrial · aurix.com.br</div>
</body></html>`;
  const w = window.open("", "_blank");
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => { w.print(); w.close(); }, 400);
}

function fmtBRL(v) {
  return (v ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR");
}

// ─── Upgrade gate ─────────────────────────────────────────────────────────────

function UpgradeGate() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-5 text-center">
      <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
        <Lock className="h-7 w-7 text-primary" />
      </div>
      <div className="max-w-sm space-y-1.5">
        <h2 className="font-heading text-xl font-bold">Módulo de Relatórios</h2>
        <p className="text-muted-foreground text-sm">
          Relatórios detalhados estão disponíveis a partir do plano <strong className="text-foreground">Essencial</strong>.
        </p>
      </div>
      <Button onClick={() => navigate("/billing")} className="rounded-lg shadow-lg shadow-primary/20">
        Ver planos
      </Button>
    </div>
  );
}

// ─── Tab: OS ─────────────────────────────────────────────────────────────────

function TabOS() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [di, setDi] = useState("");
  const [df, setDf] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (di) params.data_inicio = di;
      if (df) params.data_fim = df + "T23:59:59";
      const { data: res } = await getRelatorioOS(params);
      setData(res);
    } catch { toast.error("Erro ao carregar relatório de OS"); }
    finally { setLoading(false); }
  }, [di, df]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingCenter />;
  if (!data) return null;

  const statusData = Object.entries(data.por_status || {}).map(([k, v]) => ({
    name: STATUS_LABELS[k] || k, value: v, fill: STATUS_COLORS[k] || "#64748B",
  }));

  return (
    <div className="space-y-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-card border border-border/50 rounded-xl">
        <Filter className="h-4 w-4 text-muted-foreground mt-5" />
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">De</label>
          <Input type="date" value={di} onChange={e => setDi(e.target.value)} className="h-9 w-36 text-sm" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Até</label>
          <Input type="date" value={df} onChange={e => setDf(e.target.value)} className="h-9 w-36 text-sm" />
        </div>
        <Button size="sm" variant="outline" onClick={() => { setDi(""); setDf(""); }} className="h-9">
          Limpar
        </Button>
        <div className="flex gap-2 ml-auto">
          <Button
            size="sm"
            variant="outline"
            className="h-9"
            onClick={() => exportCSV("relatorio_os.csv", data.ordens)}
          >
            <Download className="h-3.5 w-3.5 mr-1.5" />
            CSV
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-9"
            onClick={() => exportPDF("Relatório de Ordens de Serviço", data.ordens, [
              { key: "numero", label: "#" },
              { key: "equipamento", label: "Equipamento" },
              { key: "tipo", label: "Tipo" },
              { key: "status", label: "Status" },
              { key: "tecnico", label: "Técnico" },
              { key: "tempo_reparo_min", label: "Reparo (min)" },
              { key: "created_at", label: "Data" },
            ])}
          >
            <Printer className="h-3.5 w-3.5 mr-1.5" />
            PDF
          </Button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SmallKpi
          label="Total de OS"
          value={data.total}
          icon={<Wrench className="h-4 w-4 text-blue-400" />}
          tooltip="Número total de ordens de serviço abertas no período selecionado."
        />
        <SmallKpi
          label="Atendimento SLA"
          value={data.sla_percent != null ? `${data.sla_percent}%` : "—"}
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          tooltip="Percentual de OS atendidas dentro do prazo de SLA por prioridade: Crítica ≤30min, Alta ≤60min, Média ≤120min, Baixa ≤480min."
        />
        <SmallKpi
          label="Tempo médio reparo"
          value={data.media_reparo_min != null ? `${data.media_reparo_min} min` : "—"}
          icon={<Clock className="h-4 w-4 text-amber-400" />}
          tooltip="Tempo médio (em minutos) entre o início e a conclusão do atendimento das OS encerradas no período."
        />
        <SmallKpi
          label="Tipos"
          value={Object.keys(data.por_tipo || {}).join(" / ")}
          icon={<BarChart2 className="h-4 w-4 text-purple-400" />}
          tooltip="Distribuição das OS por tipo: Corretiva (falha inesperada), Preventiva (manutenção planejada) e Preditiva (baseada em monitoramento)."
        />
      </div>

      {/* Status chart */}
      {statusData.length > 0 && (
        <div className="bg-card border border-border/50 rounded-xl p-5">
          <p className="text-sm font-semibold mb-4">OS por Status</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={statusData} barSize={36}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" name="OS" radius={[4, 4, 0, 0]}>
                {statusData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <OsTable rows={data.ordens} />
    </div>
  );
}

function OsTable({ rows }) {
  return (
    <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-border/40 text-sm font-semibold">
        Listagem ({rows.length})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/30">
              {["#", "Equipamento", "Tipo", "Status", "Técnico", "Reparo", "SLA", "Data"].map(h => (
                <th key={h} className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-10 text-muted-foreground text-sm">Nenhuma OS no período</td></tr>
            ) : rows.map((r, i) => (
              <tr key={i} className="border-b border-border/10 hover:bg-muted/20 transition-colors">
                <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">#{r.numero}</td>
                <td className="px-4 py-2.5 font-medium max-w-[160px] truncate">{r.equipamento}</td>
                <td className="px-4 py-2.5 capitalize text-xs">{r.tipo}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs font-medium" style={{ color: STATUS_COLORS[r.status] || "#64748B" }}>
                    {STATUS_LABELS[r.status] || r.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">{r.tecnico}</td>
                <td className="px-4 py-2.5 text-xs font-mono">{r.tempo_reparo_min != null ? `${r.tempo_reparo_min}min` : "—"}</td>
                <td className="px-4 py-2.5">
                  {r.dentro_sla == null ? "—" : r.dentro_sla
                    ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    : <AlertTriangle className="h-3.5 w-3.5 text-red-400" />}
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">{fmtDate(r.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Análise de Custos CAPEX/OPEX ─────────────────────────────────────────────

function fmtMes(yyyymm) {
  if (!yyyymm || yyyymm === "—") return yyyymm;
  const [y, m] = yyyymm.split("-");
  const meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${meses[parseInt(m, 10) - 1] || m}/${y}`;
}

function KpiCard({ label, value, accent, tooltip }) {
  return (
    <div className="bg-card border border-border/50 rounded-xl p-4 flex flex-col gap-1" data-testid={`kpi-custo-${label.toLowerCase().replace(/ /g, "-")}`}>
      <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider flex items-center">
        {label}
        {tooltip && <HelpTooltip text={tooltip} />}
      </p>
      <p className={`text-xl font-heading font-bold ${accent || ""}`}>{value}</p>
    </div>
  );
}

function AnaliseCustos({ cp }) {
  if (!cp) return null;
  const { custo_materiais_total, custo_mao_obra_total, custo_parada_total, custo_total,
          breakdown_por_tipo_os, breakdown_por_equipamento, classificacao_capex_opex, por_mes } = cp;

  const mesData = (por_mes || []).map(m => ({
    mes: fmtMes(m.mes),
    materiais: m.materiais, mao_obra: m.mao_obra, parada: m.parada,
  }));

  const opex  = classificacao_capex_opex?.opex  || 0;
  const capex = classificacao_capex_opex?.capex || 0;
  const totalCapexOpex = opex + capex;

  const tipoRows = Object.entries(breakdown_por_tipo_os || {}).map(([k, v]) => ({
    tipo: k === "corretiva" ? "Corretiva" : k === "preventiva" ? "Preventiva" : "Preditiva",
    ...v,
  }));

  return (
    <div className="space-y-5 border-t border-border/50 pt-5">
      <p className="text-sm font-semibold text-foreground flex items-center gap-2">
        <DollarSign className="h-4 w-4 text-primary" />Análise de Custos — Visão Completa
      </p>

      {/* 4 KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="custos-kpi-cards">
        <KpiCard label="Materiais / Peças" value={fmtBRL(custo_materiais_total)}
          tooltip="Custo acumulado de peças e materiais consumidos em todas as OS do período." />
        <KpiCard label="Mão de Obra" value={fmtBRL(custo_mao_obra_total)}
          tooltip="Custo de mão de obra calculado com base no valor/hora de cada técnico e o tempo de atendimento." />
        <KpiCard label="Parada de Máquina" value={fmtBRL(custo_parada_total)} accent="text-red-500"
          tooltip="Custo financeiro das horas de parada de produção. Calculado com valor/hora configurado em cada equipamento." />
        <KpiCard label="Impacto Total" value={fmtBRL(custo_total)} accent="text-primary"
          tooltip="Soma total de materiais + mão de obra + custo de parada. Representa o impacto financeiro real das falhas no período." />
      </div>

      {/* Gráfico de barras empilhadas por mês */}
      {mesData.length > 0 && (
        <div className="bg-card border border-border/50 rounded-xl p-5">
          <p className="text-sm font-semibold mb-4">Evolução Mensal de Custos</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={mesData} barSize={28}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={v => `R$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} width={52} />
              <Tooltip
                formatter={(v, name) => [fmtBRL(v), name === "materiais" ? "Materiais" : name === "mao_obra" ? "Mão de Obra" : "Parada"]}
                contentStyle={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }}
              />
              <Legend formatter={v => v === "materiais" ? "Materiais" : v === "mao_obra" ? "Mão de Obra" : "Parada"} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="materiais" stackId="a" fill="#3B82F6" radius={[0,0,0,0]} />
              <Bar dataKey="mao_obra"  stackId="a" fill="#F59E0B" radius={[0,0,0,0]} />
              <Bar dataKey="parada"    stackId="a" fill="#EF4444" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* CAPEX vs OPEX */}
        <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border/40 text-sm font-semibold">Classificação CAPEX / OPEX</div>
          <table className="w-full text-sm" data-testid="capex-opex-table">
            <thead>
              <tr className="border-b border-border/30">
                {["Classificação", "Valor", "% do Total"].map(h => (
                  <th key={h} className="text-left text-xs text-muted-foreground font-medium px-4 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { label: "OPEX", desc: "(Corretivas)", value: opex, color: "text-red-500" },
                { label: "CAPEX", desc: "(Preventivas + Preditivas)", value: capex, color: "text-blue-500" },
              ].map(row => (
                <tr key={row.label} className="border-b border-border/10 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-2.5">
                    <span className={`font-semibold ${row.color}`}>{row.label}</span>
                    <span className="text-[10px] text-muted-foreground ml-1">{row.desc}</span>
                  </td>
                  <td className="px-4 py-2.5 font-mono font-semibold">{fmtBRL(row.value)}</td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">
                    {totalCapexOpex > 0 ? `${((row.value / totalCapexOpex) * 100).toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
              <tr className="bg-muted/20">
                <td className="px-4 py-2.5 font-bold text-xs uppercase tracking-wide">Total</td>
                <td className="px-4 py-2.5 font-mono font-bold">{fmtBRL(totalCapexOpex)}</td>
                <td className="px-4 py-2.5 text-xs font-medium">100%</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Breakdown por tipo OS */}
        <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border/40 text-sm font-semibold">Custo por Tipo de OS</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30">
                {["Tipo", "Materiais", "Mão de Obra", "Parada", "Total"].map(h => (
                  <th key={h} className="text-left text-xs text-muted-foreground font-medium px-4 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tipoRows.map((r, i) => (
                <tr key={i} className="border-b border-border/10 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-2.5 font-medium capitalize">{r.tipo}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{fmtBRL(r.materiais)}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{fmtBRL(r.mao_obra)}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-red-500">{fmtBRL(r.parada)}</td>
                  <td className="px-4 py-2.5 font-mono font-semibold text-xs">{fmtBRL(r.total)}</td>
                </tr>
              ))}
              {tipoRows.length === 0 && (
                <tr><td colSpan={5} className="text-center py-6 text-muted-foreground text-xs">Nenhum dado no período</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top 5 equipamentos — breakdown completo */}
      {(breakdown_por_equipamento || []).length > 0 && (
        <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-border/40 text-sm font-semibold">Top 5 Equipamentos — Breakdown de Custos</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="top5-equipamentos-custos">
              <thead>
                <tr className="border-b border-border/30">
                  {["Equipamento", "Materiais", "Mão de Obra", "Parada", "Total"].map(h => (
                    <th key={h} className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {breakdown_por_equipamento.map((row, i) => (
                  <tr key={i} className="border-b border-border/10 hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-2.5 font-medium max-w-[160px] truncate">{row.equipamento}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{fmtBRL(row.custo_materiais)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs">{fmtBRL(row.custo_mao_obra)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-red-500">{fmtBRL(row.custo_parada)}</td>
                    <td className="px-4 py-2.5 font-mono font-bold text-xs">{fmtBRL(row.custo_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Tab: Custos ──────────────────────────────────────────────────────────────

function TabCustos({ isAdmin, isLider, userSetor }) {
  const canLoad = isAdmin || isLider;
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [di, setDi] = useState("");
  const [df, setDf] = useState("");

  const load = useCallback(async () => {
    if (!canLoad) { setLoading(false); return; }
    setLoading(true);
    try {
      const params = {};
      if (di) params.data_inicio = di;
      if (df) params.data_fim = df + "T23:59:59";
      if (isLider && userSetor) params.setor = userSetor;
      const { data: res } = await getRelatorioCustos(params);
      setData(res);
    } catch { toast.error("Erro ao carregar custos"); }
    finally { setLoading(false); }
  }, [di, df, canLoad, isLider, userSetor]);

  useEffect(() => { load(); }, [load]);

  if (!canLoad) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
        <Lock className="h-8 w-8 text-muted-foreground opacity-40" />
        <p className="text-sm text-muted-foreground">Apenas administradores e líderes têm acesso ao relatório financeiro.</p>
      </div>
    );
  }

  if (loading) return <LoadingCenter />;
  if (!data) return null;

  const tipoData = Object.entries(data.por_tipo || {}).map(([k, v]) => ({
    name: k === "mao_obra" ? "Mão de Obra" : k === "consumo" ? "Consumo" : "Substituição",
    value: v,
  }));

  const COLORS = ["#1A6FE8", "#10B981", "#F59E0B"];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3 p-4 bg-card border border-border/50 rounded-xl">
        <Filter className="h-4 w-4 text-muted-foreground mt-5" />
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">De</label>
          <Input type="date" value={di} onChange={e => setDi(e.target.value)} className="h-9 w-36 text-sm" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Até</label>
          <Input type="date" value={df} onChange={e => setDf(e.target.value)} className="h-9 w-36 text-sm" />
        </div>
        <Button size="sm" variant="outline" onClick={() => { setDi(""); setDf(""); }} className="h-9">Limpar</Button>
        <div className="flex gap-2 ml-auto">
          <Button size="sm" variant="outline" className="h-9"
            onClick={() => exportCSV("relatorio_custos.csv", data.por_equipamento)}>
            <Download className="h-3.5 w-3.5 mr-1.5" />CSV
          </Button>
          <Button size="sm" variant="outline" className="h-9"
            onClick={() => exportPDF("Relatório Financeiro — Custos por Equipamento", data.por_equipamento, [
              { key: "equipamento", label: "Equipamento" },
              { key: "total", label: "Total (R$)" },
            ])}>
            <Printer className="h-3.5 w-3.5 mr-1.5" />PDF
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-1 bg-card border border-border/50 rounded-xl p-5 flex flex-col gap-2">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Geral</p>
          <p className="text-3xl font-bold font-heading text-primary">{fmtBRL(data.total_geral)}</p>
          <p className="text-xs text-muted-foreground">{data.total_registros} registros de custo</p>
        </div>
        <div className="md:col-span-2 bg-card border border-border/50 rounded-xl p-5">
          <p className="text-sm font-semibold mb-4">Por Tipo</p>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={tipoData} barSize={40}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={v => `R$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} width={52} />
              <Tooltip formatter={v => [fmtBRL(v), "Total"]} contentStyle={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {tipoData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-border/40 text-sm font-semibold">Por Equipamento (materiais)</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/30">
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Equipamento</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Total</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">% do total</th>
            </tr>
          </thead>
          <tbody>
            {(data.por_equipamento || []).map((row, i) => (
              <tr key={i} className="border-b border-border/10 hover:bg-muted/20 transition-colors">
                <td className="px-4 py-2.5 font-medium">{row.equipamento}</td>
                <td className="px-4 py-2.5 font-mono text-sm">{fmtBRL(row.total)}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-border/40 max-w-[100px]">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, (row.total / data.total_geral) * 100)}%` }} />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {data.total_geral > 0 ? `${((row.total / data.total_geral) * 100).toFixed(1)}%` : "—"}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Análise de Custos (CAPEX/OPEX) ──────────────────────────────────── */}
      {data.custos_periodo && <AnaliseCustos cp={data.custos_periodo} />}
    </div>
  );
}

// ─── Tab: Pareto ──────────────────────────────────────────────────────────────

function TabPareto() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [di, setDi] = useState("");
  const [df, setDf] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (di) params.data_inicio = di;
      if (df) params.data_fim = df + "T23:59:59";
      const { data: res } = await getRelatorioPareto(params);
      setData(res);
    } catch { toast.error("Erro ao carregar Pareto"); }
    finally { setLoading(false); }
  }, [di, df]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingCenter />;
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3 p-4 bg-card border border-border/50 rounded-xl">
        <Filter className="h-4 w-4 text-muted-foreground mt-5" />
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">De</label>
          <Input type="date" value={di} onChange={e => setDi(e.target.value)} className="h-9 w-36 text-sm" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Até</label>
          <Input type="date" value={df} onChange={e => setDf(e.target.value)} className="h-9 w-36 text-sm" />
        </div>
        <Button size="sm" variant="outline" onClick={() => { setDi(""); setDf(""); }} className="h-9">Limpar</Button>
      </div>

      <div className="grid grid-cols-1 gap-2">
        <p className="text-xs text-muted-foreground">
          Total de OS corretivas analisadas: <strong className="text-foreground">{data.total_corretivas}</strong>
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <ParetoChart title="Por Tipo de Falha" rows={data.por_tipo_falha} exportName="pareto_tipo_falha.csv" />
        <ParetoChart title="Por Equipamento" rows={data.por_equipamento} exportName="pareto_equipamento.csv" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <ParetoChart title="Por Causa Raiz" rows={data.por_causa} exportName="pareto_causa.csv" />
      </div>
    </div>
  );
}

function ParetoChart({ title, rows, exportName }) {
  const top10 = (rows || []).slice(0, 10);
  return (
    <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border/40">
        <p className="text-sm font-semibold">{title}</p>
        <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => exportCSV(exportName, rows)}>
          <Download className="h-3 w-3 mr-1" />CSV
        </Button>
      </div>
      {top10.length === 0 ? (
        <div className="py-10 text-center text-muted-foreground text-sm">Sem dados</div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={top10} margin={{ top: 8, right: 16, bottom: 32, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#64748B" }} tickLine={false} axisLine={false}
                interval={0} angle={-30} textAnchor="end" height={48} />
              <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} allowDecimals={false} />
              <YAxis yAxisId="right" orientation="right" tickFormatter={v => `${v}%`} domain={[0, 100]}
                tick={{ fontSize: 11, fill: "#64748B" }} tickLine={false} axisLine={false} width={36} />
              <Tooltip contentStyle={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, fontSize: 12 }}
                formatter={(v, name) => name === "acumulado" ? [`${v}%`, "Acumulado"] : [v, "Ocorrências"]} />
              <Bar yAxisId="left" dataKey="count" name="count" fill="#1A6FE8" radius={[3, 3, 0, 0]} barSize={28} />
              <Line yAxisId="right" type="monotone" dataKey="acumulado" name="acumulado"
                stroke="#F59E0B" strokeWidth={2} dot={{ r: 3, fill: "#F59E0B" }} />
            </ComposedChart>
          </ResponsiveContainer>
          <table className="w-full text-xs border-t border-border/30">
            <thead>
              <tr className="border-b border-border/20">
                {["Categoria", "Ocorr.", "%", "Acum."].map(h => (
                  <th key={h} className="text-left text-muted-foreground font-medium px-4 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {top10.map((r, i) => (
                <tr key={i} className="border-b border-border/10 hover:bg-muted/20">
                  <td className="px-4 py-1.5 font-medium truncate max-w-[140px]">{r.label}</td>
                  <td className="px-4 py-1.5 tabular-nums">{r.count}</td>
                  <td className="px-4 py-1.5 tabular-nums text-muted-foreground">{r.percent}%</td>
                  <td className="px-4 py-1.5">
                    <span className={`font-semibold ${r.acumulado <= 80 ? "text-amber-400" : "text-muted-foreground"}`}>
                      {r.acumulado}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

// ─── Tab: Preventivos ────────────────────────────────────────────────────────

function TabPreventivos() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    getRelatorioPreventivos()
      .then(({ data: res }) => setData(res))
      .catch(() => toast.error("Erro ao carregar relatório de preventivos"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingCenter />;
  if (!data) return null;

  const complianceColor = data.compliance_percent >= 80 ? "#10B981" : data.compliance_percent >= 50 ? "#F59E0B" : "#EF4444";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SmallKpi
          label="Total de Planos"
          value={data.total}
          icon={<Calendar className="h-4 w-4 text-blue-400" />}
          tooltip="Número total de planos preventivos cadastrados e ativos para os equipamentos monitorados."
        />
        <SmallKpi
          label="Compliance"
          value={`${data.compliance_percent}%`}
          icon={<CheckCircle2 className="h-4 w-4" style={{ color: complianceColor }} />}
          tooltip="Percentual de planos preventivos executados dentro do prazo em relação ao total de planos no período."
        />
        <SmallKpi
          label="Planos Vencidos"
          value={data.vencidos}
          icon={<AlertTriangle className="h-4 w-4 text-red-400" />}
          highlight={data.vencidos > 0}
          tooltip="Planos com data de próxima execução ultrapassada sem registro de execução. Requerem ação imediata."
        />
        <SmallKpi
          label="Próximos 7 dias"
          value={data.proximos_7d}
          icon={<Clock className="h-4 w-4 text-amber-400" />}
          tooltip="Número de planos preventivos com execução prevista nos próximos 7 dias. Prepare a equipe."
        />
      </div>

      <div className="flex justify-end gap-2">
        <Button size="sm" variant="outline" className="h-9"
          onClick={() => exportCSV("relatorio_preventivos.csv", data.planos)}>
          <Download className="h-3.5 w-3.5 mr-1.5" />CSV
        </Button>
        <Button size="sm" variant="outline" className="h-9"
          onClick={() => exportPDF("Relatório de Manutenção Preventiva", data.planos, [
            { key: "nome", label: "Plano" },
            { key: "equipamento", label: "Equipamento" },
            { key: "frequencia_dias", label: "Freq. (dias)" },
            { key: "ultima_execucao", label: "Última Exec." },
            { key: "proxima_execucao", label: "Próxima Exec." },
            { key: "status", label: "Status" },
          ])}>
          <Printer className="h-3.5 w-3.5 mr-1.5" />PDF
        </Button>
      </div>

      <div className="bg-card border border-border/50 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-border/40 text-sm font-semibold">
          Planos Preventivos ({data.total})
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30">
                {["Plano", "Equipamento", "Frequência", "Última Exec.", "Próxima Exec.", "Status"].map(h => (
                  <th key={h} className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.planos.map((p, i) => (
                <tr key={i} className="border-b border-border/10 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-2.5 font-medium">{p.nome}</td>
                  <td className="px-4 py-2.5 text-muted-foreground text-xs">{p.equipamento}</td>
                  <td className="px-4 py-2.5 text-xs">{p.frequencia_dias}d</td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground">{fmtDate(p.ultima_execucao)}</td>
                  <td className="px-4 py-2.5 text-xs">{fmtDate(p.proxima_execucao)}</td>
                  <td className="px-4 py-2.5">
                    {p.status === "vencido"
                      ? <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-red-500/10 text-red-400 border border-red-500/20">
                          <AlertTriangle className="h-2.5 w-2.5" />Vencido {p.dias_atraso}d
                        </span>
                      : p.status === "proximo"
                      ? <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <Clock className="h-2.5 w-2.5" />Próximo
                        </span>
                      : <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="h-2.5 w-2.5" />OK
                        </span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Shared ───────────────────────────────────────────────────────────────────

function LoadingCenter() {
  return (
    <div className="flex justify-center py-16">
      <Loader2 className="h-7 w-7 animate-spin text-primary" />
    </div>
  );
}

function SmallKpi({ label, value, icon, highlight, tooltip }) {
  return (
    <div className={`relative border border-border/50 rounded-xl p-4 bg-card ${highlight ? "border-red-500/30" : ""}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">{icon}</div>
        {tooltip && (
          <div className="relative group/tip">
            <Info className="h-3.5 w-3.5 text-muted-foreground/40 cursor-help group-hover/tip:text-muted-foreground transition-colors" />
            {/* Tooltip bubble */}
            <div className="absolute right-0 bottom-6 z-50 w-52 bg-popover border border-border text-xs text-foreground/80 rounded-lg p-2.5 shadow-xl
                            opacity-0 pointer-events-none group-hover/tip:opacity-100 transition-opacity duration-150 leading-relaxed">
              {tooltip}
              <div className="absolute -bottom-1 right-1.5 w-2 h-2 bg-popover border-r border-b border-border rotate-45" />
            </div>
          </div>
        )}
      </div>
      <p className="text-xl font-bold font-heading tabular-nums">{value}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function RelatoriosPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("os");
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    if (user?.features && user.features.relatorios === false) {
      setLocked(true);
    }
  }, [user]);

  if (locked) return <UpgradeGate />;

  const isAdmin = user?.role === "admin";
  const isLider = user?.role === "lider";
  const canSeeCustos = isAdmin || isLider;

  return (
    <div className="space-y-6" data-testid="relatorios-page">
      {/* Header */}
      <div className="flex items-center gap-3">
        <FileText className="h-6 w-6 text-primary" />
        <div>
          <h1 className="font-heading text-2xl font-bold">Relatórios</h1>
          <p className="text-muted-foreground text-sm mt-0.5">Análise operacional e gerencial</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 bg-card border border-border/50 rounded-xl p-1.5 w-fit">
        {TABS.map(tab => {
          if (tab.id === "custos" && !canSeeCustos) return null;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? "bg-primary text-primary-foreground shadow-sm shadow-primary/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === "os"          && <TabOS />}
      {activeTab === "custos"      && <TabCustos isAdmin={isAdmin} isLider={isLider} userSetor={user?.setor} />}
      {activeTab === "pareto"      && <TabPareto />}
      {activeTab === "preventivos" && <TabPreventivos />}
    </div>
  );
}
