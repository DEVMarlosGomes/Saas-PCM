import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getOrganization, updateOrganization, changePassword, generateApiKey, revokeApiKey } from "../lib/api";
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
  XCircle,
  Key,
  Copy,
  RefreshCw,
  Trash2,
  AlertTriangle,
} from "lucide-react";

const PLAN_LABELS = {
  demo: { label: "Demo", cls: "bg-slate-500/10 text-slate-400 border border-slate-500/20" },
  essencial: { label: "Essencial", cls: "bg-blue-500/10 text-blue-400 border border-blue-500/20" },
  profissional: { label: "Profissional", cls: "bg-primary/10 text-primary border border-primary/20" },
  avancado: { label: "Avançado", cls: "bg-purple-500/10 text-purple-400 border border-purple-500/20" },
  enterprise: { label: "Enterprise", cls: "bg-amber-500/10 text-amber-400 border border-amber-500/20" },
};

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
  const unlimited = max === -1;
  const percent = unlimited ? 0 : max > 0 ? Math.round((current / max) * 100) : 0;
  const isWarning = !unlimited && percent >= 80;
  const isDanger = !unlimited && percent >= 95;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {label}
        </span>
        <span className={`text-sm font-mono font-semibold ${isDanger ? "text-red-500" : isWarning ? "text-amber-500" : "text-foreground"}`}>
          {current}{unlimited ? " / ∞" : ` / ${max}`}
        </span>
      </div>
      {!unlimited && (
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${isDanger ? "bg-red-500" : isWarning ? "bg-amber-500" : "bg-primary"}`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
      )}
      <p className="text-[11px] text-muted-foreground text-right">
        {unlimited ? "Ilimitado" : `${percent}% utilizado`}
      </p>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [org, setOrg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  const [orgNome, setOrgNome] = useState("");
  const [orgCnpj, setOrgCnpj] = useState("");

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);

  // API key state
  const [apiKeyPreview, setApiKeyPreview] = useState(null);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [fullApiKey, setFullApiKey] = useState(null);
  const [generatingKey, setGeneratingKey] = useState(false);
  const [revokingKey, setRevokingKey] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);

  useEffect(() => { loadOrg(); }, []);

  const loadOrg = async () => {
    try {
      const res = await getOrganization();
      setOrg(res.data);
      setOrgNome(res.data.nome || "");
      setOrgCnpj(res.data.cnpj || "");
      setHasApiKey(res.data.has_api_key || false);
      setApiKeyPreview(res.data.api_key_preview || null);
      setFullApiKey(null);
    } catch {
      toast.error("Erro ao carregar configurações");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveOrg = async (e) => {
    e.preventDefault();
    if (!orgNome.trim()) { toast.error("Nome da organização é obrigatório"); return; }
    setSaving(true);
    try {
      await updateOrganization({ nome: orgNome, cnpj: orgCnpj });
      toast.success("Organização atualizada com sucesso!");
      loadOrg();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao atualizar");
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (!currentPassword || !newPassword) { toast.error("Preencha todos os campos"); return; }
    if (newPassword.length < 6) { toast.error("A nova senha deve ter pelo menos 6 caracteres"); return; }
    if (newPassword !== confirmPassword) { toast.error("As senhas não conferem"); return; }
    setChangingPassword(true);
    try {
      await changePassword({ current_password: currentPassword, new_password: newPassword });
      toast.success("Senha alterada com sucesso!");
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao alterar senha");
    } finally {
      setChangingPassword(false);
    }
  };

  const handleGenerateKey = async () => {
    setGeneratingKey(true);
    try {
      const res = await generateApiKey();
      setFullApiKey(res.data.api_key);
      setHasApiKey(true);
      setApiKeyPreview(res.data.api_key.slice(0, 12) + "...");
      toast.success("API key gerada! Copie agora — ela não será exibida novamente.");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao gerar API key");
    } finally {
      setGeneratingKey(false);
    }
  };

  const handleRevokeKey = async () => {
    setRevokingKey(true);
    try {
      await revokeApiKey();
      setHasApiKey(false);
      setApiKeyPreview(null);
      setFullApiKey(null);
      setShowRevokeConfirm(false);
      toast.success("API key revogada.");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Erro ao revogar API key");
    } finally {
      setRevokingKey(false);
    }
  };

  const copyKey = () => {
    if (!fullApiKey) return;
    navigator.clipboard.writeText(fullApiKey);
    toast.success("API key copiada!");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  const planInfo = PLAN_LABELS[org?.plano] || PLAN_LABELS.demo;
  const isAdmin = user?.role === "admin";
  const hasIoT = org?.plan_features?.api_iot;

  return (
    <div className="space-y-6 max-w-3xl mx-auto" data-testid="settings-page">
      <div>
        <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
          <Settings className="h-6 w-6 text-primary" />
          Configurações
        </h1>
        <p className="text-muted-foreground text-sm mt-1">Gerencie sua organização e preferências</p>
      </div>

      {/* Organization */}
      <SettingsCard title="Organização" description="Informações da sua empresa" icon={Building2}>
        <form onSubmit={handleSaveOrg} className="space-y-4">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 mb-4">
            <span className={`inline-flex items-center text-xs px-2.5 py-1 rounded-md font-semibold ${planInfo.cls}`}>
              {planInfo.label}
            </span>
            <span className="text-xs text-muted-foreground">
              Status: <span className="font-medium text-emerald-500">{org?.subscription_status}</span>
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm">Nome da Organização</Label>
              <Input value={orgNome} onChange={(e) => setOrgNome(e.target.value)}
                className="h-10 rounded-lg" placeholder="Minha Empresa" disabled={!isAdmin} />
            </div>
            <div className="space-y-2">
              <Label className="text-sm">CNPJ</Label>
              <Input value={orgCnpj} onChange={(e) => setOrgCnpj(e.target.value)}
                className="h-10 rounded-lg" placeholder="00.000.000/0001-00" disabled={!isAdmin} />
            </div>
          </div>

          {isAdmin && (
            <Button type="submit" disabled={saving} className="rounded-lg h-9">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              Salvar alterações
            </Button>
          )}
        </form>
      </SettingsCard>

      {/* Usage */}
      <SettingsCard title="Uso do Plano" description="Consumo atual dos seus recursos" icon={Shield}>
        <div className="space-y-5">
          <UsageBar label="Equipamentos" current={org?.usage?.equipamentos || 0}
            max={org?.limits?.max_equipamentos || 10} icon={Wrench} />
          <UsageBar label="Usuários" current={org?.usage?.users || 0}
            max={org?.limits?.max_users || 5} icon={Users} />
          <UsageBar label="OS este mês" current={org?.usage?.os_mes || 0}
            max={org?.limits?.max_os_mes || 50} icon={ClipboardList} />
        </div>

        {/* Plan features checklist */}
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

      {/* API Key — only shown to admins when plan includes api_iot */}
      {isAdmin && (
        <SettingsCard
          title="API Key — Integração IoT"
          description="Autentique dispositivos e sistemas externos via X-API-Key"
          icon={Key}
        >
          {!hasIoT ? (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/40 border border-dashed border-border">
              <XCircle className="h-5 w-5 text-muted-foreground shrink-0" />
              <div>
                <p className="text-sm font-medium">Recurso não disponível no plano atual</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Integração IoT está disponível a partir do plano <strong>Profissional</strong>.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {fullApiKey ? (
                <div className="space-y-2">
                  <Label className="text-sm text-amber-400 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Copie agora — não será exibida novamente
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      readOnly
                      value={fullApiKey}
                      className="h-10 rounded-lg font-mono text-xs bg-muted"
                    />
                    <Button variant="outline" size="icon" className="h-10 w-10 shrink-0" onClick={copyKey} title="Copiar">
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : hasApiKey ? (
                <div className="space-y-2">
                  <Label className="text-sm">API Key atual</Label>
                  <div className="flex gap-2">
                    <Input readOnly value={apiKeyPreview || "••••••••••••..."} className="h-10 rounded-lg font-mono text-xs bg-muted" />
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhuma API key configurada.</p>
              )}

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 gap-2"
                  onClick={handleGenerateKey}
                  disabled={generatingKey}
                >
                  {generatingKey
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <RefreshCw className="h-3.5 w-3.5" />}
                  {hasApiKey ? "Regenerar" : "Gerar API Key"}
                </Button>

                {hasApiKey && !showRevokeConfirm && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 gap-2 text-destructive hover:text-destructive"
                    onClick={() => setShowRevokeConfirm(true)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Revogar
                  </Button>
                )}

                {showRevokeConfirm && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Confirmar revogação?</span>
                    <Button
                      variant="destructive"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={handleRevokeKey}
                      disabled={revokingKey}
                    >
                      {revokingKey ? <Loader2 className="h-3 w-3 animate-spin" /> : "Sim, revogar"}
                    </Button>
                    <Button variant="ghost" size="sm" className="h-8 text-xs"
                      onClick={() => setShowRevokeConfirm(false)}>
                      Cancelar
                    </Button>
                  </div>
                )}
              </div>

              <p className="text-xs text-muted-foreground">
                Use o header <code className="bg-muted px-1 py-0.5 rounded text-[11px]">X-API-Key: {"<sua-key>"}</code> nas chamadas ao endpoint{" "}
                <code className="bg-muted px-1 py-0.5 rounded text-[11px]">POST /api/iot/telemetria</code>.
              </p>
            </div>
          )}
        </SettingsCard>
      )}

      {/* Change Password */}
      <SettingsCard title="Alterar Senha" description="Mantenha sua conta segura" icon={Lock}>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-sm">Senha Atual</Label>
            <div className="relative">
              <Input type={showPasswords ? "text" : "password"} value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="h-10 rounded-lg pr-10" placeholder="••••••••" />
              <Button type="button" variant="ghost" size="icon"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => setShowPasswords(!showPasswords)}>
                {showPasswords ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm">Nova Senha</Label>
              <Input type={showPasswords ? "text" : "password"} value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="h-10 rounded-lg" placeholder="Mínimo 6 caracteres" />
            </div>
            <div className="space-y-2">
              <Label className="text-sm">Confirmar Nova Senha</Label>
              <Input type={showPasswords ? "text" : "password"} value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="h-10 rounded-lg" placeholder="Repita a senha" />
            </div>
          </div>
          <Button type="submit" disabled={changingPassword} variant="outline" className="rounded-lg h-9">
            {changingPassword ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Lock className="h-4 w-4 mr-2" />}
            Alterar Senha
          </Button>
        </form>
      </SettingsCard>
    </div>
  );
}
