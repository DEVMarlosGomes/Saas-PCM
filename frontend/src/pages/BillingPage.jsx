import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";
import { getBillingPlan, createBillingCheckout, getCheckoutStatus, getBillingTransactions } from "../lib/api";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { useSearchParams } from "react-router-dom";
import {
  CreditCard,
  Zap,
  Crown,
  Building2,
  CheckCircle2,
  ArrowRight,
  Loader2,
  Shield,
  Star,
  Receipt,
  Clock,
  ExternalLink,
} from "lucide-react";

const planIcons = {
  free: Shield,
  pro: Zap,
  enterprise: Crown,
};

const planColors = {
  free: {
    border: "border-border/50",
    badge: "plan-free",
    button: "bg-muted text-foreground hover:bg-muted/80",
    glow: "",
  },
  pro: {
    border: "border-blue-500/30",
    badge: "plan-pro",
    button: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20",
    glow: "ring-1 ring-blue-500/20",
  },
  enterprise: {
    border: "border-amber-500/30",
    badge: "plan-enterprise",
    button: "bg-gradient-to-r from-amber-500 to-purple-500 text-white hover:opacity-90 shadow-lg",
    glow: "ring-1 ring-amber-500/20",
  },
};

function PlanCard({ plan, planKey, currentPlan, isRecommended, onUpgrade, upgrading }) {
  const Icon = planIcons[planKey] || Shield;
  const colors = planColors[planKey] || planColors.free;
  const isCurrent = currentPlan === planKey;
  const isDowngrade = (currentPlan === "enterprise" && planKey !== "enterprise") ||
                      (currentPlan === "pro" && planKey === "free");

  return (
    <div className={`relative border rounded-xl bg-card p-6 flex flex-col card-hover ${colors.border} ${isRecommended ? colors.glow : ''}`}>
      {isRecommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center gap-1 bg-primary text-primary-foreground text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full shadow-lg shadow-primary/20">
            <Star className="h-3 w-3" />
            Recomendado
          </span>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2.5 rounded-xl ${planKey === 'free' ? 'bg-muted' : planKey === 'pro' ? 'bg-blue-500/10' : 'bg-amber-500/10'}`}>
          <Icon className={`h-5 w-5 ${planKey === 'free' ? 'text-muted-foreground' : planKey === 'pro' ? 'text-blue-500' : 'text-amber-500'}`} />
        </div>
        <div>
          <h3 className="font-heading font-bold text-lg">{plan.label}</h3>
          {isCurrent && (
            <span className="text-[10px] font-semibold text-emerald-500 uppercase tracking-wider">Seu plano atual</span>
          )}
        </div>
      </div>

      <div className="mb-6">
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold font-heading">
            {plan.price === 0 ? "Grátis" : `$${plan.price}`}
          </span>
          {plan.price > 0 && <span className="text-sm text-muted-foreground">/mês</span>}
        </div>
      </div>

      <div className="space-y-3 flex-1 mb-6">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Inclui:</p>
        <div className="space-y-2.5">
          <FeatureItem text={`${plan.max_equipamentos >= 9999 ? 'Ilimitados' : plan.max_equipamentos} equipamentos`} />
          <FeatureItem text={`${plan.max_users >= 999 ? 'Ilimitados' : plan.max_users} usuários`} />
          <FeatureItem text={`${plan.max_os_mes >= 9999 ? 'Ilimitadas' : plan.max_os_mes} OS/mês`} />
          {planKey === "pro" && <FeatureItem text="Planos preventivos" />}
          {planKey === "pro" && <FeatureItem text="Suporte prioritário" />}
          {planKey === "enterprise" && <FeatureItem text="API de integração" />}
          {planKey === "enterprise" && <FeatureItem text="Suporte 24/7 dedicado" />}
          {planKey === "enterprise" && <FeatureItem text="SLA garantido" />}
        </div>
      </div>

      <Button
        className={`w-full h-11 rounded-lg font-semibold transition-all ${colors.button}`}
        disabled={isCurrent || isDowngrade || upgrading}
        onClick={() => onUpgrade(planKey)}
      >
        {upgrading ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : isCurrent ? (
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Plano Atual
          </span>
        ) : isDowngrade ? (
          "Não disponível"
        ) : (
          <span className="flex items-center gap-2">
            Fazer Upgrade
            <ArrowRight className="h-4 w-4" />
          </span>
        )}
      </Button>
    </div>
  );
}

function FeatureItem({ text }) {
  return (
    <div className="flex items-center gap-2.5">
      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
      <span className="text-sm text-muted-foreground">{text}</span>
    </div>
  );
}

export default function BillingPage() {
  const { user } = useAuth();
  const [billing, setBilling] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [searchParams] = useSearchParams();

  const loadData = useCallback(async () => {
    try {
      const [billingRes, txRes] = await Promise.all([
        getBillingPlan(),
        getBillingTransactions().catch(() => ({ data: [] })),
      ]);
      setBilling(billingRes.data);
      setTransactions(txRes.data || []);
    } catch (error) {
      toast.error("Erro ao carregar plano");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Check for session_id in URL (return from Stripe)
  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    if (sessionId) {
      checkPayment(sessionId);
    }
  }, [searchParams]);

  const checkPayment = async (sessionId) => {
    try {
      const res = await getCheckoutStatus(sessionId);
      if (res.data.payment_status === "paid") {
        toast.success(`Plano atualizado para ${res.data.plan.toUpperCase()}!`);
        loadData();
      }
    } catch (error) {
      console.error("Payment check error:", error);
    }
  };

  const handleUpgrade = async (plan) => {
    if (user?.role !== "admin") {
      toast.error("Apenas administradores podem alterar o plano");
      return;
    }
    setUpgrading(true);
    try {
      const res = await createBillingCheckout({
        plan,
        origin_url: window.location.origin,
      });
      if (res.data.url) {
        window.location.href = res.data.url;
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Erro ao iniciar checkout");
    } finally {
      setUpgrading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const allPlans = billing?.all_plans || {};
  const currentPlan = billing?.plano || "free";

  return (
    <div className="space-y-8 max-w-5xl mx-auto" data-testid="billing-page">
      {/* Header */}
      <div className="text-center">
        <h1 className="font-heading text-3xl font-bold flex items-center justify-center gap-3">
          <CreditCard className="h-8 w-8 text-primary" />
          Planos & Billing
        </h1>
        <p className="text-muted-foreground mt-2 text-sm max-w-md mx-auto">
          Escolha o plano ideal para o tamanho da sua operação industrial
        </p>
      </div>

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Object.entries(allPlans).map(([key, plan]) => (
          <PlanCard
            key={key}
            planKey={key}
            plan={plan}
            currentPlan={currentPlan}
            isRecommended={key === "pro"}
            onUpgrade={handleUpgrade}
            upgrading={upgrading}
          />
        ))}
      </div>

      {/* Current Usage */}
      {billing && (
        <div className="border border-border/50 rounded-xl bg-card p-6 card-hover">
          <h3 className="font-heading font-semibold flex items-center gap-2 mb-4">
            <Shield className="h-5 w-5 text-primary" />
            Uso atual do plano {currentPlan.toUpperCase()}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { label: "Equipamentos", current: billing.usage?.equipamentos, max: billing.limits?.max_equipamentos, percent: billing.usage_percent?.equipamentos },
              { label: "Usuários", current: billing.usage?.users, max: billing.limits?.max_users, percent: billing.usage_percent?.users },
              { label: "OS este mês", current: billing.usage?.os_mes, max: billing.limits?.max_os_mes, percent: billing.usage_percent?.os_mes },
            ].map((item) => (
              <div key={item.label} className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{item.label}</span>
                  <span className="font-mono font-semibold">{item.current || 0}/{item.max || 0}</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      (item.percent || 0) >= 95 ? 'bg-red-500' :
                      (item.percent || 0) >= 80 ? 'bg-amber-500' : 'bg-primary'
                    }`}
                    style={{ width: `${Math.min(item.percent || 0, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transactions */}
      {transactions.length > 0 && (
        <div className="border border-border/50 rounded-xl bg-card overflow-hidden card-hover">
          <div className="px-6 py-4 border-b border-border/50 flex items-center gap-2">
            <Receipt className="h-5 w-5 text-primary" />
            <h3 className="font-heading font-semibold text-sm">Histórico de Pagamentos</h3>
          </div>
          <div className="divide-y divide-border/30">
            {transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between px-6 py-3.5">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${tx.payment_status === 'paid' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                  <div>
                    <p className="text-sm font-medium">Upgrade para {tx.plan?.toUpperCase()}</p>
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {tx.created_at ? new Date(tx.created_at).toLocaleDateString('pt-BR') : '—'}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-mono font-semibold">${tx.amount?.toFixed(2)}</p>
                  <p className={`text-[10px] font-semibold uppercase ${tx.payment_status === 'paid' ? 'text-emerald-500' : 'text-amber-500'}`}>
                    {tx.payment_status}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
