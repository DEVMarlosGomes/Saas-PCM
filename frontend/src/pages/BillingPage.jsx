import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getBillingPlan, createBillingCheckout, getCheckoutStatus, getBillingTransactions } from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  CreditCard,
  Check,
  Crown,
  Zap,
  Building2,
  RefreshCw,
  ArrowRight,
  AlertCircle,
  TrendingUp,
  Shield,
  Users,
  Settings,
  ClipboardList,
} from "lucide-react";

function UsageMeter({ label, current, max, icon: Icon }) {
  const percent = max > 0 ? Math.min((current / max) * 100, 100) : 0;
  const isWarning = percent >= 80;
  const isDanger = percent >= 95;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Icon className="h-4 w-4" />
          <span>{label}</span>
        </div>
        <span className={`font-mono font-semibold ${isDanger ? 'text-red-500' : isWarning ? 'text-amber-500' : 'text-foreground'}`}>
          {current} / {max >= 9999 ? '∞' : max}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isDanger ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-primary'
          }`}
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}

function PlanCard({ plan, label, price, features, current, onUpgrade, loading }) {
  const isCurrent = current;
  const planIcons = { free: Zap, pro: Crown, enterprise: Building2 };
  const Icon = planIcons[plan] || Zap;

  return (
    <div className={`relative border rounded-lg p-6 transition-all ${
      isCurrent 
        ? 'border-primary bg-primary/5 ring-2 ring-primary/20' 
        : 'border-border bg-card hover:border-primary/50'
    }`}>
      {isCurrent && (
        <div className="absolute -top-3 left-4 bg-primary text-primary-foreground text-xs font-semibold px-3 py-1 rounded-full">
          Plano Atual
        </div>
      )}
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg ${isCurrent ? 'bg-primary/10' : 'bg-muted'}`}>
          <Icon className={`h-6 w-6 ${isCurrent ? 'text-primary' : 'text-muted-foreground'}`} />
        </div>
        <div>
          <h3 className="font-heading font-bold text-lg">{label}</h3>
          <p className="text-2xl font-bold">
            {price === 0 ? 'Grátis' : `$${price}`}
            {price > 0 && <span className="text-sm font-normal text-muted-foreground">/mês</span>}
          </p>
        </div>
      </div>
      <ul className="space-y-2 mb-6">
        {features.map((f, i) => (
          <li key={i} className="flex items-center gap-2 text-sm">
            <Check className="h-4 w-4 text-green-500 shrink-0" />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      {!isCurrent && plan !== 'free' && (
        <Button 
          className="w-full" 
          onClick={() => onUpgrade(plan)} 
          disabled={loading}
        >
          {loading ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <ArrowRight className="h-4 w-4 mr-2" />}
          Fazer Upgrade
        </Button>
      )}
      {isCurrent && (
        <div className="text-center text-sm text-muted-foreground py-2">
          <Shield className="h-4 w-4 inline mr-1" />
          Seu plano ativo
        </div>
      )}
    </div>
  );
}

export default function BillingPage() {
  const { user } = useAuth();
  const [billingData, setBillingData] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);

  const loadBilling = useCallback(async () => {
    try {
      const [planRes, txRes] = await Promise.all([
        getBillingPlan(),
        getBillingTransactions().catch(() => ({ data: [] }))
      ]);
      setBillingData(planRes.data);
      setTransactions(txRes.data || []);
    } catch (error) {
      console.error("Error loading billing:", error);
      toast.error("Erro ao carregar informações de billing");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBilling();
  }, [loadBilling]);

  // Check for session_id in URL (return from Stripe)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    if (sessionId) {
      pollPaymentStatus(sessionId);
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    const maxAttempts = 8;
    const pollInterval = 2000;

    if (attempts >= maxAttempts) {
      toast.info("Verifique o status do pagamento em alguns instantes.");
      loadBilling();
      return;
    }

    try {
      const res = await getCheckoutStatus(sessionId);
      if (res.data.payment_status === "paid") {
        toast.success(`Upgrade para plano ${res.data.plan.toUpperCase()} realizado com sucesso!`);
        loadBilling();
        return;
      } else if (res.data.status === "expired") {
        toast.error("Sessão de pagamento expirada. Tente novamente.");
        loadBilling();
        return;
      }
      // Keep polling
      setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
    } catch (error) {
      console.error("Poll error:", error);
      if (attempts < maxAttempts - 1) {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
      }
    }
  };

  const handleUpgrade = async (plan) => {
    setUpgrading(true);
    try {
      const originUrl = window.location.origin;
      const res = await createBillingCheckout({ plan, origin_url: originUrl });
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (error) {
      const detail = error.response?.data?.detail || "Erro ao iniciar checkout";
      toast.error(detail);
    } finally {
      setUpgrading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const allPlans = billingData?.all_plans || {};
  const planFeatures = {
    free: [
      `${allPlans.free?.max_equipamentos || 10} equipamentos`,
      `${allPlans.free?.max_users || 5} usuários`,
      `${allPlans.free?.max_os_mes || 50} OS/mês`,
      "Dashboard básico",
      "Relatórios limitados",
    ],
    pro: [
      `${allPlans.pro?.max_equipamentos || 100} equipamentos`,
      `${allPlans.pro?.max_users || 50} usuários`,
      `${allPlans.pro?.max_os_mes || 500} OS/mês`,
      "Dashboard completo",
      "Relatórios avançados",
      "Suporte prioritário",
    ],
    enterprise: [
      "Equipamentos ilimitados",
      "Usuários ilimitados",
      "OS ilimitadas",
      "Dashboard completo",
      "API dedicada",
      "Suporte 24/7",
      "SLA customizado",
    ],
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto" data-testid="billing-page">
      {/* Header */}
      <div>
        <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
          <CreditCard className="h-7 w-7 text-primary" />
          Planos & Faturamento
        </h1>
        <p className="text-muted-foreground mt-1">Gerencie sua assinatura e acompanhe o uso dos recursos</p>
      </div>

      {/* Usage Overview */}
      <div className="border border-border rounded-lg p-6 bg-card">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-heading font-semibold text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            Uso dos Recursos
          </h2>
          <span className={`text-xs font-semibold px-3 py-1 rounded-full ${
            billingData?.plano === 'enterprise' ? 'bg-purple-500/10 text-purple-500' :
            billingData?.plano === 'pro' ? 'bg-amber-500/10 text-amber-500' :
            'bg-muted text-muted-foreground'
          }`}>
            {billingData?.plano?.toUpperCase()}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <UsageMeter
            label="Equipamentos"
            current={billingData?.usage?.equipamentos || 0}
            max={billingData?.limits?.max_equipamentos || 10}
            icon={Settings}
          />
          <UsageMeter
            label="Usuários"
            current={billingData?.usage?.users || 0}
            max={billingData?.limits?.max_users || 5}
            icon={Users}
          />
          <UsageMeter
            label="OS este mês"
            current={billingData?.usage?.os_mes || 0}
            max={billingData?.limits?.max_os_mes || 50}
            icon={ClipboardList}
          />
        </div>
      </div>

      {/* Plan Cards */}
      <div>
        <h2 className="font-heading font-semibold text-lg mb-4">Escolha seu Plano</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Object.entries(allPlans).map(([key, plan]) => (
            <PlanCard
              key={key}
              plan={key}
              label={plan.label}
              price={plan.price}
              features={planFeatures[key] || []}
              current={billingData?.plano === key}
              onUpgrade={handleUpgrade}
              loading={upgrading}
            />
          ))}
        </div>
      </div>

      {/* Transaction History */}
      {transactions.length > 0 && (
        <div className="border border-border rounded-lg p-6 bg-card">
          <h2 className="font-heading font-semibold text-lg mb-4 flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Histórico de Transações
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Data</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Plano</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Valor</th>
                  <th className="text-left py-2 px-3 font-medium text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id} className="border-b border-border/50">
                    <td className="py-2 px-3">
                      {tx.created_at ? new Date(tx.created_at).toLocaleDateString('pt-BR') : '-'}
                    </td>
                    <td className="py-2 px-3 font-medium uppercase">{tx.plan}</td>
                    <td className="py-2 px-3">${tx.amount?.toFixed(2)}</td>
                    <td className="py-2 px-3">
                      <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${
                        tx.payment_status === 'paid' 
                          ? 'bg-green-500/10 text-green-500' 
                          : tx.payment_status === 'pending'
                          ? 'bg-amber-500/10 text-amber-500'
                          : 'bg-red-500/10 text-red-500'
                      }`}>
                        {tx.payment_status === 'paid' ? <Check className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                        {tx.payment_status === 'paid' ? 'Pago' : tx.payment_status === 'pending' ? 'Pendente' : tx.payment_status}
                      </span>
                    </td>
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
