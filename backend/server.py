from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import secrets
from urllib.parse import quote_plus

# PostgreSQL with SQLAlchemy
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

ROOT_DIR = Path(__file__).parent

# Database connection - Supabase PostgreSQL
# Handle special characters in password
DB_HOST = os.environ.get('DB_HOST', 'aws-1-sa-east-1.pooler.supabase.com')
DB_PORT = os.environ.get('DB_PORT', '6543')
DB_NAME = os.environ.get('POSTGRES_DB', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres.ehrfwytvchhrzywnutyf')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '@Mgfj125256')

# URL encode the password to handle special characters like @
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if not DATABASE_URL:
    encoded_password = quote_plus(DB_PASSWORD)
    DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== ENUMS ==========
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    LIDER = "lider"
    TECNICO = "tecnico"
    OPERADOR = "operador"

class TipoOS(str, enum.Enum):
    CORRETIVA = "corretiva"
    PREVENTIVA = "preventiva"
    PREDITIVA = "preditiva"

class PrioridadeOS(str, enum.Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

class StatusOS(str, enum.Enum):
    ABERTA = "aberta"
    EM_ATENDIMENTO = "em_atendimento"
    AGUARDANDO_REVISAO = "aguardando_revisao"
    REVISADA = "revisada"
    FECHADA = "fechada"

class TipoCusto(str, enum.Enum):
    CONSUMO = "consumo"
    SUBSTITUICAO = "substituicao"
    MAO_OBRA = "mao_obra"

class PlanoSaaS(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

# Plan limits configuration
PLAN_LIMITS = {
    PlanoSaaS.FREE: {"max_equipamentos": 10, "max_users": 5, "max_os_mes": 50, "price": 0.00, "label": "Free"},
    PlanoSaaS.PRO: {"max_equipamentos": 100, "max_users": 50, "max_os_mes": 500, "price": 99.00, "label": "Pro"},
    PlanoSaaS.ENTERPRISE: {"max_equipamentos": 9999, "max_users": 999, "max_os_mes": 9999, "price": 299.00, "label": "Enterprise"},
}

# ========== MODELS ==========
class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(255), nullable=False)
    cnpj = Column(String(20), unique=True, nullable=True)
    plano = Column(SQLEnum(PlanoSaaS), default=PlanoSaaS.FREE)
    limite_equipamentos = Column(Integer, default=10)
    limite_usuarios = Column(Integer, default=5)
    limite_os_mes = Column(Integer, default=50)
    ativo = Column(Boolean, default=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nome = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.OPERADOR)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Grupo(Base):
    __tablename__ = "grupos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Subgrupo(Base):
    __tablename__ = "subgrupos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Equipamento(Base):
    __tablename__ = "equipamentos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    localizacao = Column(String(255), nullable=True)
    valor_hora = Column(Float, default=0.0)  # Custo de máquina parada por hora
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=True)
    subgrupo_id = Column(UUID(as_uuid=True), ForeignKey("subgrupos.id"), nullable=True)
    ativo = Column(Boolean, default=True)
    criticidade = Column(Integer, default=1)  # 1-5
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (Index('idx_equipamento_org', 'organization_id'),)

class OrdemServico(Base):
    __tablename__ = "ordens_servico"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=True)
    subgrupo_id = Column(UUID(as_uuid=True), ForeignKey("subgrupos.id"), nullable=True)
    tipo = Column(SQLEnum(TipoOS), default=TipoOS.CORRETIVA)
    prioridade = Column(SQLEnum(PrioridadeOS), default=PrioridadeOS.MEDIA)
    status = Column(SQLEnum(StatusOS), default=StatusOS.ABERTA)
    descricao = Column(Text, nullable=False)
    solucao = Column(Text, nullable=True)
    
    # Usuários
    solicitante_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tecnico_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revisor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    inicio_atendimento = Column(DateTime(timezone=True), nullable=True)
    fim_atendimento = Column(DateTime(timezone=True), nullable=True)
    revisado_at = Column(DateTime(timezone=True), nullable=True)
    fechado_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tempos calculados (em minutos)
    tempo_resposta = Column(Integer, nullable=True)
    tempo_reparo = Column(Integer, nullable=True)
    tempo_total = Column(Integer, nullable=True)
    
    # SLA
    dentro_sla = Column(Boolean, default=True)
    
    # Falha
    falha_tipo = Column(String(100), nullable=True)
    falha_modo = Column(String(100), nullable=True)
    falha_causa = Column(String(100), nullable=True)
    reincidente = Column(Boolean, default=False)
    
    # Bloco de parada
    bloco_parada_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Review workflow
    review_deadline = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    auto_approved = Column(Boolean, default=False)
    
    __table_args__ = (Index('idx_os_org', 'organization_id'),)

class CustoOS(Base):
    __tablename__ = "custos_os"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    ordem_servico_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id"), nullable=False)
    tipo = Column(SQLEnum(TipoCusto), nullable=False)
    descricao = Column(String(255), nullable=False)
    valor = Column(Float, nullable=False)
    quantidade = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PlanoPreventivo(Base):
    __tablename__ = "planos_preventivos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    frequencia_dias = Column(Integer, nullable=False)
    ultima_execucao = Column(DateTime(timezone=True), nullable=True)
    proxima_execucao = Column(DateTime(timezone=True), nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuditoriaLog(Base):
    __tablename__ = "auditoria_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    entidade = Column(String(100), nullable=False)
    entidade_id = Column(UUID(as_uuid=True), nullable=False)
    acao = Column(String(50), nullable=False)
    dados_anteriores = Column(Text, nullable=True)
    dados_novos = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(String(255), nullable=False, index=True)
    attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    plan = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="usd")
    payment_status = Column(String(50), default="pending")
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Create tables
Base.metadata.create_all(bind=engine)

# ========== PYDANTIC SCHEMAS ==========
class OrganizationCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None

class OrganizationResponse(BaseModel):
    id: str
    nome: str
    cnpj: Optional[str]
    plano: str
    limite_equipamentos: int
    limite_usuarios: int
    limite_os_mes: int
    ativo: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    nome: str
    organization_nome: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    nome: str
    role: str
    organization_id: str
    ativo: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nome: str
    role: UserRole = UserRole.OPERADOR

class GrupoCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None

class GrupoResponse(BaseModel):
    id: str
    nome: str
    descricao: Optional[str]
    organization_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SubgrupoCreate(BaseModel):
    grupo_id: str
    nome: str
    descricao: Optional[str] = None

class SubgrupoResponse(BaseModel):
    id: str
    grupo_id: str
    nome: str
    descricao: Optional[str]
    organization_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class EquipamentoCreate(BaseModel):
    codigo: str
    nome: str
    descricao: Optional[str] = None
    localizacao: Optional[str] = None
    valor_hora: float = 0.0
    grupo_id: Optional[str] = None
    subgrupo_id: Optional[str] = None
    criticidade: int = 1

class EquipamentoResponse(BaseModel):
    id: str
    codigo: str
    nome: str
    descricao: Optional[str]
    localizacao: Optional[str]
    valor_hora: float
    grupo_id: Optional[str]
    subgrupo_id: Optional[str]
    criticidade: int
    ativo: bool
    organization_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class OSCreate(BaseModel):
    equipamento_id: str
    grupo_id: Optional[str] = None
    subgrupo_id: Optional[str] = None
    tipo: TipoOS = TipoOS.CORRETIVA
    prioridade: PrioridadeOS = PrioridadeOS.MEDIA
    descricao: str
    falha_tipo: Optional[str] = None
    falha_modo: Optional[str] = None
    falha_causa: Optional[str] = None

class OSUpdate(BaseModel):
    status: Optional[StatusOS] = None
    tecnico_id: Optional[str] = None
    solucao: Optional[str] = None
    falha_tipo: Optional[str] = None
    falha_modo: Optional[str] = None
    falha_causa: Optional[str] = None
    review_notes: Optional[str] = None

class OSResponse(BaseModel):
    id: str
    numero: int
    equipamento_id: str
    equipamento_nome: Optional[str] = None
    grupo_id: Optional[str]
    subgrupo_id: Optional[str]
    tipo: str
    prioridade: str
    status: str
    descricao: str
    solucao: Optional[str]
    solicitante_id: str
    tecnico_id: Optional[str]
    revisor_id: Optional[str]
    revisor_nome: Optional[str] = None
    created_at: datetime
    inicio_atendimento: Optional[datetime]
    fim_atendimento: Optional[datetime]
    tempo_resposta: Optional[int]
    tempo_reparo: Optional[int]
    tempo_total: Optional[int]
    dentro_sla: bool
    falha_tipo: Optional[str]
    falha_modo: Optional[str]
    falha_causa: Optional[str]
    reincidente: bool
    organization_id: str
    custo_parada: Optional[float] = None
    review_deadline: Optional[datetime] = None
    review_notes: Optional[str] = None
    auto_approved: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class CustoCreate(BaseModel):
    ordem_servico_id: str
    tipo: TipoCusto
    descricao: str
    valor: float
    quantidade: float = 1.0

class CustoResponse(BaseModel):
    id: str
    ordem_servico_id: str
    tipo: str
    descricao: str
    valor: float
    quantidade: float
    organization_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class PlanoCreate(BaseModel):
    equipamento_id: str
    nome: str
    descricao: Optional[str] = None
    frequencia_dias: int

class PlanoResponse(BaseModel):
    id: str
    equipamento_id: str
    nome: str
    descricao: Optional[str]
    frequencia_dias: int
    ultima_execucao: Optional[datetime]
    proxima_execucao: Optional[datetime]
    ativo: bool
    organization_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DashboardKPIs(BaseModel):
    total_os_mes: int
    os_abertas: int
    os_atrasadas: int
    mttr: float  # Mean Time To Repair (horas)
    mtbf: float  # Mean Time Between Failures (horas)
    disponibilidade: float  # %
    custo_total_mes: float
    custo_parada_mes: float
    avg_tempo_resposta: float  # Average response time in minutes
    preventiva_vs_corretiva: dict
    top_equipamentos_falhas: List[dict]
    top_equipamentos_custos: List[dict]
    top_equipamentos_downtime: List[dict]

class BillingPlanResponse(BaseModel):
    plano: str
    subscription_status: str
    limits: dict
    usage: dict
    usage_percent: dict

class CheckoutRequest(BaseModel):
    plan: str
    origin_url: str

# ========== HELPER FUNCTIONS ==========
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_jwt_secret() -> str:
    return JWT_SECRET

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, 
        "email": email, 
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), 
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id, 
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), 
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    # Use secure=True and samesite="none" for cross-origin HTTPS
    is_production = os.environ.get("FRONTEND_URL", "").startswith("https")
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        secure=is_production, 
        samesite="none" if is_production else "lax", 
        max_age=900, 
        path="/"
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        secure=is_production, 
        samesite="none" if is_production else "lax", 
        max_age=604800, 
        path="/"
    )

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

def check_brute_force(db: Session, identifier: str) -> bool:
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).first()
    if attempt and attempt.locked_until:
        if datetime.now(timezone.utc) < attempt.locked_until:
            return False
        else:
            attempt.attempts = 0
            attempt.locked_until = None
            db.commit()
    return True

def record_failed_attempt(db: Session, identifier: str):
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).first()
    if not attempt:
        attempt = LoginAttempt(identifier=identifier, attempts=1)
        db.add(attempt)
    else:
        attempt.attempts += 1
        if attempt.attempts >= 5:
            attempt.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.commit()

def clear_failed_attempts(db: Session, identifier: str):
    db.query(LoginAttempt).filter(LoginAttempt.identifier == identifier).delete()
    db.commit()

def create_audit_log(db: Session, org_id: str, user_id: str, entidade: str, entidade_id: str, acao: str, dados_anteriores: str = None, dados_novos: str = None):
    log = AuditoriaLog(
        organization_id=org_id,
        user_id=user_id,
        entidade=entidade,
        entidade_id=entidade_id,
        acao=acao,
        dados_anteriores=dados_anteriores,
        dados_novos=dados_novos
    )
    db.add(log)
    db.commit()

def get_next_os_number(db: Session, org_id: str) -> int:
    last_os = db.query(OrdemServico).filter(OrdemServico.organization_id == org_id).order_by(OrdemServico.numero.desc()).first()
    return (last_os.numero + 1) if last_os else 1

def get_org_usage(db: Session, org_id) -> dict:
    """Get current usage counts for an organization"""
    now = datetime.now(timezone.utc)
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    equipamentos_count = db.query(Equipamento).filter(
        Equipamento.organization_id == org_id,
        Equipamento.ativo == True
    ).count()
    
    users_count = db.query(User).filter(
        User.organization_id == org_id,
        User.ativo == True
    ).count()
    
    os_mes_count = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= first_day_month
    ).count()
    
    return {
        "equipamentos": equipamentos_count,
        "users": users_count,
        "os_mes": os_mes_count
    }

def check_plan_limit(db: Session, org: Organization, resource: str) -> tuple:
    """Check if organization has reached its plan limit for a resource.
    Returns (allowed: bool, message: str)"""
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.FREE])
    
    limit_map = {
        "equipamentos": ("max_equipamentos", usage["equipamentos"]),
        "users": ("max_users", usage["users"]),
        "os": ("max_os_mes", usage["os_mes"]),
    }
    
    if resource not in limit_map:
        return True, ""
    
    limit_key, current = limit_map[resource]
    max_val = limits[limit_key]
    
    if current >= max_val:
        plan_label = limits["label"]
        return False, f"Limite do plano {plan_label} atingido: {current}/{max_val} {resource}. Faça upgrade para continuar."
    
    return True, ""

def build_os_response(o, db: Session) -> OSResponse:
    """Build OSResponse with computed custo_parada and enriched names"""
    # Compute downtime cost
    custo_parada = None
    equipamento_nome = None
    equip = db.query(Equipamento).filter(Equipamento.id == o.equipamento_id).first()
    if equip:
        equipamento_nome = equip.nome
        if o.tempo_total and equip.valor_hora:
            custo_parada = round((o.tempo_total / 60) * equip.valor_hora, 2)
    
    # Get reviewer name
    revisor_nome = None
    if o.revisor_id:
        revisor = db.query(User).filter(User.id == o.revisor_id).first()
        if revisor:
            revisor_nome = revisor.nome
    
    return OSResponse(
        id=str(o.id), numero=o.numero, equipamento_id=str(o.equipamento_id),
        equipamento_nome=equipamento_nome,
        grupo_id=str(o.grupo_id) if o.grupo_id else None,
        subgrupo_id=str(o.subgrupo_id) if o.subgrupo_id else None,
        tipo=o.tipo.value, prioridade=o.prioridade.value, status=o.status.value,
        descricao=o.descricao, solucao=o.solucao,
        solicitante_id=str(o.solicitante_id),
        tecnico_id=str(o.tecnico_id) if o.tecnico_id else None,
        revisor_id=str(o.revisor_id) if o.revisor_id else None,
        revisor_nome=revisor_nome,
        created_at=o.created_at, inicio_atendimento=o.inicio_atendimento,
        fim_atendimento=o.fim_atendimento, tempo_resposta=o.tempo_resposta,
        tempo_reparo=o.tempo_reparo, tempo_total=o.tempo_total,
        dentro_sla=o.dentro_sla, falha_tipo=o.falha_tipo,
        falha_modo=o.falha_modo, falha_causa=o.falha_causa,
        reincidente=o.reincidente, organization_id=str(o.organization_id),
        custo_parada=custo_parada,
        review_deadline=o.review_deadline,
        review_notes=o.review_notes,
        auto_approved=o.auto_approved or False
    )

def calculate_sla(prioridade: PrioridadeOS, tempo_resposta: int) -> bool:
    sla_map = {
        PrioridadeOS.CRITICA: 30,
        PrioridadeOS.ALTA: 60,
        PrioridadeOS.MEDIA: 120,
        PrioridadeOS.BAIXA: 480
    }
    return tempo_resposta <= sla_map.get(prioridade, 120)

def check_reincidencia(db: Session, org_id: str, equipamento_id: str, falha_tipo: str) -> bool:
    if not falha_tipo:
        return False
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    count = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.equipamento_id == equipamento_id,
        OrdemServico.falha_tipo == falha_tipo,
        OrdemServico.created_at >= thirty_days_ago
    ).count()
    return count > 1

# ========== APP SETUP ==========
app = FastAPI(title="PCM - Sistema de Gestão de Manutenção Industrial", version="1.0.0")
api_router = APIRouter(prefix="/api")

# CORS
frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("CORS_ORIGINS", "*"))
origins = frontend_url.split(",") if frontend_url != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== AUTH ENDPOINTS ==========
@api_router.post("/auth/register")
async def register(data: UserRegister, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    # Create organization
    org_nome = data.organization_nome or f"Empresa de {data.nome}"
    org = Organization(nome=org_nome)
    db.add(org)
    db.commit()
    db.refresh(org)
    
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
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "access_token": access_token
    }

@api_router.post("/auth/login")
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
    
    return {
        "id": str(user.id),
        "email": user.email,
        "nome": user.nome,
        "role": user.role.value,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "access_token": access_token
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logout realizado com sucesso"}

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "nome": user.nome,
        "role": user.role.value,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo
    }

@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    # Try to get token from cookie or header
    token = request.cookies.get("refresh_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # For header-based auth, we use the access token to identify user
            try:
                payload = jwt.decode(auth_header[7:], get_jwt_secret(), algorithms=[JWT_ALGORITHM])
                user = db.query(User).filter(User.id == payload["sub"]).first()
                if user:
                    new_access_token = create_access_token(str(user.id), user.email)
                    return {"message": "Token atualizado", "access_token": new_access_token}
            except:
                pass
        raise HTTPException(status_code=401, detail="Token de refresh não encontrado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Tipo de token inválido")
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        access_token = create_access_token(str(user.id), user.email)
        is_production = os.environ.get("FRONTEND_URL", "").startswith("https")
        response.set_cookie(
            key="access_token", 
            value=access_token, 
            httponly=True, 
            secure=is_production, 
            samesite="none" if is_production else "lax", 
            max_age=900, 
            path="/"
        )
        return {"message": "Token atualizado", "access_token": access_token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ========== USERS ENDPOINTS ==========
@api_router.get("/users", response_model=List[UserResponse])
async def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    users = db.query(User).filter(User.organization_id == user.organization_id).all()
    return [UserResponse(
        id=str(u.id), email=u.email, nome=u.nome, role=u.role.value,
        organization_id=str(u.organization_id), ativo=u.ativo, created_at=u.created_at
    ) for u in users]

@api_router.post("/users", response_model=UserResponse)
async def create_user(data: UserCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode criar usuários")
    
    # Check plan limit
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    allowed, msg = check_plan_limit(db, org, "users")
    if not allowed:
        raise HTTPException(status_code=402, detail=msg)
    
    existing = db.query(User).filter(User.email == data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")
    
    new_user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        nome=data.nome,
        role=data.role,
        organization_id=user.organization_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return UserResponse(
        id=str(new_user.id), email=new_user.email, nome=new_user.nome, role=new_user.role.value,
        organization_id=str(new_user.organization_id), ativo=new_user.ativo, created_at=new_user.created_at
    )

# ========== GRUPOS ENDPOINTS ==========
@api_router.get("/grupos", response_model=List[GrupoResponse])
async def list_grupos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    grupos = db.query(Grupo).filter(Grupo.organization_id == user.organization_id).all()
    return [GrupoResponse(
        id=str(g.id), nome=g.nome, descricao=g.descricao,
        organization_id=str(g.organization_id), created_at=g.created_at
    ) for g in grupos]

@api_router.post("/grupos", response_model=GrupoResponse)
async def create_grupo(data: GrupoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    grupo = Grupo(nome=data.nome, descricao=data.descricao, organization_id=user.organization_id)
    db.add(grupo)
    db.commit()
    db.refresh(grupo)
    return GrupoResponse(
        id=str(grupo.id), nome=grupo.nome, descricao=grupo.descricao,
        organization_id=str(grupo.organization_id), created_at=grupo.created_at
    )

# ========== SUBGRUPOS ENDPOINTS ==========
@api_router.get("/subgrupos", response_model=List[SubgrupoResponse])
async def list_subgrupos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subgrupos = db.query(Subgrupo).filter(Subgrupo.organization_id == user.organization_id).all()
    return [SubgrupoResponse(
        id=str(s.id), grupo_id=str(s.grupo_id), nome=s.nome, descricao=s.descricao,
        organization_id=str(s.organization_id), created_at=s.created_at
    ) for s in subgrupos]

@api_router.post("/subgrupos", response_model=SubgrupoResponse)
async def create_subgrupo(data: SubgrupoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    subgrupo = Subgrupo(
        grupo_id=data.grupo_id, nome=data.nome, descricao=data.descricao,
        organization_id=user.organization_id
    )
    db.add(subgrupo)
    db.commit()
    db.refresh(subgrupo)
    return SubgrupoResponse(
        id=str(subgrupo.id), grupo_id=str(subgrupo.grupo_id), nome=subgrupo.nome,
        descricao=subgrupo.descricao, organization_id=str(subgrupo.organization_id), created_at=subgrupo.created_at
    )

# ========== EQUIPAMENTOS ENDPOINTS ==========
@api_router.get("/equipamentos", response_model=List[EquipamentoResponse])
async def list_equipamentos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    equipamentos = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.ativo == True
    ).all()
    return [EquipamentoResponse(
        id=str(e.id), codigo=e.codigo, nome=e.nome, descricao=e.descricao,
        localizacao=e.localizacao, valor_hora=e.valor_hora,
        grupo_id=str(e.grupo_id) if e.grupo_id else None,
        subgrupo_id=str(e.subgrupo_id) if e.subgrupo_id else None,
        criticidade=e.criticidade, ativo=e.ativo,
        organization_id=str(e.organization_id), created_at=e.created_at
    ) for e in equipamentos]

@api_router.post("/equipamentos", response_model=EquipamentoResponse)
async def create_equipamento(data: EquipamentoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Check plan limit
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    allowed, msg = check_plan_limit(db, org, "equipamentos")
    if not allowed:
        raise HTTPException(status_code=402, detail=msg)
    
    equipamento = Equipamento(
        codigo=data.codigo, nome=data.nome, descricao=data.descricao,
        localizacao=data.localizacao, valor_hora=data.valor_hora,
        grupo_id=data.grupo_id, subgrupo_id=data.subgrupo_id,
        criticidade=data.criticidade, organization_id=user.organization_id
    )
    db.add(equipamento)
    db.commit()
    db.refresh(equipamento)
    
    create_audit_log(db, str(user.organization_id), str(user.id), "equipamento", str(equipamento.id), "create")
    
    return EquipamentoResponse(
        id=str(equipamento.id), codigo=equipamento.codigo, nome=equipamento.nome,
        descricao=equipamento.descricao, localizacao=equipamento.localizacao,
        valor_hora=equipamento.valor_hora,
        grupo_id=str(equipamento.grupo_id) if equipamento.grupo_id else None,
        subgrupo_id=str(equipamento.subgrupo_id) if equipamento.subgrupo_id else None,
        criticidade=equipamento.criticidade, ativo=equipamento.ativo,
        organization_id=str(equipamento.organization_id), created_at=equipamento.created_at
    )

@api_router.get("/equipamentos/{equipamento_id}", response_model=EquipamentoResponse)
async def get_equipamento(equipamento_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    return EquipamentoResponse(
        id=str(equipamento.id), codigo=equipamento.codigo, nome=equipamento.nome,
        descricao=equipamento.descricao, localizacao=equipamento.localizacao,
        valor_hora=equipamento.valor_hora,
        grupo_id=str(equipamento.grupo_id) if equipamento.grupo_id else None,
        subgrupo_id=str(equipamento.subgrupo_id) if equipamento.subgrupo_id else None,
        criticidade=equipamento.criticidade, ativo=equipamento.ativo,
        organization_id=str(equipamento.organization_id), created_at=equipamento.created_at
    )

@api_router.put("/equipamentos/{equipamento_id}", response_model=EquipamentoResponse)
async def update_equipamento(equipamento_id: str, data: EquipamentoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    for key, value in data.model_dump().items():
        setattr(equipamento, key, value)
    
    db.commit()
    db.refresh(equipamento)
    
    create_audit_log(db, str(user.organization_id), str(user.id), "equipamento", str(equipamento.id), "update")
    
    return EquipamentoResponse(
        id=str(equipamento.id), codigo=equipamento.codigo, nome=equipamento.nome,
        descricao=equipamento.descricao, localizacao=equipamento.localizacao,
        valor_hora=equipamento.valor_hora,
        grupo_id=str(equipamento.grupo_id) if equipamento.grupo_id else None,
        subgrupo_id=str(equipamento.subgrupo_id) if equipamento.subgrupo_id else None,
        criticidade=equipamento.criticidade, ativo=equipamento.ativo,
        organization_id=str(equipamento.organization_id), created_at=equipamento.created_at
    )

@api_router.delete("/equipamentos/{equipamento_id}")
async def delete_equipamento(equipamento_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    equipamento.ativo = False
    db.commit()
    
    create_audit_log(db, str(user.organization_id), str(user.id), "equipamento", str(equipamento.id), "delete")
    
    return {"message": "Equipamento desativado"}

# ========== ORDENS DE SERVIÇO ENDPOINTS ==========
@api_router.get("/ordens-servico", response_model=List[OSResponse])
async def list_os(
    status: Optional[str] = None,
    tipo: Optional[str] = None,
    prioridade: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)
    
    if status:
        query = query.filter(OrdemServico.status == status)
    if tipo:
        query = query.filter(OrdemServico.tipo == tipo)
    if prioridade:
        query = query.filter(OrdemServico.prioridade == prioridade)
    
    ordens = query.order_by(OrdemServico.created_at.desc()).all()
    
    return [build_os_response(o, db) for o in ordens]

@api_router.post("/ordens-servico", response_model=OSResponse)
async def create_os(data: OSCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check plan limit
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    allowed, msg = check_plan_limit(db, org, "os")
    if not allowed:
        raise HTTPException(status_code=402, detail=msg)
    
    # Verify equipment exists
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == data.equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    numero = get_next_os_number(db, str(user.organization_id))
    
    os = OrdemServico(
        numero=numero,
        equipamento_id=data.equipamento_id,
        grupo_id=data.grupo_id or equipamento.grupo_id,
        subgrupo_id=data.subgrupo_id or equipamento.subgrupo_id,
        tipo=data.tipo,
        prioridade=data.prioridade,
        descricao=data.descricao,
        falha_tipo=data.falha_tipo,
        falha_modo=data.falha_modo,
        falha_causa=data.falha_causa,
        solicitante_id=user.id,
        organization_id=user.organization_id
    )
    
    # Check reincidência
    os.reincidente = check_reincidencia(db, str(user.organization_id), data.equipamento_id, data.falha_tipo)
    
    db.add(os)
    db.commit()
    db.refresh(os)
    
    create_audit_log(db, str(user.organization_id), str(user.id), "ordem_servico", str(os.id), "create")
    
    return build_os_response(os, db)

@api_router.put("/ordens-servico/{os_id}", response_model=OSResponse)
async def update_os(os_id: str, data: OSUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    os = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    
    import json as json_lib
    now = datetime.now(timezone.utc)
    
    # Track field changes for audit
    changes = {}
    
    if data.status:
        old_status = os.status
        changes["status"] = {"de": old_status.value, "para": data.status.value}
        os.status = data.status
        
        # Handle status transitions
        if data.status == StatusOS.EM_ATENDIMENTO and old_status == StatusOS.ABERTA:
            os.inicio_atendimento = now
            os.tempo_resposta = int((now - os.created_at).total_seconds() / 60)
            os.dentro_sla = calculate_sla(os.prioridade, os.tempo_resposta)
            if data.tecnico_id:
                os.tecnico_id = data.tecnico_id
            elif user.role in [UserRole.TECNICO, UserRole.LIDER]:
                os.tecnico_id = user.id
        
        elif data.status == StatusOS.AGUARDANDO_REVISAO:
            os.fim_atendimento = now
            if os.inicio_atendimento:
                os.tempo_reparo = int((now - os.inicio_atendimento).total_seconds() / 60)
            os.tempo_total = int((now - os.created_at).total_seconds() / 60)
            
            # Auto-assign leader as reviewer
            leader = db.query(User).filter(
                User.organization_id == user.organization_id,
                User.role == UserRole.LIDER,
                User.ativo == True
            ).first()
            if leader:
                os.revisor_id = leader.id
                changes["revisor_auto_atribuido"] = leader.nome
            
            # Set 24h review deadline
            os.review_deadline = now + timedelta(hours=24)
        
        elif data.status == StatusOS.REVISADA:
            os.revisado_at = now
            os.revisor_id = user.id
        
        elif data.status == StatusOS.FECHADA:
            os.fechado_at = now
    
    if data.solucao:
        if os.solucao != data.solucao:
            changes["solucao"] = {"de": os.solucao or "", "para": data.solucao}
        os.solucao = data.solucao
    if data.tecnico_id:
        os.tecnico_id = data.tecnico_id
    if data.falha_tipo:
        if os.falha_tipo != data.falha_tipo:
            changes["falha_tipo"] = {"de": os.falha_tipo or "", "para": data.falha_tipo}
        os.falha_tipo = data.falha_tipo
    if data.falha_modo:
        if os.falha_modo != data.falha_modo:
            changes["falha_modo"] = {"de": os.falha_modo or "", "para": data.falha_modo}
        os.falha_modo = data.falha_modo
    if data.falha_causa:
        if os.falha_causa != data.falha_causa:
            changes["falha_causa"] = {"de": os.falha_causa or "", "para": data.falha_causa}
        os.falha_causa = data.falha_causa
    if data.review_notes:
        os.review_notes = data.review_notes
        changes["review_notes"] = data.review_notes
    
    db.commit()
    db.refresh(os)
    
    # Enhanced audit log with field changes
    create_audit_log(
        db, str(user.organization_id), str(user.id), "ordem_servico", str(os.id), "update",
        dados_anteriores=None,
        dados_novos=json_lib.dumps(changes, ensure_ascii=False) if changes else None
    )
    
    return build_os_response(os, db)

@api_router.post("/ordens-servico/auto-approve")
async def auto_approve_expired_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Auto-approve work orders past their 24h review deadline"""
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    now = datetime.now(timezone.utc)
    expired = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO,
        OrdemServico.review_deadline != None,
        OrdemServico.review_deadline < now
    ).all()
    
    count = 0
    for os_item in expired:
        os_item.status = StatusOS.REVISADA
        os_item.revisado_at = now
        os_item.auto_approved = True
        os_item.review_notes = "Auto-aprovada: prazo de revisão de 24h expirado"
        count += 1
        create_audit_log(db, str(user.organization_id), str(user.id), "ordem_servico", str(os_item.id), "auto_approve")
    
    db.commit()
    return {"auto_approved": count, "message": f"{count} OS auto-aprovadas"}

@api_router.get("/ordens-servico/pending-reviews")
async def get_pending_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get work orders pending review for the current user"""
    now = datetime.now(timezone.utc)
    
    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO
    )
    
    # Leaders see OS assigned to them for review
    if user.role == UserRole.LIDER:
        query = query.filter(OrdemServico.revisor_id == user.id)
    elif user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    pending = query.order_by(OrdemServico.review_deadline.asc()).all()
    
    results = []
    for o in pending:
        resp = build_os_response(o, db)
        time_remaining = None
        if o.review_deadline:
            remaining = (o.review_deadline - now).total_seconds()
            time_remaining = max(0, round(remaining / 3600, 1))
        results.append({
            **resp.model_dump(),
            "hours_remaining": time_remaining,
            "is_expired": time_remaining is not None and time_remaining <= 0
        })
    
    return results

@api_router.get("/ordens-servico/{os_id}", response_model=OSResponse)
async def get_os(os_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    os = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    return build_os_response(os, db)

# ========== CUSTOS ENDPOINTS ==========
@api_router.get("/custos", response_model=List[CustoResponse])
async def list_custos(ordem_servico_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(CustoOS).filter(CustoOS.organization_id == user.organization_id)
    if ordem_servico_id:
        query = query.filter(CustoOS.ordem_servico_id == ordem_servico_id)
    custos = query.all()
    return [CustoResponse(
        id=str(c.id), ordem_servico_id=str(c.ordem_servico_id), tipo=c.tipo.value,
        descricao=c.descricao, valor=c.valor, quantidade=c.quantidade,
        organization_id=str(c.organization_id), created_at=c.created_at
    ) for c in custos]

@api_router.post("/custos", response_model=CustoResponse)
async def create_custo(data: CustoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER, UserRole.TECNICO]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Verify OS exists
    os = db.query(OrdemServico).filter(
        OrdemServico.id == data.ordem_servico_id,
        OrdemServico.organization_id == user.organization_id
    ).first()
    if not os:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    
    custo = CustoOS(
        ordem_servico_id=data.ordem_servico_id,
        tipo=data.tipo,
        descricao=data.descricao,
        valor=data.valor,
        quantidade=data.quantidade,
        organization_id=user.organization_id
    )
    db.add(custo)
    db.commit()
    db.refresh(custo)
    
    return CustoResponse(
        id=str(custo.id), ordem_servico_id=str(custo.ordem_servico_id), tipo=custo.tipo.value,
        descricao=custo.descricao, valor=custo.valor, quantidade=custo.quantidade,
        organization_id=str(custo.organization_id), created_at=custo.created_at
    )

# ========== PLANOS PREVENTIVOS ENDPOINTS ==========
@api_router.get("/planos-preventivos", response_model=List[PlanoResponse])
async def list_planos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    planos = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.organization_id == user.organization_id,
        PlanoPreventivo.ativo == True
    ).all()
    return [PlanoResponse(
        id=str(p.id), equipamento_id=str(p.equipamento_id), nome=p.nome,
        descricao=p.descricao, frequencia_dias=p.frequencia_dias,
        ultima_execucao=p.ultima_execucao, proxima_execucao=p.proxima_execucao,
        ativo=p.ativo, organization_id=str(p.organization_id), created_at=p.created_at
    ) for p in planos]

@api_router.post("/planos-preventivos", response_model=PlanoResponse)
async def create_plano(data: PlanoCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    # Verify equipment exists
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == data.equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    proxima = datetime.now(timezone.utc) + timedelta(days=data.frequencia_dias)
    
    plano = PlanoPreventivo(
        equipamento_id=data.equipamento_id,
        nome=data.nome,
        descricao=data.descricao,
        frequencia_dias=data.frequencia_dias,
        proxima_execucao=proxima,
        organization_id=user.organization_id
    )
    db.add(plano)
    db.commit()
    db.refresh(plano)
    
    return PlanoResponse(
        id=str(plano.id), equipamento_id=str(plano.equipamento_id), nome=plano.nome,
        descricao=plano.descricao, frequencia_dias=plano.frequencia_dias,
        ultima_execucao=plano.ultima_execucao, proxima_execucao=plano.proxima_execucao,
        ativo=plano.ativo, organization_id=str(plano.organization_id), created_at=plano.created_at
    )

@api_router.post("/planos-preventivos/{plano_id}/executar")
async def executar_plano(plano_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Gera uma OS preventiva a partir do plano"""
    plano = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.id == plano_id,
        PlanoPreventivo.organization_id == user.organization_id
    ).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    equipamento = db.query(Equipamento).filter(Equipamento.id == plano.equipamento_id).first()
    
    numero = get_next_os_number(db, str(user.organization_id))
    
    os = OrdemServico(
        numero=numero,
        equipamento_id=plano.equipamento_id,
        grupo_id=equipamento.grupo_id if equipamento else None,
        subgrupo_id=equipamento.subgrupo_id if equipamento else None,
        tipo=TipoOS.PREVENTIVA,
        prioridade=PrioridadeOS.MEDIA,
        descricao=f"Manutenção preventiva: {plano.nome}",
        solicitante_id=user.id,
        organization_id=user.organization_id
    )
    db.add(os)
    
    # Update plano
    now = datetime.now(timezone.utc)
    plano.ultima_execucao = now
    plano.proxima_execucao = now + timedelta(days=plano.frequencia_dias)
    
    db.commit()
    db.refresh(os)
    
    return {"message": "OS preventiva criada", "os_id": str(os.id), "numero": os.numero}

# ========== DASHBOARD / INDICADORES ==========
@api_router.get("/dashboard/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_id = user.organization_id
    now = datetime.now(timezone.utc)
    first_day_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Total OS do mês
    total_os_mes = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= first_day_month
    ).count()
    
    # OS abertas
    os_abertas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO])
    ).count()
    
    # OS atrasadas (fora do SLA)
    os_atrasadas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.dentro_sla == False
    ).count()
    
    # MTTR (Mean Time To Repair) - média em horas
    os_com_reparo = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tempo_reparo != None
    ).all()
    mttr = sum(o.tempo_reparo for o in os_com_reparo) / len(os_com_reparo) / 60 if os_com_reparo else 0
    
    # MTBF (Mean Time Between Failures) - simplificado
    # Conta dias desde primeira OS até hoje / número de falhas
    first_os = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).order_by(OrdemServico.created_at).first()
    
    total_corretivas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).count()
    
    if first_os and total_corretivas > 1:
        days_operating = (now - first_os.created_at).days or 1
        mtbf = (days_operating * 24) / total_corretivas
    else:
        mtbf = 720  # Default 30 dias em horas
    
    # Disponibilidade = (MTBF / (MTBF + MTTR)) * 100
    disponibilidade = (mtbf / (mtbf + mttr) * 100) if (mtbf + mttr) > 0 else 100
    
    # Custos do mês
    custos_mes = db.query(CustoOS).join(OrdemServico).filter(
        CustoOS.organization_id == org_id,
        OrdemServico.created_at >= first_day_month
    ).all()
    custo_total_mes = sum(c.valor * c.quantidade for c in custos_mes)
    
    # Custo de máquina parada do mês
    os_mes_com_tempo = db.query(OrdemServico).join(Equipamento).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= first_day_month,
        OrdemServico.tempo_total != None
    ).all()
    
    custo_parada = 0
    for o in os_mes_com_tempo:
        equip = db.query(Equipamento).filter(Equipamento.id == o.equipamento_id).first()
        if equip:
            horas_parada = o.tempo_total / 60
            custo_parada += horas_parada * equip.valor_hora
    
    # Preventiva vs Corretiva
    preventivas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= first_day_month,
        OrdemServico.tipo == TipoOS.PREVENTIVA
    ).count()
    corretivas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.created_at >= first_day_month,
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).count()
    
    # Top equipamentos por falhas
    from sqlalchemy import func
    top_falhas = db.query(
        OrdemServico.equipamento_id,
        func.count(OrdemServico.id).label('total')
    ).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).group_by(OrdemServico.equipamento_id).order_by(func.count(OrdemServico.id).desc()).limit(5).all()
    
    top_equipamentos_falhas = []
    for eq_id, total in top_falhas:
        equip = db.query(Equipamento).filter(Equipamento.id == eq_id).first()
        if equip:
            top_equipamentos_falhas.append({"nome": equip.nome, "codigo": equip.codigo, "total": total})
    
    # Top equipamentos por custo
    top_custos = db.query(
        OrdemServico.equipamento_id,
        func.sum(CustoOS.valor * CustoOS.quantidade).label('total')
    ).join(CustoOS).filter(
        OrdemServico.organization_id == org_id
    ).group_by(OrdemServico.equipamento_id).order_by(func.sum(CustoOS.valor * CustoOS.quantidade).desc()).limit(5).all()
    
    top_equipamentos_custos = []
    for eq_id, total in top_custos:
        equip = db.query(Equipamento).filter(Equipamento.id == eq_id).first()
        if equip:
            top_equipamentos_custos.append({"nome": equip.nome, "codigo": equip.codigo, "total": float(total or 0)})
    
    # Average response time
    os_com_resposta = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tempo_resposta != None
    ).all()
    avg_tempo_resposta = sum(o.tempo_resposta for o in os_com_resposta) / len(os_com_resposta) if os_com_resposta else 0
    
    # Top equipamentos por downtime (tempo parado)
    top_downtime_raw = db.query(
        OrdemServico.equipamento_id,
        func.sum(OrdemServico.tempo_total).label('total_downtime')
    ).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tempo_total != None
    ).group_by(OrdemServico.equipamento_id).order_by(func.sum(OrdemServico.tempo_total).desc()).limit(5).all()
    
    top_equipamentos_downtime = []
    for eq_id, total_dt in top_downtime_raw:
        equip = db.query(Equipamento).filter(Equipamento.id == eq_id).first()
        if equip:
            hours = round((total_dt or 0) / 60, 1)
            top_equipamentos_downtime.append({"nome": equip.nome, "codigo": equip.codigo, "total_horas": hours})
    
    return DashboardKPIs(
        total_os_mes=total_os_mes,
        os_abertas=os_abertas,
        os_atrasadas=os_atrasadas,
        mttr=round(mttr, 2),
        mtbf=round(mtbf, 2),
        disponibilidade=round(disponibilidade, 2),
        custo_total_mes=round(custo_total_mes, 2),
        custo_parada_mes=round(custo_parada, 2),
        avg_tempo_resposta=round(avg_tempo_resposta, 1),
        preventiva_vs_corretiva={"preventiva": preventivas, "corretiva": corretivas},
        top_equipamentos_falhas=top_equipamentos_falhas,
        top_equipamentos_custos=top_equipamentos_custos,
        top_equipamentos_downtime=top_equipamentos_downtime
    )

@api_router.get("/dashboard/backlog")
async def get_backlog(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna backlog de OS"""
    org_id = user.organization_id
    
    abertas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.ABERTA
    ).count()
    
    em_atendimento = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.EM_ATENDIMENTO
    ).count()
    
    aguardando_revisao = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO
    ).count()
    
    atrasadas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.dentro_sla == False,
        OrdemServico.status.in_([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO])
    ).count()
    
    return {
        "abertas": abertas,
        "em_atendimento": em_atendimento,
        "aguardando_revisao": aguardando_revisao,
        "atrasadas": atrasadas,
        "total_pendentes": abertas + em_atendimento + aguardando_revisao
    }

@api_router.get("/equipamentos/{equipamento_id}/historico")
async def get_equipamento_historico(equipamento_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Timeline completa de um equipamento"""
    equipamento = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()
    if not equipamento:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")
    
    # OS do equipamento
    ordens = db.query(OrdemServico).filter(
        OrdemServico.equipamento_id == equipamento_id
    ).order_by(OrdemServico.created_at.desc()).all()
    
    # Custos totais
    total_custos = 0
    for o in ordens:
        custos = db.query(CustoOS).filter(CustoOS.ordem_servico_id == o.id).all()
        total_custos += sum(c.valor * c.quantidade for c in custos)
    
    # Tempo total parado
    tempo_total_parado = sum(o.tempo_total or 0 for o in ordens) / 60  # em horas
    custo_parada_total = tempo_total_parado * equipamento.valor_hora
    
    return {
        "equipamento": {
            "id": str(equipamento.id),
            "codigo": equipamento.codigo,
            "nome": equipamento.nome,
            "valor_hora": equipamento.valor_hora
        },
        "estatisticas": {
            "total_os": len(ordens),
            "corretivas": len([o for o in ordens if o.tipo == TipoOS.CORRETIVA]),
            "preventivas": len([o for o in ordens if o.tipo == TipoOS.PREVENTIVA]),
            "custo_total": round(total_custos, 2),
            "custo_parada_total": round(custo_parada_total, 2),
            "tempo_total_parado_horas": round(tempo_total_parado, 2)
        },
        "ordens": [{
            "id": str(o.id),
            "numero": o.numero,
            "tipo": o.tipo.value,
            "status": o.status.value,
            "descricao": o.descricao,
            "custo_parada": round(((o.tempo_total or 0) / 60) * equipamento.valor_hora, 2) if o.tempo_total and equipamento.valor_hora else None,
            "created_at": o.created_at.isoformat()
        } for o in ordens[:20]]
    }

@api_router.get("/auditoria")
async def list_auditoria(
    entidade: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role not in [UserRole.ADMIN, UserRole.LIDER]:
        raise HTTPException(status_code=403, detail="Acesso negado")
    
    query = db.query(AuditoriaLog).filter(AuditoriaLog.organization_id == user.organization_id)
    if entidade:
        query = query.filter(AuditoriaLog.entidade == entidade)
    
    logs = query.order_by(AuditoriaLog.created_at.desc()).limit(limit).all()
    
    return [{
        "id": str(l.id),
        "user_id": str(l.user_id) if l.user_id else None,
        "entidade": l.entidade,
        "entidade_id": str(l.entidade_id),
        "acao": l.acao,
        "dados_novos": l.dados_novos,
        "created_at": l.created_at.isoformat()
    } for l in logs]

# ========== BILLING ENDPOINTS ==========
@api_router.get("/billing/plan")
async def get_billing_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current plan info and usage for the organization"""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.FREE])
    
    usage_percent = {
        "equipamentos": round((usage["equipamentos"] / limits["max_equipamentos"]) * 100, 1) if limits["max_equipamentos"] > 0 else 0,
        "users": round((usage["users"] / limits["max_users"]) * 100, 1) if limits["max_users"] > 0 else 0,
        "os_mes": round((usage["os_mes"] / limits["max_os_mes"]) * 100, 1) if limits["max_os_mes"] > 0 else 0,
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
                "max_equipamentos": info["max_equipamentos"],
                "max_users": info["max_users"],
                "max_os_mes": info["max_os_mes"],
            }
            for plan, info in PLAN_LIMITS.items()
        }
    }

@api_router.post("/billing/checkout")
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
    
    if target_plan == PlanoSaaS.FREE:
        raise HTTPException(status_code=400, detail="Não é possível fazer checkout para o plano Free")
    
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

@api_router.get("/billing/checkout/status/{session_id}")
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

@api_router.post("/webhook/stripe")
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

@api_router.get("/billing/transactions")
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

# ========== SEED DATA ==========
@api_router.post("/seed-demo")
async def seed_demo_data(db: Session = Depends(get_db)):
    """Cria dados de demonstração"""
    # Check if demo org exists
    demo_org = db.query(Organization).filter(Organization.nome == "Empresa Demo").first()
    if demo_org:
        return {"message": "Dados de demonstração já existem", "email": "admin@demo.pcm"}
    
    # Create organization
    org = Organization(
        nome="Empresa Demo",
        cnpj="00.000.000/0001-00",
        plano=PlanoSaaS.PRO,
        limite_equipamentos=100,
        limite_usuarios=50,
        limite_os_mes=500
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    
    # Create users
    admin = User(
        email="admin@demo.pcm",
        password_hash=hash_password("admin123"),
        nome="Administrador Demo",
        role=UserRole.ADMIN,
        organization_id=org.id
    )
    lider = User(
        email="lider@demo.pcm",
        password_hash=hash_password("lider123"),
        nome="Líder Técnico",
        role=UserRole.LIDER,
        organization_id=org.id
    )
    tecnico = User(
        email="tecnico@demo.pcm",
        password_hash=hash_password("tecnico123"),
        nome="Técnico Manutenção",
        role=UserRole.TECNICO,
        organization_id=org.id
    )
    operador = User(
        email="operador@demo.pcm",
        password_hash=hash_password("operador123"),
        nome="Operador Produção",
        role=UserRole.OPERADOR,
        organization_id=org.id
    )
    db.add_all([admin, lider, tecnico, operador])
    db.commit()
    
    # Create grupos
    mecanico = Grupo(nome="Mecânico", descricao="Manutenção mecânica", organization_id=org.id)
    eletrica = Grupo(nome="Elétrica", descricao="Manutenção elétrica", organization_id=org.id)
    automacao = Grupo(nome="TI/Automação", descricao="Automação e sistemas", organization_id=org.id)
    db.add_all([mecanico, eletrica, automacao])
    db.commit()
    db.refresh(mecanico)
    db.refresh(eletrica)
    db.refresh(automacao)
    
    # Create subgrupos
    hidraulica = Subgrupo(nome="Hidráulica", grupo_id=mecanico.id, organization_id=org.id)
    pneumatica = Subgrupo(nome="Pneumática", grupo_id=mecanico.id, organization_id=org.id)
    motores = Subgrupo(nome="Motores", grupo_id=eletrica.id, organization_id=org.id)
    paineis = Subgrupo(nome="Painéis Elétricos", grupo_id=eletrica.id, organization_id=org.id)
    clp = Subgrupo(nome="CLP", grupo_id=automacao.id, organization_id=org.id)
    db.add_all([hidraulica, pneumatica, motores, paineis, clp])
    db.commit()
    db.refresh(hidraulica)
    db.refresh(motores)
    
    # Create equipamentos
    equipamentos_data = [
        {"codigo": "EQ-001", "nome": "Prensa Hidráulica 1", "localizacao": "Setor A", "valor_hora": 500.0, "grupo_id": mecanico.id, "subgrupo_id": hidraulica.id, "criticidade": 5},
        {"codigo": "EQ-002", "nome": "Torno CNC", "localizacao": "Setor B", "valor_hora": 800.0, "grupo_id": automacao.id, "subgrupo_id": clp.id, "criticidade": 5},
        {"codigo": "EQ-003", "nome": "Esteira Transportadora", "localizacao": "Setor C", "valor_hora": 200.0, "grupo_id": eletrica.id, "subgrupo_id": motores.id, "criticidade": 3},
        {"codigo": "EQ-004", "nome": "Compressor de Ar", "localizacao": "Utilidades", "valor_hora": 300.0, "grupo_id": mecanico.id, "subgrupo_id": pneumatica.id, "criticidade": 4},
        {"codigo": "EQ-005", "nome": "Empilhadeira Elétrica", "localizacao": "Logística", "valor_hora": 150.0, "grupo_id": eletrica.id, "subgrupo_id": motores.id, "criticidade": 2},
    ]
    
    equipamentos = []
    for eq_data in equipamentos_data:
        eq = Equipamento(organization_id=org.id, **eq_data)
        db.add(eq)
        equipamentos.append(eq)
    db.commit()
    for eq in equipamentos:
        db.refresh(eq)
    
    # Create some OS
    import random
    tipos_falha = ["Mecânica", "Elétrica", "Hidráulica", "Pneumática", "Software"]
    modos_falha = ["Desgaste", "Quebra", "Vazamento", "Curto-circuito", "Travamento"]
    causas_falha = ["Uso inadequado", "Falta de manutenção", "Vida útil", "Sobrecarga", "Defeito de fábrica"]
    
    for i in range(15):
        eq = random.choice(equipamentos)
        tipo = random.choice([TipoOS.CORRETIVA, TipoOS.CORRETIVA, TipoOS.PREVENTIVA])
        prioridade = random.choice(list(PrioridadeOS))
        status = random.choice([StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO, StatusOS.FECHADA])
        
        os = OrdemServico(
            numero=i + 1,
            equipamento_id=eq.id,
            grupo_id=eq.grupo_id,
            subgrupo_id=eq.subgrupo_id,
            tipo=tipo,
            prioridade=prioridade,
            status=status,
            descricao=f"Manutenção {tipo.value} - {eq.nome}",
            solicitante_id=operador.id,
            organization_id=org.id,
            falha_tipo=random.choice(tipos_falha) if tipo == TipoOS.CORRETIVA else None,
            falha_modo=random.choice(modos_falha) if tipo == TipoOS.CORRETIVA else None,
            falha_causa=random.choice(causas_falha) if tipo == TipoOS.CORRETIVA else None,
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))
        )
        
        if status in [StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO, StatusOS.FECHADA]:
            os.tecnico_id = tecnico.id
            os.inicio_atendimento = os.created_at + timedelta(minutes=random.randint(10, 120))
            os.tempo_resposta = int((os.inicio_atendimento - os.created_at).total_seconds() / 60)
            os.dentro_sla = calculate_sla(prioridade, os.tempo_resposta)
        
        if status in [StatusOS.AGUARDANDO_REVISAO, StatusOS.FECHADA]:
            os.fim_atendimento = os.inicio_atendimento + timedelta(minutes=random.randint(30, 480))
            os.tempo_reparo = int((os.fim_atendimento - os.inicio_atendimento).total_seconds() / 60)
            os.tempo_total = int((os.fim_atendimento - os.created_at).total_seconds() / 60)
            os.solucao = "Problema resolvido com sucesso"
        
        if status == StatusOS.FECHADA:
            os.revisado_at = os.fim_atendimento + timedelta(hours=random.randint(1, 24))
            os.revisor_id = lider.id
            os.fechado_at = os.revisado_at
        
        db.add(os)
    
    db.commit()
    
    # Add some custos
    ordens = db.query(OrdemServico).filter(OrdemServico.organization_id == org.id).all()
    for os in ordens[:10]:
        if random.random() > 0.3:
            custo = CustoOS(
                ordem_servico_id=os.id,
                tipo=random.choice(list(TipoCusto)),
                descricao="Material de manutenção",
                valor=random.uniform(50, 500),
                quantidade=random.randint(1, 5),
                organization_id=org.id
            )
            db.add(custo)
    
    db.commit()
    
    # Create planos preventivos
    for eq in equipamentos[:3]:
        plano = PlanoPreventivo(
            equipamento_id=eq.id,
            nome=f"Preventiva mensal - {eq.nome}",
            descricao="Verificação geral e lubrificação",
            frequencia_dias=30,
            proxima_execucao=datetime.now(timezone.utc) + timedelta(days=random.randint(1, 30)),
            organization_id=org.id
        )
        db.add(plano)
    
    db.commit()
    
    # Write test credentials
    credentials_path = Path("/app/memory/test_credentials.md")
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text("""# Test Credentials - PCM Demo

## Admin
- Email: admin@demo.pcm
- Password: admin123
- Role: admin

## Líder Técnico
- Email: lider@demo.pcm
- Password: lider123
- Role: lider

## Técnico
- Email: tecnico@demo.pcm
- Password: tecnico123
- Role: tecnico

## Operador
- Email: operador@demo.pcm
- Password: operador123
- Role: operador

## Auth Endpoints
- POST /api/auth/login
- POST /api/auth/register
- POST /api/auth/logout
- GET /api/auth/me
- POST /api/auth/refresh
""")
    
    return {"message": "Dados de demonstração criados", "email": "admin@demo.pcm", "password": "admin123"}

# Include router
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "PCM - Sistema de Gestão de Manutenção Industrial", "version": "1.0.0"}

@app.on_event("startup")
async def startup():
    logger.info("Starting PCM application...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down PCM application...")
