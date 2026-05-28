import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { getSetoresTecnico } from "../lib/api";
import { toast } from "sonner";
import { Wrench, ChevronRight, CheckCircle, Eye, EyeOff, Loader2 } from "lucide-react";

// ─── Stepper indicator ────────────────────────────────────────────────────────

function Stepper({ step }) {
  const steps = ["Setor", "Identificação", "Confirmação"];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 32 }}>
      {steps.map((label, i) => {
        const idx = i + 1;
        const done = step > idx;
        const active = step === idx;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: i < steps.length - 1 ? 1 : "none" }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: done ? "#10B981" : active ? "#2563EB" : "rgba(255,255,255,0.08)",
                border: done ? "2px solid #10B981" : active ? "2px solid #2563EB" : "2px solid rgba(255,255,255,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 700,
                color: (done || active) ? "#fff" : "rgba(255,255,255,0.3)",
                transition: "all 0.2s",
              }}>
                {done ? <CheckCircle size={16} /> : idx}
              </div>
              <span style={{
                fontSize: 10, fontWeight: 600,
                color: active ? "#fff" : done ? "#10B981" : "rgba(255,255,255,0.3)",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}>
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div style={{
                flex: 1, height: 1,
                background: step > idx ? "#10B981" : "rgba(255,255,255,0.1)",
                margin: "0 8px", marginBottom: 18,
                transition: "background 0.3s",
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function TecnicoLoginPage() {
  const { loginTecnico } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // tenant_id: priority = URL param → localStorage → null (manual input)
  const [tenantId, setTenantId] = useState(() => {
    const fromUrl = searchParams.get("t") || searchParams.get("tenant");
    if (fromUrl) return fromUrl;
    try {
      const stored = JSON.parse(localStorage.getItem("aurix_user") || "{}");
      return stored.organization_id || null;
    } catch {
      return null;
    }
  });
  const [tenantInput, setTenantInput] = useState("");

  const [step, setStep] = useState(1);
  const [setores, setSetores] = useState([]);
  const [loadingSetores, setLoadingSetores] = useState(false);

  const [selectedSetor, setSelectedSetor] = useState(null); // { id, nome }
  const [matricula, setMatricula] = useState("");
  const [senha, setSenha] = useState("");
  const [showSenha, setShowSenha] = useState(false);
  const [loading, setLoading] = useState(false);
  const [confirmedUser, setConfirmedUser] = useState(null); // { nome_funcionario, sector_name, employee_id }

  // Carrega setores ao ter o tenant_id
  useEffect(() => {
    if (!tenantId) return;
    setLoadingSetores(true);
    getSetoresTecnico(tenantId)
      .then(({ data }) => setSetores(data || []))
      .catch(() => {
        toast.error("Não foi possível carregar os setores. Verifique o código da empresa.");
        setSetores([]);
      })
      .finally(() => setLoadingSetores(false));
  }, [tenantId]);

  // ── Etapa 1: selecionar tenant e setor ──

  const handleTenantSubmit = (e) => {
    e.preventDefault();
    if (!tenantInput.trim()) return;
    setTenantId(tenantInput.trim());
  };

  const handleSetorSelect = (setor) => {
    setSelectedSetor(setor);
    setStep(2);
  };

  // ── Etapa 2: matrícula + senha ──

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!matricula.trim()) { toast.error("Informe sua matrícula funcional"); return; }
    if (!senha.trim())     { toast.error("Informe a senha do setor");         return; }
    setLoading(true);
    const result = await loginTecnico(senha, selectedSetor.id, matricula.trim());
    setLoading(false);
    if (!result.success) {
      toast.error(result.error || "Senha inválida ou matrícula incorreta");
      return;
    }
    setConfirmedUser(result.user);
    setStep(3);
  };

  // ── Etapa 3: confirmação + redirect ──

  useEffect(() => {
    if (step !== 3) return;
    const t = setTimeout(() => {
      navigate("/dashboard/operador", { replace: true });
    }, 2000);
    return () => clearTimeout(t);
  }, [step, navigate]);

  // ── Layout wrapper ──

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0A0A0A",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 16,
      // Subtle industrial grid pattern
      backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.025) 1px, transparent 0)",
      backgroundSize: "32px 32px",
    }}>
      <div style={{
        width: "100%", maxWidth: 440,
        background: "#171717",
        border: "1px solid #262626",
        borderRadius: 4,
        padding: "36px 32px",
        boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 4,
            background: "rgba(37,99,235,0.15)", border: "1px solid rgba(37,99,235,0.3)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Wrench size={20} style={{ color: "#3B82F6" }} />
          </div>
          <div>
            <p style={{ fontSize: 15, fontWeight: 800, color: "#F8FAFC", margin: 0, fontFamily: "Outfit, sans-serif" }}>
              AURIX
            </p>
            <p style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", margin: 0 }}>Login de Técnico</p>
          </div>
        </div>

        <Stepper step={step} />

        {/* ── Etapa 1 ── */}
        {step === 1 && (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "#F8FAFC", marginBottom: 4, fontFamily: "Outfit, sans-serif" }}>
              Selecione o Setor
            </h2>
            <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 24 }}>
              Escolha o setor em que você vai trabalhar neste turno.
            </p>

            {/* Se não tem tenant_id, pede o código da empresa */}
            {!tenantId && (
              <form onSubmit={handleTenantSubmit} style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Código da empresa (ID)</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="text"
                    placeholder="Cole o UUID da organização"
                    value={tenantInput}
                    onChange={e => setTenantInput(e.target.value)}
                    style={inputStyle}
                  />
                  <button type="submit" style={btnSmallStyle}>OK</button>
                </div>
                <p style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", marginTop: 6 }}>
                  Peça ao administrador ou escaneie o QR code do seu setor.
                </p>
              </form>
            )}

            {loadingSetores && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "rgba(255,255,255,0.4)", fontSize: 13, padding: "16px 0" }}>
                <Loader2 size={16} className="animate-spin" style={{ animation: "spin 1s linear infinite" }} />
                Carregando setores...
              </div>
            )}

            {!loadingSetores && tenantId && setores.length === 0 && (
              <p style={{ fontSize: 13, color: "rgba(255,255,255,0.35)", textAlign: "center", padding: "16px 0" }}>
                Nenhum setor disponível nesta empresa.
              </p>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {setores.map(s => (
                <button
                  key={s.id}
                  onClick={() => handleSetorSelect(s)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    padding: "14px 16px", borderRadius: 4,
                    background: "rgba(255,255,255,0.04)", border: "1px solid #262626",
                    color: "#F8FAFC", cursor: "pointer", textAlign: "left",
                    fontSize: 14, fontWeight: 600,
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = "rgba(37,99,235,0.1)"; e.currentTarget.style.borderColor = "rgba(37,99,235,0.4)"; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.borderColor = "#262626"; }}
                >
                  <span>{s.nome}</span>
                  <ChevronRight size={16} style={{ color: "rgba(255,255,255,0.3)" }} />
                </button>
              ))}
            </div>

            <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px solid #262626" }}>
              <a
                href="/login"
                style={{ fontSize: 12, color: "rgba(255,255,255,0.3)", textDecoration: "none" }}
              >
                ← Login com e-mail e senha
              </a>
            </div>
          </div>
        )}

        {/* ── Etapa 2 ── */}
        {step === 2 && (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "#F8FAFC", marginBottom: 4, fontFamily: "Outfit, sans-serif" }}>
              Identificação
            </h2>
            <p style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 24 }}>
              Setor selecionado:{" "}
              <strong style={{ color: "#3B82F6" }}>{selectedSetor?.nome}</strong>
            </p>

            <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label style={labelStyle}>Matrícula funcional</label>
                <input
                  type="text"
                  placeholder="Ex: 45821"
                  value={matricula}
                  onChange={e => setMatricula(e.target.value)}
                  style={inputStyle}
                  autoFocus
                />
              </div>

              <div>
                <label style={labelStyle}>Senha do setor</label>
                <div style={{ position: "relative" }}>
                  <input
                    type={showSenha ? "text" : "password"}
                    placeholder="Senha compartilhada do setor"
                    value={senha}
                    onChange={e => setSenha(e.target.value)}
                    style={{ ...inputStyle, paddingRight: 40 }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowSenha(v => !v)}
                    style={{
                      position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", cursor: "pointer",
                      color: "rgba(255,255,255,0.35)", padding: 0,
                    }}
                  >
                    {showSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                style={loading ? { ...btnPrimaryStyle, opacity: 0.6, cursor: "not-allowed" } : btnPrimaryStyle}
              >
                {loading ? (
                  <span style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
                    <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
                    Verificando...
                  </span>
                ) : "Entrar"}
              </button>
            </form>

            <button
              onClick={() => { setStep(1); setSelectedSetor(null); }}
              style={{
                marginTop: 16, background: "none", border: "none",
                color: "rgba(255,255,255,0.3)", fontSize: 12, cursor: "pointer",
              }}
            >
              ← Trocar setor
            </button>
          </div>
        )}

        {/* ── Etapa 3 ── */}
        {step === 3 && (
          <div style={{ textAlign: "center", padding: "8px 0" }}>
            <div style={{
              width: 56, height: 56, borderRadius: "50%",
              background: "rgba(16,185,129,0.15)", border: "2px solid #10B981",
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 20px",
            }}>
              <CheckCircle size={28} style={{ color: "#10B981" }} />
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: "#F8FAFC", marginBottom: 8, fontFamily: "Outfit, sans-serif" }}>
              Turno iniciado!
            </h2>
            <p style={{ fontSize: 14, color: "rgba(255,255,255,0.5)", marginBottom: 6 }}>
              Bem-vindo, <strong style={{ color: "#F8FAFC" }}>{confirmedUser?.nome_funcionario || matricula}</strong>
            </p>
            <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)" }}>
              Setor: {confirmedUser?.sector_name} · Mat. {confirmedUser?.employee_id}
            </p>
            <p style={{ fontSize: 11, color: "rgba(255,255,255,0.2)", marginTop: 20 }}>
              Redirecionando para o dashboard...
            </p>
          </div>
        )}
      </div>

      {/* Spin keyframe */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ─── Shared styles ────────────────────────────────────────────────────────────

const labelStyle = {
  display: "block", fontSize: 11, fontWeight: 600,
  color: "rgba(255,255,255,0.5)", marginBottom: 6,
  textTransform: "uppercase", letterSpacing: "0.04em",
};

const inputStyle = {
  width: "100%", height: 42, borderRadius: 4,
  background: "rgba(255,255,255,0.05)", border: "1px solid #262626",
  color: "#F8FAFC", padding: "0 12px", fontSize: 14, outline: "none",
  boxSizing: "border-box",
  fontFamily: "Inter, sans-serif",
};

const btnPrimaryStyle = {
  width: "100%", height: 44, borderRadius: 4, border: "none",
  background: "#2563EB", color: "#fff", fontWeight: 700, fontSize: 14,
  cursor: "pointer", fontFamily: "Inter, sans-serif",
};

const btnSmallStyle = {
  height: 42, padding: "0 16px", borderRadius: 4, border: "none",
  background: "#2563EB", color: "#fff", fontWeight: 700, fontSize: 13,
  cursor: "pointer", whiteSpace: "nowrap",
};
