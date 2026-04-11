import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getOrganization, updateOrganization, changePassword } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import {
  Building2,
  Save,
  Shield,
  Lock,
  Users,
  Settings,
  Wrench,
  ClipboardList,
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
} from "lucide-react";

function SettingsCard({ title, description, icon: Icon, children }) {
  return (
    <div className="border border-border/50 rounded-xl bg-card overflow-hidden card-hover">
      <div className="px-6 py-4 border-b border-border/50 flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h3 className="font-heading font-semibold text-sm">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

function UsageBar({ label, current, max, icon: Icon }) {
  const percent = max > 0 ? Math.round((current / max) * 100) : 0;
  const isWarning = percent >= 80;
  const isDanger = percent >= 95;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {label}
        </span>
        <span className={`text-sm font-mono font-semibold ${isDanger ? 'text-red-500' : isWarning ? 'text-amber-500' : 'text-foreground'}`}>
          {current}/{max}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            isDanger ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-primary'
          }`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
      <p className="text-[11px] text-muted-foreground text-right">{percent}% utilizado</p>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  // Org form
  const [orgNome, setOrgNome] = useState("");
  const [orgCnpj, setOrgCnpj] = useState("");

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);

  useEffect(() => {
    loadOrg();
  }, []);

  const loadOrg = async () => {
    try {
      const res = await getOrganization();
      setOrg(res.data);
      setOrgNome(res.data.nome || "");
      setOrgCnpj(res.data.cnpj || "");
    } catch (error) {
      toast.error("Erro ao carregar configurações");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveOrg = async (e) => {
    e.preventDefault();
    if (!orgNome.trim()) {
      toast.error("Nome da organização é obrigatório");
      return;
    }
    setSaving(true);
    try {
      await updateOrganization({ nome: orgNome, cnpj: orgCnpj });
      toast.success("Organização atualizada com sucesso!");
      loadOrg();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao atualizar");
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (!currentPassword || !newPassword) {
      toast.error("Preencha todos os campos");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("A nova senha deve ter pelo menos 6 caracteres");
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error("As senhas não conferem");
      return;
    }
    setChangingPassword(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      toast.success("Senha alterada com sucesso!");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao alterar senha");
    } finally {
      setChangingPassword(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  const planBadge = {
    free: "plan-free",
    pro: "plan-pro",
    enterprise: "plan-enterprise",
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto" data-testid="settings-page">
      <div>
        <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
          <Settings className="h-6 w-6 text-primary" />
          Configurações
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Gerencie sua organização e preferências
        </p>
      </div>

      {/* Organization Settings */}
      <SettingsCard
        title="Organização"
        description="Informações da sua empresa"
        icon={Building2}
      >
        <form onSubmit={handleSaveOrg} className="space-y-4">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 mb-4">
            <span className={`inline-flex items-center text-xs px-2.5 py-1 rounded-md font-semibold ${planBadge[org?.plano] || planBadge.free}`}>
              {org?.plano?.toUpperCase()}
            </span>
            <span className="text-xs text-muted-foreground">
              Status: <span className="font-medium text-emerald-500">{org?.subscription_status}</span>
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm">Nome da Organização</Label>
              <Input
                value={orgNome}
                onChange={(e) => setOrgNome(e.target.value)}
                className="h-10 rounded-lg"
                placeholder="Minha Empresa"
                disabled={user?.role !== "admin"}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm">CNPJ</Label>
              <Input
                value={orgCnpj}
                onChange={(e) => setOrgCnpj(e.target.value)}
                className="h-10 rounded-lg"
                placeholder="00.000.000/0001-00"
                disabled={user?.role !== "admin"}
              />
            </div>
          </div>

          {user?.role === "admin" && (
            <Button type="submit" disabled={saving} className="rounded-lg h-9">
              {saving ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Salvar alterações
            </Button>
          )}
        </form>
      </SettingsCard>

      {/* Usage */}
      <SettingsCard
        title="Uso do Plano"
        description="Consumo atual dos seus recursos"
        icon={Shield}
      >
        <div className="space-y-5">
          <UsageBar
            label="Equipamentos"
            current={org?.usage?.equipamentos || 0}
            max={org?.limits?.max_equipamentos || 10}
            icon={Wrench}
          />
          <UsageBar
            label="Usuários"
            current={org?.usage?.users || 0}
            max={org?.limits?.max_users || 5}
            icon={Users}
          />
          <UsageBar
            label="OS este mês"
            current={org?.usage?.os_mes || 0}
            max={org?.limits?.max_os_mes || 50}
            icon={ClipboardList}
          />
        </div>
        {org?.features && org.features.length > 0 && (
          <div className="mt-6 pt-4 border-t border-border/50">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Recursos inclusos</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {org.features.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                  <span className="text-muted-foreground">{f}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </SettingsCard>

      {/* Change Password */}
      <SettingsCard
        title="Alterar Senha"
        description="Mantenha sua conta segura"
        icon={Lock}
      >
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-sm">Senha Atual</Label>
            <div className="relative">
              <Input
                type={showPasswords ? "text" : "password"}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="h-10 rounded-lg pr-10"
                placeholder="••••••••"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => setShowPasswords(!showPasswords)}
              >
                {showPasswords ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm">Nova Senha</Label>
              <Input
                type={showPasswords ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="h-10 rounded-lg"
                placeholder="Mínimo 6 caracteres"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm">Confirmar Nova Senha</Label>
              <Input
                type={showPasswords ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="h-10 rounded-lg"
                placeholder="Repita a senha"
              />
            </div>
          </div>
          <Button type="submit" disabled={changingPassword} variant="outline" className="rounded-lg h-9">
            {changingPassword ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Lock className="h-4 w-4 mr-2" />
            )}
            Alterar Senha
          </Button>
        </form>
      </SettingsCard>
    </div>
  );
}
