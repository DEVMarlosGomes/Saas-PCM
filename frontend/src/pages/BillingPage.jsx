import { useState, useEffect, useCallback } from "react";
import "./BillingPage.css";
import { useAuth } from "../contexts/AuthContext";
import { getBillingPlan, getBillingTransactions, getBillingPortal, cancelarAssinatura, changePlan } from "../lib/api";
import { toast } from "sonner";
import {
  ArrowRight,
  BarChart3,
  Building2,
  Check,
  Clock,
  Crown,
  ExternalLink,
  Headphones,
  Loader2,
  Play,
  Receipt,
  Settings2,
  Shield,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  XCircle,
  Zap,
} from "lucide-react";

// ─── Planos AURIX ────────────────────────────────────────────────────────────

const PLANS = [
  {
    key: "demo",
    name: "Demo",
    subtitle: "Experimente a Aurix",
    price: null,
    priceLabel: "GRÁTIS",
    icon: Play,
    ctaTipo: "trial",
    ctaTexto: "EXPERIMENTAR GRÁTIS",
    destaque: false,
    features: [
      { text: "Até 3 colaboradores", included: true },
      { text: "Até 5 equipamentos", included: true },
      { text: "10 dias de teste", included: true },
      { text: "Análise de relatórios", included: false },
      { text: "Módulo preditivo", included: false },
      { text: "Planos preventivos", included: false },
    ],
  },
  {
    key: "essencial",
    name: "Essencial",
    subtitle: "Comece com eficiência",
    price: 250,
    icon: Settings2,
    ctaTipo: "stripe_checkout",
    ctaTexto: "ASSINAR PLANO",
    destaque: false,
    features: [
      { text: "Até 10 colaboradores", included: true },
      { text: "Até 20 equipamentos", included: true },
      { text: "Análise de indicadores", included: true },
      { text: "Suporte por e-mail", included: true },
      { text: "Módulo preditivo", included: false },
      { text: "WhatsApp integrado", included: false },
    ],
  },
  {
    key: "profissional",
    name: "Profissional",
    subtitle: "Escala com inteligência",
    price: 490,
    icon: Crown,
    ctaTipo: "stripe_checkout",
    ctaTexto: "ASSINAR PLANO",
    destaque: true,
    features: [
      { text: "Até 45 colaboradores", included: true },
      { text: "Até 35 equipamentos", included: true },
      { text: "Setores independentes", included: true },
      { text: "Dashboards e Kanban", included: true },
      { text: "Módulo preditivo (10 equip.)", included: true },
      { text: "Suporte prioritário", included: true },
    ],
  },
  {
    key: "avancado",
    name: "Avançado",
    subtitle: "Gestão que gera resultado",
    price: 790,
    icon: TrendingUp,
    ctaTipo: "stripe_checkout",
    ctaTexto: "ASSINAR PLANO",
    destaque: false,
    features: [
      { text: "Até 100 colaboradores", included: true },
      { text: "Até 50 equipamentos", included: true },
      { text: "Dashboards avançados", included: true },
      { text: "Relatórios personalizados", included: true },
      { text: "Módulo preditivo (30 equip.)", included: true },
      { text: "WhatsApp integrado", included: true },
    ],
  },
  {
    key: "enterprise",
    name: "Enterprise",
    subtitle: "Solução sem limites",
    price: 1290,
    icon: Building2,
    ctaTipo: "contato",
    ctaTexto: "FALE CONOSCO",
    destaque: false,
    features: [
      { text: "Colaboradores ilimitados", included: true },
      { text: "Equipamentos ilimitados", included: true },
      { text: "Todas funcionalidades", included: true },
      { text: "Integrações avançadas (SCADA/ERP)", included: true },
      { text: "SSO (SAML 2.0)", included: true },
      { text: "Suporte dedicado + SLA", included: true },
    ],
  },
];

const TRUST_ITEMS = [
  {
    icon: ShieldCheck,
    title: "Segurança",
    desc: "Seus dados protegidos com criptografia avançada.",
  },
  {
    icon: Zap,
    title: "Performance",
    desc: "Plataforma escalável para alto desempenho industrial.",
  },
  {
    icon: Settings2,
    title: "Integração",
    desc: "Conecte máquinas, sistemas e pessoas.",
  },
  {
    icon: Headphones,
    title: "Suporte Especializado",
    desc: "Time técnico preparado para sua operação.",
  },
];

// ─── Componentes ─────────────────────────────────────────────────────────────

function PricingBadge() {
  return (
    <div className="pricing-badge" data-testid="popular-badge">
      MAIS POPULAR
    </div>
  );
}

function PricingFeatureItem({ text, included }) {
  return (
    <li className="pricing-feature-item">
      {included ? (
        <Check className="pricing-feature-icon pricing-feature-icon--check" size={16} />
      ) : (
        <X className="pricing-feature-icon pricing-feature-icon--x" size={14} />
      )}
      <span className={included ? "" : "pricing-feature-text--excluded"}>{text}</span>
    </li>
  );
}

function PricingCard({ plan, currentPlan, onSelect, loading }) {
  const isCurrent = currentPlan === plan.key;
  const Icon = plan.icon;
  const isLoading = loading === plan.key;

  return (
    <article
      className={`pricing-card ${plan.destaque ? "pricing-card--popular" : ""} ${isCurrent ? "pricing-card--current" : ""}`}
      data-testid={`pricing-card-${plan.key}`}
    >
      {plan.destaque && <PricingBadge />}

      <div className="pricing-card__header">
        <div className="pricing-card__icon" data-testid={`pricing-icon-${plan.key}`}>
          <Icon size={22} />
        </div>
        <div>
          <h3 className="pricing-card__name">{plan.name}</h3>
          <p className="pricing-card__subtitle">{plan.subtitle}</p>
        </div>
      </div>

      <div className="pricing-card__price">
        {plan.price === null ? (
          <span className="pricing-card__price-free">{plan.priceLabel}</span>
        ) : (
          <>
            <span className="pricing-card__price-currency">R$</span>
            <span className="pricing-card__price-value">{plan.price.toLocaleString("pt-BR")}</span>
            <span className="pricing-card__price-period">/mês</span>
          </>
        )}
      </div>

      <ul className="pricing-card__features">
        {plan.features.map((f) => (
          <PricingFeatureItem key={f.text} text={f.text} included={f.included} />
        ))}
      </ul>

      <button
        className={`pricing-card__cta ${plan.destaque ? "pricing-card__cta--primary" : "pricing-card__cta--outline"} ${isCurrent ? "pricing-card__cta--current" : ""}`}
        disabled={isCurrent || isLoading}
        onClick={() => onSelect(plan)}
        data-testid={`btn-${plan.key === "enterprise" ? "fale-conosco" : plan.key === "demo" ? "experimentar-gratis" : "assinar-plano"}-${plan.key}`}
      >
        {isLoading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : isCurrent ? (
          <>
            <Check size={16} />
            Plano atual
          </>
        ) : (
          plan.ctaTexto
        )}
      </button>
    </article>
  );
}

function UsageBar({ label, current, max, percent }) {
  const pct = Math.min(percent ?? 0, 100);
  const isWarning = pct >= 61 && pct <= 85;
  const isDanger = pct > 85;
  const isUnlimited = max === -1;

  return (
    <div className="usage-item" data-testid={`usage-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <div className="usage-item__header">
        <span className="usage-item__label">{label}</span>
        <span className="usage-item__value">
          {isUnlimited ? `${current} / ∞` : `${current} / ${max}`}
          {isDanger && !isUnlimited && (
            <span className="usage-item__badge usage-item__badge--danger">LIMITE PRÓXIMO</span>
          )}
          {isWarning && !isUnlimited && (
            <span className="usage-item__badge usage-item__badge--warning">ATENÇÃO ⚠</span>
          )}
        </span>
      </div>
      {!isUnlimited && (
        <div className="usage-bar-track">
          <div
            className={`usage-bar-fill ${isDanger ? "usage-bar-fill--danger" : isWarning ? "usage-bar-fill--warning" : "usage-bar-fill--ok"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}

function EnterpriseContactModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose} data-testid="enterprise-modal-overlay">
      <div className="modal-box" onClick={(e) => e.stopPropagation()} data-testid="enterprise-modal">
        <div className="modal-box__header">
          <Building2 size={24} className="modal-box__icon" />
          <h2>Fale com o Comercial Aurix</h2>
        </div>
        <p className="modal-box__body">
          O plano Enterprise é negociado diretamente com nossa equipe comercial.
          Entre em contato para desenharmos uma solução sem limites para sua operação.
        </p>
        <div className="modal-box__actions">
          <a
            href="mailto:comercial@aurix.com.br?subject=Interesse%20no%20plano%20Enterprise%20Aurix"
            className="btn-primary"
            data-testid="btn-contato-enterprise-email"
          >
            Enviar e-mail
          </a>
          <button className="btn-outline" onClick={onClose} data-testid="btn-contato-fechar">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

export default function BillingPage() {
  const { user } = useAuth();
  const [billing, setBilling] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(null);
  const [showEnterpriseModal, setShowEnterpriseModal] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [confirmPlan, setConfirmPlan] = useState(null); // plan object awaiting confirmation

  const loadData = useCallback(async () => {
    try {
      const [billingRes, txRes] = await Promise.all([
        getBillingPlan(),
        getBillingTransactions().catch(() => ({ data: [] })),
      ]);
      setBilling(billingRes.data);
      setTransactions(txRes.data || []);
    } catch {
      toast.error("Erro ao carregar informações do plano");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Check for Stripe redirect on return
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    if (sessionId) {
      toast.success("Pagamento processado! Seu plano será atualizado em instantes.");
      window.history.replaceState({}, "", "/billing");
      setTimeout(loadData, 2000);
    }
  }, [loadData]);

  const handleOpenPortal = async () => {
    setPortalLoading(true);
    try {
      const res = await getBillingPortal();
      if (res.data?.url) window.location.href = res.data.url;
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Erro ao acessar portal Stripe");
    } finally {
      setPortalLoading(false);
    }
  };

  const handleCancelar = async () => {
    setCancelLoading(true);
    try {
      await cancelarAssinatura();
      toast.success("Assinatura cancelada. Seu plano foi revertido para Demo.");
      setShowCancelConfirm(false);
      await loadData();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Erro ao cancelar assinatura");
    } finally {
      setCancelLoading(false);
    }
  };

  const handlePlanSelect = (plan) => {
    if (plan.ctaTipo === "contato") {
      setShowEnterpriseModal(true);
      return;
    }
    if (plan.ctaTipo === "trial") {
      toast.info("Você já está no período de demonstração Aurix.");
      return;
    }
    // Abre modal de confirmação antes de trocar
    setConfirmPlan(plan);
  };

  const handleConfirmPlan = async () => {
    if (!confirmPlan) return;
    setCheckoutLoading(confirmPlan.key);
    try {
      const res = await changePlan(confirmPlan.key);
      const label = res.data?.label || confirmPlan.name;
      toast.success(`Plano alterado para ${label} com sucesso!`);
      setConfirmPlan(null);
      await loadData();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Erro ao trocar plano");
    } finally {
      setCheckoutLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="billing-loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const currentPlan = billing?.plano || "demo";
  const usage = billing?.usage || {};
  const limits = billing?.limits || {};
  const usagePct = billing?.usage_percent || {};

  return (
    <div className="billing-page" data-testid="billing-page">
      <div className="billing-bg" />

      <div className="billing-shell">

        {/* ── Hero ─────────────────────────────────────────────────────── */}
        <header className="billing-hero" data-testid="billing-hero">
          <div className="billing-hero__eyebrow">
            <Sparkles size={14} />
            Tecnologia para a Gestão Industrial
          </div>

          <div className="billing-hero__brand">
            <span className="billing-hero__brand-text">AURI</span>
            <span className="billing-hero__brand-accent">X</span>
          </div>

          <div className="billing-hero__tagline">
            <p>
              Estratégia que <strong className="billing-hero__highlight">CORTA</strong> custos.
            </p>
            <p>
              Tecnologia que <strong className="billing-hero__highlight">AMPLIFICA</strong> resultados.
            </p>
          </div>
        </header>

        {/* ── Uso atual (quando já tem plano ativo) ────────────────────── */}
        {billing && currentPlan !== "demo" && (
          <section className="billing-usage-card" data-testid="billing-usage">
            <div className="billing-usage-card__title">
              <Shield size={18} />
              <span>
                Plano atual: <strong>{(PLANS.find((p) => p.key === currentPlan)?.name || currentPlan).toUpperCase()}</strong>
              </span>
            </div>

            <div className="billing-usage-card__grid">
              <UsageBar
                label="Colaboradores"
                current={usage.users ?? 0}
                max={limits.max_users ?? 0}
                percent={usagePct.users}
              />
              <UsageBar
                label="Equipamentos"
                current={usage.equipamentos ?? 0}
                max={limits.max_equipamentos ?? 0}
                percent={usagePct.equipamentos}
              />
              <UsageBar
                label="OS este mês"
                current={usage.os_mes ?? 0}
                max={limits.max_os_mes ?? 0}
                percent={usagePct.os_mes}
              />
            </div>
          </section>
        )}

        {/* ── Gerenciar assinatura (planos pagos) ─────────────────────── */}
        {billing && currentPlan !== "demo" && user?.role === "admin" && (
          <section className="billing-manage-section" data-testid="billing-manage">
            <div className="billing-manage-section__title">
              <Settings2 size={16} />
              Gerenciar Assinatura
            </div>
            <div className="billing-manage-section__actions">
              <button
                className="btn-outline billing-manage-btn"
                onClick={handleOpenPortal}
                disabled={portalLoading}
                data-testid="btn-portal-stripe"
              >
                {portalLoading ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
                Gerenciar no Stripe
              </button>
              <button
                className="btn-outline billing-manage-btn billing-manage-btn--danger"
                onClick={() => setShowCancelConfirm(true)}
                disabled={cancelLoading}
                data-testid="btn-cancelar-assinatura"
              >
                <XCircle size={14} />
                Cancelar Assinatura
              </button>
            </div>
          </section>
        )}

        {/* ── Confirmar cancelamento ───────────────────────────────────── */}
        {showCancelConfirm && (
          <div className="modal-overlay" onClick={() => setShowCancelConfirm(false)} data-testid="cancel-confirm-overlay">
            <div className="modal-box" onClick={(e) => e.stopPropagation()} data-testid="cancel-confirm-modal">
              <div className="modal-box__header">
                <XCircle size={24} className="modal-box__icon" style={{ color: "#EF4444" }} />
                <h2>Cancelar Assinatura</h2>
              </div>
              <p className="modal-box__body">
                Tem certeza que deseja cancelar sua assinatura? Seu plano será revertido para <strong>Demo</strong> e você perderá acesso a todos os recursos pagos.
              </p>
              <div className="modal-box__actions">
                <button
                  className="btn-primary"
                  style={{ background: "#EF4444", borderColor: "#EF4444" }}
                  onClick={handleCancelar}
                  disabled={cancelLoading}
                  data-testid="btn-confirmar-cancelamento"
                >
                  {cancelLoading ? <Loader2 size={14} className="animate-spin" /> : null}
                  Sim, cancelar
                </button>
                <button className="btn-outline" onClick={() => setShowCancelConfirm(false)} data-testid="btn-cancelar-fechar">
                  Voltar
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Grid de planos ───────────────────────────────────────────── */}
        <section className="billing-plans-section" data-testid="billing-plans">
          <div className="billing-plans-section__head">
            <h2 className="billing-plans-section__title">
              Planos pensados para escalar a manutenção industrial
            </h2>
            <p className="billing-plans-section__sub">
              Escolha o plano ideal para o tamanho e complexidade da sua operação.
            </p>
          </div>

          <div className="pricing-grid" data-testid="pricing-grid">
            {PLANS.map((plan) => (
              <PricingCard
                key={plan.key}
                plan={plan}
                currentPlan={currentPlan}
                onSelect={handlePlanSelect}
                loading={checkoutLoading}
              />
            ))}
          </div>
        </section>

        {/* ── Diferenciais ─────────────────────────────────────────────── */}
        <section className="billing-trust" data-testid="billing-trust">
          {TRUST_ITEMS.map((item) => (
            <div key={item.title} className="billing-trust__item">
              <div className="billing-trust__icon">
                <item.icon size={20} />
              </div>
              <div>
                <p className="billing-trust__title">{item.title}</p>
                <p className="billing-trust__desc">{item.desc}</p>
              </div>
            </div>
          ))}
        </section>

        {/* ── Histórico de transações ───────────────────────────────────── */}
        {transactions.length > 0 && (
          <section className="billing-transactions" data-testid="billing-transactions">
            <div className="billing-transactions__header">
              <Receipt size={18} />
              <div>
                <h3>Histórico de pagamentos</h3>
                <p>Linha do tempo das últimas movimentações de assinatura.</p>
              </div>
            </div>

            <div className="billing-transactions__list">
              {transactions.map((tx) => (
                <div key={tx.id} className="billing-transactions__item" data-testid={`transaction-${tx.id}`}>
                  <div className="billing-transactions__item-left">
                    <span
                      className={`billing-transactions__dot ${tx.payment_status === "paid" ? "billing-transactions__dot--paid" : "billing-transactions__dot--pending"}`}
                    />
                    <div>
                      <p className="billing-transactions__plan">
                        Upgrade para {tx.plan?.toUpperCase()}
                      </p>
                      <p className="billing-transactions__date">
                        <Clock size={12} />
                        {tx.created_at ? new Date(tx.created_at).toLocaleDateString("pt-BR") : "—"}
                      </p>
                    </div>
                  </div>
                  <div className="billing-transactions__item-right">
                    <p className="billing-transactions__amount">R$ {tx.amount?.toFixed(2)}</p>
                    <span
                      className={`billing-transactions__status ${tx.payment_status === "paid" ? "billing-transactions__status--paid" : "billing-transactions__status--pending"}`}
                    >
                      {tx.payment_status === "paid" ? "Pago" : "Pendente"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      {/* ── Modal Confirmar Troca de Plano ──────────────────────────────── */}
      {confirmPlan && (
        <div
          className="modal-overlay"
          onClick={() => { if (!checkoutLoading) setConfirmPlan(null); }}
          data-testid="confirm-plan-overlay"
        >
          <div className="modal-box" onClick={(e) => e.stopPropagation()} data-testid="confirm-plan-modal">
            <div className="modal-box__header">
              <ArrowRight size={24} className="modal-box__icon" />
              <h2>Confirmar troca de plano</h2>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px", margin: "16px 0" }}>
              {/* De → Para */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "12px", flexWrap: "wrap" }}>
                <span style={{ padding: "6px 14px", borderRadius: "8px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", fontSize: "13px", fontWeight: 600 }}>
                  {(PLANS.find((p) => p.key === currentPlan)?.name || currentPlan).toUpperCase()}
                </span>
                <ArrowRight size={16} style={{ opacity: 0.5 }} />
                <span style={{ padding: "6px 14px", borderRadius: "8px", background: "rgba(26,111,232,0.15)", border: "1px solid rgba(26,111,232,0.3)", fontSize: "13px", fontWeight: 700, color: "#60a5fa" }}>
                  {confirmPlan.name.toUpperCase()}
                </span>
              </div>

              {/* Preço */}
              {confirmPlan.price && (
                <p style={{ textAlign: "center", fontSize: "22px", fontWeight: 800, letterSpacing: "-0.5px" }}>
                  R$ {confirmPlan.price.toLocaleString("pt-BR")}
                  <span style={{ fontSize: "13px", fontWeight: 400, opacity: 0.6 }}>/mês</span>
                </p>
              )}

              {/* Features */}
              <ul style={{ display: "flex", flexDirection: "column", gap: "6px", padding: "12px 16px", background: "rgba(255,255,255,0.03)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.06)", listStyle: "none", margin: 0 }}>
                {confirmPlan.features.filter(f => f.included).map((f) => (
                  <li key={f.text} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px" }}>
                    <Check size={13} style={{ color: "#10b981", flexShrink: 0 }} />
                    {f.text}
                  </li>
                ))}
              </ul>
            </div>

            <div className="modal-box__actions">
              <button
                className="btn-primary"
                onClick={handleConfirmPlan}
                disabled={!!checkoutLoading}
                data-testid="btn-confirmar-plano"
              >
                {checkoutLoading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Confirmar troca
              </button>
              <button
                className="btn-outline"
                onClick={() => setConfirmPlan(null)}
                disabled={!!checkoutLoading}
                data-testid="btn-cancelar-troca"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Enterprise ────────────────────────────────────────────── */}
      {showEnterpriseModal && (
        <EnterpriseContactModal onClose={() => setShowEnterpriseModal(false)} />
      )}
    </div>
  );
}
