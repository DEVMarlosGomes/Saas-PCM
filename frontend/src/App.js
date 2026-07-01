import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { RealtimeProvider } from "./contexts/RealtimeContext";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { getEquipamentos } from "./lib/api";
import { toast } from "sonner";
import { Wrench, LogIn } from "lucide-react";

// Pages
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import TecnicoLoginPage from "./pages/TecnicoLoginPage";
import DashboardPage from "./pages/DashboardPage";
import DashboardOperadorPage from "./pages/DashboardOperadorPage";
import DashboardLiderPage from "./pages/DashboardLiderPage";
import EquipamentosPage from "./pages/EquipamentosPage";
import OrdensServicoPage from "./pages/OrdensServicoPage";
import PlanosPreventivosPage from "./pages/PlanosPreventivosPage";
import UsuariosPage from "./pages/UsuariosPage";
import ColaboradoresPage from "./pages/ColaboradoresPage";
import AuditoriaPage from "./pages/AuditoriaPage";
import BillingPage from "./pages/BillingPage";
import SettingsPage from "./pages/SettingsPage";
import PreditivoPage from "./pages/PreditivoPage";
import RelatoriosPage from "./pages/RelatoriosPage";
import KanbanPage from "./pages/KanbanPage";
import SuperuserPage from "./pages/SuperuserPage";
import EstoquePage from "./pages/EstoquePage";
import FornecedoresPage from "./pages/FornecedoresPage";
import EvidenciasPage from "./pages/EvidenciasPage";

// Layout
import AppLayout from "./components/AppLayout";

function TechnicianSessionGate({ children }) {
  const { needsTechnicianSession, completeTechnicianSession } = useAuth();
  const [sector, setSector] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sectors, setSectors] = useState([]);

  useEffect(() => {
    if (!needsTechnicianSession) return;
    getEquipamentos()
      .then(({ data }) => {
        const unique = [...new Set((data || []).filter(e => e.setor).map(e => e.setor))].sort();
        setSectors(unique);
      })
      .catch(() => {});
  }, [needsTechnicianSession]);

  if (!needsTechnicianSession) return children;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!sector || !employeeId.trim()) {
      toast.error("Selecione o setor e informe sua matrícula");
      return;
    }
    setSubmitting(true);
    const result = await completeTechnicianSession(sector, employeeId.trim());
    setSubmitting(false);
    if (!result.success) toast.error(result.error || "Erro ao iniciar sessão");
  };

  return (
    <>
      {children}
      <div
        style={{
          position: "fixed", inset: 0, zIndex: 9999,
          background: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)",
          display: "flex", alignItems: "center", justifyContent: "center", padding: 16,
        }}
      >
        <div
          style={{
            background: "var(--background, #0a0f1e)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 16, padding: "32px 28px",
            width: "100%", maxWidth: 400,
            boxShadow: "0 24px 64px rgba(0,0,0,0.6)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 12,
              background: "rgba(26,111,232,0.15)", border: "1px solid rgba(26,111,232,0.3)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Wrench style={{ width: 22, height: 22, color: "#2E90FA" }} />
            </div>
            <div>
              <p style={{ fontSize: 16, fontWeight: 700, color: "rgba(255,255,255,0.9)", margin: 0 }}>
                Início de Turno
              </p>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", margin: 0 }}>
                Selecione seu setor e informe sua matrícula
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.6)", display: "block", marginBottom: 6 }}>
                Setor
              </label>
              {sectors.length > 0 ? (
                <select
                  value={sector}
                  onChange={e => setSector(e.target.value)}
                  style={{
                    width: "100%", height: 42, borderRadius: 8,
                    background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
                    color: sector ? "rgba(255,255,255,0.9)" : "rgba(255,255,255,0.35)",
                    padding: "0 12px", fontSize: 14, outline: "none",
                  }}
                >
                  <option value="" style={{ background: "#0a0f1e" }}>Selecione o setor...</option>
                  {sectors.map(s => (
                    <option key={s} value={s} style={{ background: "#0a0f1e" }}>{s}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="Digite o nome do setor"
                  value={sector}
                  onChange={e => setSector(e.target.value)}
                  style={{
                    width: "100%", height: 42, borderRadius: 8,
                    background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
                    color: "rgba(255,255,255,0.9)", padding: "0 12px", fontSize: 14, outline: "none",
                    boxSizing: "border-box",
                  }}
                />
              )}
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.6)", display: "block", marginBottom: 6 }}>
                Matrícula
              </label>
              <input
                type="text"
                placeholder="Ex: 12345"
                value={employeeId}
                onChange={e => setEmployeeId(e.target.value)}
                style={{
                  width: "100%", height: 42, borderRadius: 8,
                  background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
                  color: "rgba(255,255,255,0.9)", padding: "0 12px", fontSize: 14, outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              style={{
                height: 44, borderRadius: 10, border: "none",
                background: submitting ? "rgba(26,111,232,0.5)" : "#1A6FE8",
                color: "#fff", fontWeight: 700, fontSize: 14,
                cursor: submitting ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                marginTop: 4,
              }}
            >
              <LogIn style={{ width: 16, height: 16 }} />
              {submitting ? "Iniciando..." : "Iniciar Turno"}
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background gradient-mesh">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
          </div>
          <span className="text-sm text-muted-foreground font-medium">Carregando AURIX...</span>
        </div>
      </div>
    );
  }

  if (!user || user === false) {
    return <Navigate to="/login" replace />;
  }

  return <TechnicianSessionGate>{children}</TechnicianSessionGate>;
};

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="w-10 h-10 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
      </div>
    );
  }

  if (user && user !== false) {
    if (user.role === "superusuario") return <Navigate to="/superuser" replace />;
    if (["operador", "tecnico", "lider_producao", "supervisor_producao"].includes(user.role))
      return <Navigate to="/dashboard/operador" replace />;
    if (["lider", "lider_manutencao_eletrica", "lider_manutencao_mecanica",
         "supervisor_manutencao", "analista_manutencao", "engenheiro_manutencao"].includes(user.role))
      return <Navigate to="/dashboard/lider" replace />;
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

function IndexRedirect() {
  const { user } = useAuth();
  if (user?.role === "superusuario") return <Navigate to="/superuser" replace />;
  if (["operador", "tecnico", "lider_producao", "supervisor_producao"].includes(user?.role))
    return <Navigate to="/dashboard/operador" replace />;
  if (["lider", "lider_manutencao_eletrica", "lider_manutencao_mecanica",
       "supervisor_manutencao", "analista_manutencao", "engenheiro_manutencao"].includes(user?.role))
    return <Navigate to="/dashboard/lider" replace />;
  return <Navigate to="/dashboard" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
      <Route path="/login/tecnico" element={<TecnicoLoginPage />} />

      <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<IndexRedirect />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="dashboard/operador" element={<DashboardOperadorPage />} />
        <Route path="dashboard/lider" element={<DashboardLiderPage />} />
        <Route path="equipamentos" element={<EquipamentosPage />} />
        <Route path="ordens-servico" element={<OrdensServicoPage />} />
        <Route path="planos-preventivos" element={<PlanosPreventivosPage />} />
        <Route path="usuarios" element={<UsuariosPage />} />
        <Route path="colaboradores" element={<ColaboradoresPage />} />
        <Route path="estoque" element={<EstoquePage />} />
        <Route path="fornecedores" element={<FornecedoresPage />} />
        <Route path="evidencias" element={<EvidenciasPage />} />
        <Route path="auditoria" element={<AuditoriaPage />} />
        <Route path="preditivo" element={<PreditivoPage />} />
        <Route path="relatorios" element={<RelatoriosPage />} />
        <Route path="kanban" element={<KanbanPage />} />
        <Route path="billing" element={<BillingPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="superuser" element={<SuperuserPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <RealtimeProvider>
        <TooltipProvider delayDuration={300}>
          <BrowserRouter>
            <AppRoutes />
            <Toaster position="top-right" richColors />
          </BrowserRouter>
        </TooltipProvider>
        </RealtimeProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
