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

router = APIRouter(tags=["Autenticação"])

# ── Helpers locais ────────────────────────────────────────────────────────────
_GRUPOS_PADRAO = {
    "MECANICA": ["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Preditiva", "Utilidades"],
    "TI": ["Infraestrutura", "Sistemas", "Conectividade", "Segurança"],
    "ELETRICA": ["Alta Tensão", "Automação/CLP", "Instrumentação", "Utilidades"],
}

def _seed_grupos_padrao(db, org_id):
    for setor, subgrupos in _GRUPOS_PADRAO.items():
        grp = Grupo(organization_id=org_id, nome=setor, descricao=f"Grupo padrão {setor}")
        db.add(grp)
        db.flush()
        for sg_nome in subgrupos:
            db.add(Subgrupo(organization_id=org_id, grupo_id=grp.id, nome=sg_nome))
    db.commit()


@router.post("/auth/register")
@limiter.limit(LIMIT_AUTH)
async def register(data: UserRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    # Create organization
    org_nome = data.organization_nome or f"Empresa de {data.nome}"
    org = Organization(
        nome=org_nome,
        plano_trial_expira_em=datetime.now(timezone.utc) + timedelta(days=10),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    _seed_grupos_padrao(db, org.id)
    
    # Create user as admin
    hashed = hash_password(data.password)
    user = User(
        email=email,
        password_hash=hashed,
        nome=data.nome,
        role=UserRole.ADMIN,
        organization_id=org.id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))
    set_auth_cookies(response, access_token, refresh_token)
    
    return {
        "id": str(user.id),
        "email": user.email,
        "nome": user.nome,
        "role": user.role.value,
        "setor": user.setor,
        "is_lider": user.is_lider or False,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "access_token": access_token,
    }

@router.post("/auth/login")
async def login(data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    
    if not check_brute_force(db, identifier):
        raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em 15 minutos.")
    
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.password_hash):
        record_failed_attempt(db, identifier)
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    if not user.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado")
    
    clear_failed_attempts(db, identifier)

    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))
    set_auth_cookies(response, access_token, refresh_token)

    _login_ip = request.headers.get("X-Forwarded-For", ip).split(",")[0].strip()
    create_audit_log(
        db, str(user.organization_id), str(user.id), "user", str(user.id),
        "login",
        ip=_login_ip,
        user_agent=request.headers.get("User-Agent"),
    )

    return {
        "id": str(user.id),
        "email": user.email,
        "nome": user.nome,
        "role": user.role.value,
        "setor": user.setor,
        "is_lider": user.is_lider or False,
        "employee_id": user.employee_id,
        "generic_session_sector": user.generic_session_sector,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "access_token": access_token,
        "needs_technician_session": user.role == UserRole.TECNICO and not user.generic_session_sector,
    }

@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logout realizado com sucesso"}

@router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    limits = PLAN_LIMITS.get(org.plano if org else PlanoSaaS.DEMO, PLAN_LIMITS[PlanoSaaS.DEMO])
    features = {
        "modulo_preditivo": limits.get("modulo_preditivo", False),
        "planos_preventivos": limits.get("planos_preventivos", False),
        "relatorios": limits.get("relatorios", False),
        "dashboard_avancado": limits.get("dashboard_avancado", False),
        "aprovacao_setor": limits.get("aprovacao_setor", False),
        "exportacao_pdf": limits.get("exportacao_pdf", False),
        "kanban": limits.get("kanban", False),
    }
    return {
        "id": str(user.id),
        "email": user.email,
        "nome": user.nome,
        "role": user.role.value,
        "setor": user.setor,
        "is_lider": user.is_lider or False,
        "employee_id": user.employee_id,
        "generic_session_sector": user.generic_session_sector,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "org_plano": org.plano.value if org else "demo",
        "features": features,
        "needs_technician_session": user.role == UserRole.TECNICO and not user.generic_session_sector,
    }

@router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    # Try to get token from cookie or header
    token = request.cookies.get("refresh_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # For header-based auth, we use the access token to identify user
            try:
                payload = _jwt.decode(auth_header[7:], get_jwt_secret(), algorithms=[JWT_ALGORITHM])
                user = db.query(User).filter(User.id == payload["sub"]).first()
                if user:
                    new_access_token = create_access_token(str(user.id), user.email)
                    return {"message": "Token atualizado", "access_token": new_access_token}
            except:
                pass
        raise HTTPException(status_code=401, detail="Token de refresh não encontrado")
    try:
        payload = _jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        access_token = create_access_token(str(user.id), user.email)
        _prod = settings.is_production
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=_prod,
            samesite="strict" if _prod else "lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
        )
        return {"message": "Token atualizado", "access_token": access_token}
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ========== TECHNICIAN SESSION ==========

@router.post("/auth/technician-session")
async def set_technician_session(
    data: TechnicianSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Segunda etapa do login genérico do técnico.
    Associa sector + matrícula funcional à sessão atual.
    O banco armazena generic_session_sector e employee_id para auditoria.
    """
    if user.role != UserRole.TECNICO:
        raise HTTPException(status_code=403, detail="Apenas técnicos precisam desta etapa de login.")
    if not data.sector.strip():
        raise HTTPException(status_code=400, detail="Setor obrigatório.")
    if not data.employee_id.strip():
        raise HTTPException(status_code=400, detail="Matrícula obrigatória.")

    user.generic_session_sector = data.sector.strip().upper()
    user.employee_id = data.employee_id.strip()
    db.commit()
    db.refresh(user)

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    limits = PLAN_LIMITS.get(org.plano if org else PlanoSaaS.DEMO, PLAN_LIMITS[PlanoSaaS.DEMO])
    features = {
        "modulo_preditivo": limits.get("modulo_preditivo", False),
        "planos_preventivos": limits.get("planos_preventivos", False),
        "relatorios": limits.get("relatorios", False),
        "dashboard_avancado": limits.get("dashboard_avancado", False),
        "aprovacao_setor": limits.get("aprovacao_setor", False),
        "exportacao_pdf": limits.get("exportacao_pdf", False),
        "kanban": limits.get("kanban", False),
    }

    create_audit_log(
        db, str(user.organization_id), str(user.id), "user", str(user.id),
        "technician_session",
        dados_novos=f'{{"sector": "{user.generic_session_sector}", "employee_id": "{user.employee_id}"}}',
    )

    return {
        "id": str(user.id),
        "email": user.email,
        "nome": user.nome,
        "role": user.role.value,
        "setor": user.setor,
        "is_lider": user.is_lider or False,
        "employee_id": user.employee_id,
        "generic_session_sector": user.generic_session_sector,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "org_plano": org.plano.value if org else "demo",
        "features": features,
        "needs_technician_session": False,
    }

@router.post("/auth/technician-logout-session")
async def clear_technician_session(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Limpa a sessão genérica do técnico (logout de turno)."""
    if user.role != UserRole.TECNICO:
        raise HTTPException(status_code=403, detail="Apenas técnicos.")
    user.generic_session_sector = None
    db.commit()
    return {"message": "Sessão de turno encerrada."}

@router.post("/auth/tecnico-login")
async def tecnico_login(
    data: TecnicoLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Login genérico para técnicos de manutenção via senha compartilhada do setor.
    Não requer conta individual prévia — identifica o técnico pela matrícula (employee_id).
    Se a matrícula coincidir com um usuário cadastrado, usa o nome dele; caso contrário usa a matrícula como nome.
    """
    setor = db.query(Setor).filter(
        Setor.id == data.sector_id,
        Setor.ativo == True,
    ).first()
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado ou inativo.")

    if not verify_password(data.senha_generica, setor.senha_tecnico_hash):
        raise HTTPException(status_code=401, detail="Senha genérica inválida.")

    if not data.employee_id.strip():
        raise HTTPException(status_code=400, detail="Matrícula obrigatória.")

    employee_id = data.employee_id.strip()

    # Tenta achar um usuário registrado com essa matrícula na mesma organização
    usuario_registrado = db.query(User).filter(
        User.organization_id == setor.organization_id,
        User.employee_id == employee_id,
        User.ativo == True,
    ).first()

    nome_funcionario = usuario_registrado.nome if usuario_registrado else employee_id

    # Resolve o user_id para o token: usa o cadastrado ou o primeiro TECNICO da org como âncora
    if usuario_registrado:
        user_id = str(usuario_registrado.id)
        user_email = usuario_registrado.email
        # Grava o setor na sessão do usuário
        usuario_registrado.generic_session_sector = setor.nome
        usuario_registrado.employee_id = employee_id
        db.commit()
    else:
        # Sem cadastro: procura um usuário TECNICO genérico da org para emitir o token
        tecnico_generico = db.query(User).filter(
            User.organization_id == setor.organization_id,
            User.role == UserRole.TECNICO,
            User.ativo == True,
        ).first()
        if not tecnico_generico:
            raise HTTPException(
                status_code=404,
                detail="Nenhum usuário técnico cadastrado nesta organização. Cadastre ao menos um técnico.",
            )
        user_id = str(tecnico_generico.id)
        user_email = tecnico_generico.email
        # Usa employee_id passado como matrícula ativa da sessão
        tecnico_generico.generic_session_sector = setor.nome
        tecnico_generico.employee_id = employee_id
        db.commit()

    access_token = create_access_token(user_id, user_email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token)

    return {
        "token": access_token,
        "user": {
            "role": "tecnico",
            "employee_id": employee_id,
            "sector_id": str(setor.id),
            "sector_name": setor.nome,
            "nome_funcionario": nome_funcionario,
        },
    }

@router.get("/sectors/tecnico-options")
async def get_sectors_for_tecnico(
    tenant_id: str,
    db: Session = Depends(get_db),
):
    """
    Lista setores disponíveis para o login genérico do técnico.
    Não requer autenticação — apenas tenant_id (organization_id) como query param.
    """
    setores = db.query(Setor).filter(
        Setor.organization_id == tenant_id,
        Setor.ativo == True,
    ).order_by(Setor.nome).all()
    return [{"id": str(s.id), "nome": s.nome} for s in setores]


# ========== USERS ENDPOINTS ==========

@router.post("/auth/change-password")
async def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change password for currently authenticated user"""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="A nova senha deve ter pelo menos 6 caracteres")
    
    user.password_hash = hash_password(data.new_password)
    db.commit()
    
    return {"message": "Senha alterada com sucesso"}

# ========== GRUPOS ENDPOINTS ==========
