import { useState, useEffect, useCallback } from "react";
import {
  getSuperuserDashboard,
  getSuperuserEmpresas,
  createSuperuserEmpresa,
  updateSuperuserEmpresa,
} from "../lib/api";
import { toast } from "sonner";
import {
  Shield, Building2, Loader2, RefreshCw, Plus, X, AlertTriangle,
  Activity, Wrench, CheckCircle, XCircle, TrendingUp, Users, Edit,
} from "lucide-react";
import { Button } from "../components/ui/button";

const PLANOS = [
  { value: "demo",        label: "Demo",        color: "#64748B" },
  { value: "essencial",   label: "Essencial",   color: "#3B82F6" },
  { value: "profissional",label: "Profissional", color: "#8B5CF6" },
  { value: "avancado",    label: "Avançado",    color: "#10B981" },
  { value: "enterprise",  label: "Enterprise",  color: "#F59E0B" },
];

function planoColor(plano) {
  return PLANOS.find(p => p.value === plano)?.color || "#64748B";
}

function planoLabel(plano) {
  return PLANOS.find(p => p.value === plano)?.label || plano;
}

function UsageBar({ used, max, color }) {
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  const barColor = pct >= 90 ? "#EF4444" : pct >= 70 ? "#F97316" : color || "#3B82F6";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.08)" }}>
        <div style={{ height: "100%", borderRadius: 2, width: `${pct}%`, background: barColor, transition: "width 0.5s" }} />
      </div>
      <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", fontFamily: "monospace", minWidth: 44, textAlign: "right" }}>
        {used}/{max}
      </span>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, color }) {
  return (
    <div style={{
      background: "var(--aurix-bg-card, #0D1626)",
      border: "1px solid rgba(255,255,255,0.07)",
      borderRadius: 12, padding: "18px 20px",
      display: "flex", alignItems: "center", gap: 14,
    }}>
      <div style={{
        width: 42, height: 42, borderRadius: 10, flexShrink: 0,
        background: color + "22", display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Icon style={{ width: 20, height: 20, color }} />
      </div>
      <div>
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 }}>{label}</p>
        <p style={{ fontSize: 26, fontWeight: 800, color: "rgba(255,255,255,0.95)", margin: 0, lineHeight: 1.2 }}>{value}</p>
      </div>
    </div>
  );
}

// ─── Create Empresa Modal ─────────────────────────────────

function CreateEmpresaModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    nome: "", cnpj: "", plano: "demo",
    admin_email: "", admin_password: "", admin_nome: "",
  });
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.nome || !form.admin_email || !form.admin_password || !form.admin_nome) {
      toast.error("Preencha todos os campos obrigatórios");
      return;
    }
    setLoading(true);
    try {
      await createSuperuserEmpresa(form);
      toast.success("Empresa criada com sucesso!");
      onCreated();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao criar empresa");
    } finally {
      setLoading(false);
    }
  };

  const labelStyle = { fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.55)", display: "block", marginBottom: 5 };
  const inputStyle = {
    width: "100%", height: 38, borderRadius: 7, boxSizing: "border-box",
    background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
    color: "rgba(255,255,255,0.9)", padding: "0 10px", fontSize: 13, outline: "none",
  };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(0,0,0,0.65)", backdropFilter: "blur(3px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
      onClick={onClose}
    >
      <div style={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 14, padding: "28px 24px", width: "100%", maxWidth: 500, boxShadow: "0 24px 60px rgba(0,0,0,0.5)" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22 }}>
          <p style={{ fontSize: 16, fontWeight: 700, color: "rgba(255,255,255,0.9)", margin: 0 }}>Nova Empresa</p>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.4)", lineHeight: 0 }}><X size={16} /></button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={labelStyle}>Nome da empresa *</label>
              <input style={inputStyle} placeholder="Empresa Ltda." value={form.nome} onChange={e => set("nome", e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>CNPJ</label>
              <input style={inputStyle} placeholder="00.000.000/0001-00" value={form.cnpj} onChange={e => set("cnpj", e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Plano</label>
              <select style={{ ...inputStyle, background: "#0D1626" }} value={form.plano} onChange={e => set("plano", e.target.value)}>
                {PLANOS.map(p => <option key={p.value} value={p.value} style={{ background: "#0D1626" }}>{p.label}</option>)}
              </select>
            </div>
          </div>

          <div style={{ height: 1, background: "rgba(255,255,255,0.07)", margin: "4px 0" }} />
          <p style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.35)", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 }}>Administrador inicial</p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={labelStyle}>Nome do admin *</label>
              <input style={inputStyle} placeholder="João Silva" value={form.admin_nome} onChange={e => set("admin_nome", e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Email do admin *</label>
              <input style={inputStyle} type="email" placeholder="admin@empresa.com" value={form.admin_email} onChange={e => set("admin_email", e.target.value)} />
            </div>
            <div>
              <label style={labelStyle}>Senha do admin *</label>
              <input style={inputStyle} type="password" placeholder="••••••••" value={form.admin_password} onChange={e => set("admin_password", e.target.value)} />
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 4 }}>
            <button type="button" onClick={onClose} style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.12)", background: "transparent", color: "rgba(255,255,255,0.5)", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>
              Cancelar
            </button>
            <button type="submit" disabled={loading} style={{ padding: "8px 18px", borderRadius: 8, border: "none", background: loading ? "rgba(26,111,232,0.4)" : "#1A6FE8", color: "#fff", fontSize: 13, cursor: loading ? "not-allowed" : "pointer", fontWeight: 700 }}>
              {loading ? "Criando..." : "Criar Empresa"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Edit Empresa Modal ────────────────────────────────────

function EditEmpresaModal({ empresa, onClose, onUpdated }) {
  const [plano, setPlano] = useState(empresa.plano);
  const [ativo, setAtivo] = useState(empresa.ativo);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateSuperuserEmpresa(empresa.id, { plano, ativo });
      toast.success("Empresa atualizada!");
      onUpdated();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao atualizar empresa");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 100, background: "rgba(0,0,0,0.65)", backdropFilter: "blur(3px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
      onClick={onClose}
    >
      <div style={{ background: "#0D1626", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 14, padding: "28px 24px", width: "100%", maxWidth: 400, boxShadow: "0 24px 60px rgba(0,0,0,0.5)" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <p style={{ fontSize: 15, fontWeight: 700, color: "rgba(255,255,255,0.9)", margin: 0 }}>Editar Empresa</p>
            <p style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", margin: "3px 0 0" }}>{empresa.nome}</p>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "rgba(255,255,255,0.4)", lineHeight: 0 }}><X size={16} /></button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.55)", display: "block", marginBottom: 5 }}>Plano</label>
            <select
              value={plano}
              onChange={e => setPlano(e.target.value)}
              style={{ width: "100%", height: 38, borderRadius: 7, background: "#0D1626", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.9)", padding: "0 10px", fontSize: 13, outline: "none" }}
            >
              {PLANOS.map(p => <option key={p.value} value={p.value} style={{ background: "#0D1626" }}>{p.label}</option>)}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: "rgba(255,255,255,0.55)", display: "block", marginBottom: 8 }}>Status</label>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={() => setAtivo(true)}
                style={{
                  flex: 1, padding: "8px 0", borderRadius: 8, border: "1px solid",
                  borderColor: ativo ? "#10B981" : "rgba(255,255,255,0.1)",
                  background: ativo ? "rgba(16,185,129,0.12)" : "transparent",
                  color: ativo ? "#10B981" : "rgba(255,255,255,0.4)",
                  fontSize: 12, fontWeight: 700, cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                }}
              >
                <CheckCircle size={13} /> Ativa
              </button>
              <button
                type="button"
                onClick={() => setAtivo(false)}
                style={{
                  flex: 1, padding: "8px 0", borderRadius: 8, border: "1px solid",
                  borderColor: !ativo ? "#EF4444" : "rgba(255,255,255,0.1)",
                  background: !ativo ? "rgba(239,68,68,0.12)" : "transparent",
                  color: !ativo ? "#EF4444" : "rgba(255,255,255,0.4)",
                  fontSize: 12, fontWeight: 700, cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 5,
                }}
              >
                <XCircle size={13} /> Suspensa
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 4 }}>
            <button type="button" onClick={onClose} style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.12)", background: "transparent", color: "rgba(255,255,255,0.5)", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>
              Cancelar
            </button>
            <button type="submit" disabled={loading} style={{ padding: "8px 18px", borderRadius: 8, border: "none", background: loading ? "rgba(26,111,232,0.4)" : "#1A6FE8", color: "#fff", fontSize: 13, cursor: loading ? "not-allowed" : "pointer", fontWeight: 700 }}>
              {loading ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────

export default function SuperuserPage() {
  const [dashboard, setDashboard] = useState(null);
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createModal, setCreateModal] = useState(false);
  const [editModal, setEditModal] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dashRes, empRes] = await Promise.all([
        getSuperuserDashboard(),
        getSuperuserEmpresas(),
      ]);
      setDashboard(dashRes.data);
      setEmpresas(empRes.data.empresas || []);
    } catch (err) {
      toast.error("Erro ao carregar dados da plataforma");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-80">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-6" data-testid="superuser-page">
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Shield style={{ width: 22, height: 22, color: "#EF4444" }} />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold">Portal Plataforma</h1>
              <p className="text-muted-foreground text-sm">Gestão de empresas e saúde da plataforma AURIX</p>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="outline" size="sm" onClick={load} className="h-9 gap-2">
              <RefreshCw className="h-3.5 w-3.5" />
              Atualizar
            </Button>
            <Button size="sm" onClick={() => setCreateModal(true)} className="h-9 gap-2">
              <Plus className="h-3.5 w-3.5" />
              Nova Empresa
            </Button>
          </div>
        </div>

        {/* Platform KPIs */}
        {dashboard && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            <KpiCard icon={Building2} label="Empresas Ativas" value={dashboard.total_empresas} color="#3B82F6" />
            <KpiCard icon={Wrench} label="OS Abertas" value={dashboard.total_os_abertas} color="#F59E0B" />
            <KpiCard icon={Activity} label="OS este mês" value={dashboard.total_os_mes} color="#8B5CF6" />
            <KpiCard icon={AlertTriangle} label="Alertas Críticos" value={dashboard.alertas_criticos} color={dashboard.alertas_criticos > 0 ? "#EF4444" : "#10B981"} />
            <KpiCard icon={TrendingUp} label="Disponib. Média" value={`${dashboard.disponibilidade_media?.toFixed(1) ?? "—"}%`} color="#10B981" />
          </div>
        )}

        {/* Empresa list */}
        <div style={{ background: "var(--aurix-bg-card, #0D1626)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 14, overflow: "hidden" }}>
          {/* Table header */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 110px 100px 180px 80px", gap: 0, padding: "10px 20px", borderBottom: "1px solid rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.03)" }}>
            {["Empresa", "Plano", "Status", "Uso (equip / users / OS)", ""].map((h, i) => (
              <span key={i} style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,255,255,0.35)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{h}</span>
            ))}
          </div>

          {empresas.length === 0 ? (
            <div style={{ textAlign: "center", padding: "40px 20px", color: "rgba(255,255,255,0.3)", fontSize: 13 }}>
              Nenhuma empresa cadastrada
            </div>
          ) : empresas.map((emp, i) => {
            const planColor = planoColor(emp.plano);
            const isActive = emp.ativo !== false;
            return (
              <div
                key={emp.id}
                style={{
                  display: "grid", gridTemplateColumns: "1fr 110px 100px 180px 80px",
                  gap: 0, padding: "14px 20px", alignItems: "center",
                  borderBottom: i < empresas.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                  opacity: isActive ? 1 : 0.55,
                }}
              >
                {/* Nome + CNPJ */}
                <div>
                  <p style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.9)", margin: 0 }}>{emp.nome}</p>
                  <p style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", margin: "2px 0 0", fontFamily: "monospace" }}>
                    {emp.cnpj || "CNPJ não informado"} · criada {emp.created_at ? new Date(emp.created_at).toLocaleDateString("pt-BR") : "—"}
                  </p>
                </div>

                {/* Plano badge */}
                <div>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 5,
                    background: planColor + "22", color: planColor,
                    border: `1px solid ${planColor}33`, textTransform: "uppercase", letterSpacing: "0.04em",
                  }}>
                    {planoLabel(emp.plano)}
                  </span>
                </div>

                {/* Status */}
                <div>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 5,
                    background: isActive ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)",
                    color: isActive ? "#10B981" : "#EF4444",
                    border: `1px solid ${isActive ? "rgba(16,185,129,0.25)" : "rgba(239,68,68,0.25)"}`,
                    display: "flex", alignItems: "center", gap: 4, width: "fit-content",
                  }}>
                    {isActive ? <CheckCircle size={9} /> : <XCircle size={9} />}
                    {isActive ? "Ativa" : "Suspensa"}
                  </span>
                </div>

                {/* Usage bars */}
                <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingRight: 8 }}>
                  <UsageBar used={emp.usage?.equipamentos ?? 0} max={emp.limits?.max_equipamentos ?? 0} color={planColor} />
                  <UsageBar used={emp.usage?.users ?? 0} max={emp.limits?.max_users ?? 0} color={planColor} />
                  <UsageBar used={emp.usage?.os_mes ?? 0} max={emp.limits?.max_os_mes ?? 0} color={planColor} />
                </div>

                {/* Actions */}
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setEditModal(emp)}
                    style={{
                      display: "flex", alignItems: "center", gap: 4,
                      padding: "5px 10px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.1)",
                      background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.55)",
                      fontSize: 11, cursor: "pointer", fontWeight: 600,
                    }}
                    title="Editar empresa"
                  >
                    <Edit size={11} />
                    Editar
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer count */}
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", textAlign: "right" }}>
          {empresas.length} empresa{empresas.length !== 1 ? "s" : ""} · plataforma AURIX v2
        </p>
      </div>

      {/* Modals */}
      {createModal && (
        <CreateEmpresaModal onClose={() => setCreateModal(false)} onCreated={load} />
      )}
      {editModal && (
        <EditEmpresaModal empresa={editModal} onClose={() => setEditModal(null)} onUpdated={load} />
      )}
    </>
  );
}
