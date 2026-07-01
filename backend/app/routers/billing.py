from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy.orm import Session

from ..deps import (
    get_db, get_current_user, check_plan_limit, check_plan_feature,
    criar_notificacao, create_audit_log, send_email_notification,
    hash_password, verify_password, create_access_token, create_refresh_token,
    set_auth_cookies, get_jwt_secret, get_org_usage, get_next_os_number,
    check_brute_force, record_failed_attempt, clear_failed_attempts,
    JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    SMTP_HOST, SMTP_USER,
)
from ..models.core import (
    Organization, User, Grupo, Subgrupo, Equipamento, OrdemServico,
    CustoOS, Setor, PlanoPreventivo, AuditoriaLog, LoginAttempt,
    PasswordResetToken, PaymentTransaction, OSEquipe, Colaborador,
    OSHistorico, OSExcecaoArea, Notificacao, ConfiguracaoMonitoramento,
    LeituraSensor, AlertaPreditivo,
    UserRole, TipoOS, PrioridadeOS, StatusOS, TipoCusto, PlanoSaaS, PLAN_LIMITS,
)
from ..schemas.main import (
    OrganizationCreate, OrganizationResponse,
    UserRegister, UserLogin, UserResponse, UserCreate,
    TechnicianSessionRequest, TecnicoLoginRequest,
    SetorCreate, SetorResponse, GrupoCreate, GrupoResponse,
    SubgrupoCreate, SubgrupoResponse,
    EquipamentoCreate, EquipamentoResponse,
    OSCreate, OSUpdate, OSResponse, OSEquipeCreate, OSEquipeResponse,
    OSHistoricoResponse, OSExcecaoAreaResponse, CustoMaoObraUpdate,
    CustoCreate, CustoResponse, PlanoCreate, PlanoResponse,
    DashboardKPIs, BillingPlanResponse, CheckoutRequest,
    ColaboradorCreate, ColaboradorUpdate, ColaboradorResponse,
)
from ..settings import settings
import jwt as _jwt
from ..middleware.rate_limiter import (
    limiter, LIMIT_AUTH, LIMIT_BILLING, LIMIT_IOT, LIMIT_APIKEY, LIMIT_STRICT,
)
from slowapi.errors import RateLimitExceeded

import stripe

router = APIRouter(tags=["Billing"])


@router.get("/billing/plan")
async def get_billing_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current plan info and usage for the organization"""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])

    def safe_percent(current, maximum):
        if maximum == -1:
            return 0.0
        if not maximum:
            return 0.0
        return round((current / maximum) * 100, 1)

    usage_percent = {
        "equipamentos": safe_percent(usage["equipamentos"], limits["max_equipamentos"]),
        "users": safe_percent(usage["users"], limits["max_users"]),
        "os_mes": safe_percent(usage["os_mes"], limits["max_os_mes"]),
    }

    return {
        "plano": org.plano.value,
        "subscription_status": org.subscription_status or "active",
        "limits": {
            "max_equipamentos": limits["max_equipamentos"],
            "max_users": limits["max_users"],
            "max_os_mes": limits["max_os_mes"],
        },
        "usage": usage,
        "usage_percent": usage_percent,
        "all_plans": {
            plan.value: {
                "label": info["label"],
                "price": info["price"],
                "preco_mensal": info.get("preco_mensal", info["price"]),
                "max_equipamentos": info["max_equipamentos"],
                "max_users": info["max_users"],
                "max_os_mes": info["max_os_mes"],
                "destaque": info.get("destaque", False),
                "cta_tipo": info.get("cta_tipo", "stripe_checkout"),
                "features": info.get("features", []),
            }
            for plan, info in PLAN_LIMITS.items()
        },
    }

@router.post("/billing/checkout")
@limiter.limit(LIMIT_BILLING)
async def create_billing_checkout(data: CheckoutRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a Stripe checkout session for plan upgrade"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode alterar o plano")
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    # Validate plan
    plan_key = data.plan.lower()
    try:
        target_plan = PlanoSaaS(plan_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Plano inválido")
    
    if target_plan == PlanoSaaS.DEMO:
        raise HTTPException(status_code=400, detail="Não é possível fazer checkout para o plano Demo")

    if target_plan == PlanoSaaS.ENTERPRISE:
        raise HTTPException(status_code=400, detail="Para o plano Enterprise, entre em contato com o comercial Aurix")
    
    if org.plano == target_plan:
        raise HTTPException(status_code=400, detail="Você já está neste plano")
    
    # Get amount from server-side PLAN_LIMITS (never from frontend)
    plan_info = PLAN_LIMITS[target_plan]
    amount = plan_info["price"]
    
    # Build URLs from provided origin
    origin_url = data.origin_url.rstrip("/")
    success_url = f"{origin_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/billing"
    
    import json as json_lib
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
        
        api_key = os.environ.get("STRIPE_API_KEY", "")
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        
        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
        
        checkout_request = CheckoutSessionRequest(
            amount=float(amount),
            currency="usd",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "organization_id": str(org.id),
                "plan": target_plan.value,
                "user_id": str(user.id),
            }
        )
        
        session = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Create pending transaction record
        transaction = PaymentTransaction(
            organization_id=org.id,
            session_id=session.session_id,
            plan=target_plan.value,
            amount=float(amount),
            currency="usd",
            payment_status="pending",
            metadata_json=json_lib.dumps({
                "organization_id": str(org.id),
                "plan": target_plan.value,
                "user_id": str(user.id),
            })
        )
        db.add(transaction)
        db.commit()
        
        return {"url": session.url, "session_id": session.session_id}
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar sessão de pagamento: {str(e)}")

@router.get("/billing/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check payment status and update if completed"""
    import json as json_lib
    
    transaction = db.query(PaymentTransaction).filter(PaymentTransaction.session_id == session_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    
    # If already processed, return status
    if transaction.payment_status == "paid":
        return {"status": "complete", "payment_status": "paid", "plan": transaction.plan}
    
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        
        api_key = os.environ.get("STRIPE_API_KEY", "")
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        
        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
        checkout_status = await stripe_checkout.get_checkout_status(session_id)
        
        # Update transaction
        transaction.payment_status = checkout_status.payment_status
        
        # If paid and not already processed, upgrade the plan
        if checkout_status.payment_status == "paid" and transaction.payment_status != "paid":
            transaction.payment_status = "paid"
        
        if checkout_status.payment_status == "paid":
            org = db.query(Organization).filter(Organization.id == transaction.organization_id).first()
            if org:
                target_plan = PlanoSaaS(transaction.plan)
                plan_info = PLAN_LIMITS[target_plan]
                org.plano = target_plan
                org.limite_equipamentos = plan_info["max_equipamentos"]
                org.limite_usuarios = plan_info["max_users"]
                org.limite_os_mes = plan_info["max_os_mes"]
                org.subscription_status = "active"
        
        db.commit()
        
        return {
            "status": checkout_status.status,
            "payment_status": checkout_status.payment_status,
            "plan": transaction.plan,
        }
    except Exception as e:
        logger.error(f"Checkout status error: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao verificar pagamento: {str(e)}")

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks"""
    import json as json_lib
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
        
        api_key = os.environ.get("STRIPE_API_KEY", "")
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        
        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
        body = await request.body()
        signature = request.headers.get("Stripe-Signature", "")
        
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        if webhook_response and webhook_response.session_id:
            transaction = db.query(PaymentTransaction).filter(
                PaymentTransaction.session_id == webhook_response.session_id
            ).first()
            
            if transaction and transaction.payment_status != "paid":
                transaction.payment_status = webhook_response.payment_status or "unknown"
                
                if webhook_response.payment_status == "paid":
                    org = db.query(Organization).filter(Organization.id == transaction.organization_id).first()
                    if org:
                        target_plan = PlanoSaaS(transaction.plan)
                        plan_info = PLAN_LIMITS[target_plan]
                        org.plano = target_plan
                        org.limite_equipamentos = plan_info["max_equipamentos"]
                        org.limite_usuarios = plan_info["max_users"]
                        org.limite_os_mes = plan_info["max_os_mes"]
                        org.subscription_status = "active"
                
                db.commit()
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/billing/transactions")
async def list_transactions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List payment transactions for the organization"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    transactions = db.query(PaymentTransaction).filter(
        PaymentTransaction.organization_id == user.organization_id
    ).order_by(PaymentTransaction.created_at.desc()).limit(20).all()
    
    return [{
        "id": str(t.id),
        "session_id": t.session_id,
        "plan": t.plan,
        "amount": t.amount,
        "currency": t.currency,
        "payment_status": t.payment_status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    } for t in transactions]

@router.post("/billing/change-plan")
async def change_plan_direct(
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Troca de plano direta (sem Stripe). Disponível para ambientes sem integração de pagamento."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas administradores podem alterar o plano")

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    plan_key = (data.get("plan") or "").lower().strip()
    try:
        target_plan = PlanoSaaS(plan_key)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Plano inválido: {plan_key}")

    if target_plan == PlanoSaaS.ENTERPRISE:
        raise HTTPException(status_code=400, detail="Para o plano Enterprise, entre em contato com o comercial Aurix")

    if org.plano == target_plan:
        raise HTTPException(status_code=400, detail="Você já está neste plano")

    plan_info = PLAN_LIMITS[target_plan]

    old_plan = org.plano.value
    org.plano = target_plan
    org.limite_equipamentos = plan_info["max_equipamentos"]
    org.limite_usuarios = plan_info["max_users"]
    org.limite_os_mes = plan_info["max_os_mes"]

    import json as _json
    tx = PaymentTransaction(
        organization_id=org.id,
        session_id=f"direct_{old_plan}_to_{target_plan.value}_{int(datetime.now().timestamp())}",
        plan=target_plan.value,
        amount=plan_info["price"],
        currency="brl",
        payment_status="paid",
        metadata_json=_json.dumps({
            "organization_id": str(org.id),
            "plan": target_plan.value,
            "previous_plan": old_plan,
            "user_id": str(user.id),
            "method": "direct",
        }),
    )
    db.add(tx)
    db.commit()

    return {
        "ok": True,
        "plano_anterior": old_plan,
        "plano": target_plan.value,
        "label": plan_info["label"],
        "message": f"Plano alterado para {plan_info['label']} com sucesso.",
    }

@router.get("/billing/portal")
async def get_billing_portal(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return Stripe Customer Portal URL for managing subscription/payment methods"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    if not org.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura Stripe ativa. Faça upgrade para um plano pago primeiro.")
    try:
        import stripe as stripe_sdk
        stripe_sdk.api_key = os.environ.get("STRIPE_API_KEY", "")
        origin = request.headers.get("origin", "")
        return_url = f"{origin}/billing"
        session = stripe_sdk.billing_portal.Session.create(
            customer=org.stripe_customer_id,
            return_url=return_url,
        )
        return {"url": session.url}
    except ImportError:
        raise HTTPException(status_code=503, detail="Integração Stripe não disponível")
    except Exception as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar sessão do portal Stripe")

@router.post("/billing/cancelar")
async def cancelar_assinatura(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancel the active Stripe subscription and downgrade org to DEMO"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    if org.plano == "DEMO":
        raise HTTPException(status_code=400, detail="Você já está no plano Demo")
    cancelled_in_stripe = False
    if org.stripe_subscription_id:
        try:
            import stripe as stripe_sdk
            stripe_sdk.api_key = os.environ.get("STRIPE_API_KEY", "")
            stripe_sdk.Subscription.cancel(org.stripe_subscription_id)
            cancelled_in_stripe = True
        except Exception as e:
            logger.warning(f"Stripe cancel error (continuing): {e}")
    org.plano = "DEMO"
    org.stripe_subscription_id = None
    db.commit()
    return {"ok": True, "cancelled_in_stripe": cancelled_in_stripe, "plano": "DEMO"}

# ========== CONFIABILIDADE / RELIABILITY ==========
import math
