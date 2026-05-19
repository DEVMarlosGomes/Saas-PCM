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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# PostgreSQL with SQLAlchemy
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.exc import SQLAlchemyError
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
database_initialized = False

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours for SaaS session
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SMTP configuration (fail-silent email notifications)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@aurix.com.br")

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
    DEMO = "demo"
    ESSENCIAL = "essencial"
    PROFISSIONAL = "profissional"
    AVANCADO = "avancado"
    ENTERPRISE = "enterprise"

# Plan limits & feature flags — 5 planos AURIX
PLAN_LIMITS = {
    PlanoSaaS.DEMO: {
        "label": "Demo", "price": 0.0, "preco_mensal": 0.0,
        "max_equipamentos": 5, "max_users": 3, "max_os_mes": 10,
        "stripe_price_id": None, "cta_tipo": "trial", "destaque": False,
        "relatorios": False, "grupos_subgrupos": False, "aprovacao_setor": False,
        "modulo_preditivo": False, "planos_preventivos": False, "api_iot": False,
        "notificacoes_email": False, "exportacao_pdf": False, "sso": False,
        "dashboard_avancado": False, "kanban": False, "suporte": "none",
    },
    PlanoSaaS.ESSENCIAL: {
        "label": "Essencial", "price": 250.0, "preco_mensal": 250.0,
        "max_equipamentos": 20, "max_users": 10, "max_os_mes": 100,
        "stripe_price_id": "price_essencial_mensal", "cta_tipo": "stripe_checkout", "destaque": False,
        "relatorios": True, "grupos_subgrupos": True, "aprovacao_setor": True,
        "modulo_preditivo": False, "planos_preventivos": False, "api_iot": False,
        "notificacoes_email": True, "exportacao_pdf": False, "sso": False,
        "dashboard_avancado": False, "kanban": False, "suporte": "email",
    },
    PlanoSaaS.PROFISSIONAL: {
        "label": "Profissional", "price": 490.0, "preco_mensal": 490.0,
        "max_equipamentos": 35, "max_users": 45, "max_os_mes": -1,
        "stripe_price_id": "price_profissional_mensal", "cta_tipo": "stripe_checkout", "destaque": True,
        "relatorios": True, "grupos_subgrupos": True, "aprovacao_setor": True,
        "modulo_preditivo": True, "max_equipamentos_preditivo": 10,
        "planos_preventivos": True, "api_iot": True,
        "notificacoes_email": True, "exportacao_pdf": True, "sso": False,
        "dashboard_avancado": True, "kanban": True, "setores_independentes": True,
        "relatorios_custo": True, "suporte": "prioritario",
    },
    PlanoSaaS.AVANCADO: {
        "label": "Avançado", "price": 790.0, "preco_mensal": 790.0,
        "max_equipamentos": 50, "max_users": 100, "max_os_mes": -1,
        "stripe_price_id": "price_avancado_mensal", "cta_tipo": "stripe_checkout", "destaque": False,
        "relatorios": True, "relatorios_personalizados": True, "grupos_subgrupos": True,
        "aprovacao_setor": True, "modulo_preditivo": True, "max_equipamentos_preditivo": 30,
        "planos_preventivos": True, "api_iot": True,
        "notificacoes_email": True, "notificacoes_whatsapp": True,
        "exportacao_pdf": True, "integracoes_basicas": True, "sso": False,
        "dashboard_avancado": True, "kanban": True, "setores_independentes": True,
        "relatorios_custo": True, "analise_pareto": True, "suporte": "prioritario",
    },
    PlanoSaaS.ENTERPRISE: {
        "label": "Enterprise", "price": 1290.0, "preco_mensal": 1290.0,
        "max_equipamentos": -1, "max_users": -1, "max_os_mes": -1,
        "stripe_price_id": None, "cta_tipo": "contato", "destaque": False,
        "relatorios": True, "relatorios_personalizados": True, "grupos_subgrupos": True,
        "aprovacao_setor": True, "modulo_preditivo": True, "max_equipamentos_preditivo": -1,
        "planos_preventivos": True, "api_iot": True,
        "notificacoes_email": True, "notificacoes_whatsapp": True,
        "exportacao_pdf": True, "integracoes_avancadas": True, "sso": True,
        "dashboard_avancado": True, "kanban": True, "setores_independentes": True,
        "relatorios_custo": True, "analise_pareto": True,
        "onboarding_personalizado": True, "sla_customizado": True, "suporte": "dedicado",
    },
}

# ========== MODELS ==========
class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(255), nullable=False)
    cnpj = Column(String(20), unique=True, nullable=True)
    plano = Column(SQLEnum(PlanoSaaS), default=PlanoSaaS.DEMO)
    limite_equipamentos = Column(Integer, default=5)
    limite_usuarios = Column(Integer, default=3)
    limite_os_mes = Column(Integer, default=10)
    ativo = Column(Boolean, default=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(50), default="active")
    api_key = Column(String(64), nullable=True, unique=True)
    plano_trial_expira_em = Column(DateTime(timezone=True), nullable=True)
    contato_enterprise_solicitado = Column(Boolean, default=False)
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
    setor = Column(String(100), nullable=True)    # ex: "MECANICA", "TI", "ELETRICA"
    is_lider = Column(Boolean, default=False)     # True = líder do setor, recebe aprovações
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

class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    destinatario_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tipo = Column(String(50), nullable=False)   # "aprovacao_pendente"|"os_aprovada"|"os_rejeitada"|"sla_expirando"|"os_concluida"
    titulo = Column(String(255), nullable=False)
    mensagem = Column(Text, nullable=False)
    os_id = Column(UUID(as_uuid=True), nullable=True)
    lida = Column(Boolean, default=False)
    criada_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    lida_em = Column(DateTime(timezone=True), nullable=True)


class ConfiguracaoMonitoramento(Base):
    __tablename__ = "configuracoes_monitoramento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    parametro_nome = Column(String(100), nullable=False)
    unidade = Column(String(20), nullable=True)
    threshold_atencao = Column(Float, nullable=False)
    threshold_critico = Column(Float, nullable=False)
    tendencia_janela_dias = Column(Integer, default=7)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LeituraSensor(Base):
    __tablename__ = "leituras_sensor"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    parametro_nome = Column(String(100), nullable=False)
    valor = Column(Float, nullable=False)
    unidade = Column(String(20), nullable=True)
    fonte = Column(String(50), default="manual")
    registrado_por = Column(UUID(as_uuid=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processado = Column(Boolean, default=False)


class AlertaPreditivo(Base):
    __tablename__ = "alertas_preditivos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    equipamento_id = Column(UUID(as_uuid=True), ForeignKey("equipamentos.id"), nullable=False)
    parametro_nome = Column(String(100), nullable=False)
    severidade = Column(String(20), nullable=False)   # "ATENCAO"|"CRITICO"
    valor_atual = Column(Float, nullable=False)
    threshold_violado = Column(Float, nullable=False)
    tendencia = Column(String(20), default="ESTAVEL")  # "ESTAVEL"|"CRESCENTE"|"CRITICA"
    rul_estimado_dias = Column(Integer, nullable=True)
    descricao = Column(Text, nullable=False)
    status = Column(String(20), default="ABERTO")      # "ABERTO"|"OS_GERADA"|"IGNORADO"|"RESOLVIDO"
    os_gerada_id = Column(UUID(as_uuid=True), nullable=True)
    ignorado_por = Column(UUID(as_uuid=True), nullable=True)
    motivo_ignorado = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolvido_em = Column(DateTime(timezone=True), nullable=True)


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
    setor: Optional[str] = None
    is_lider: bool = False
    organization_id: str
    ativo: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nome: str
    role: UserRole = UserRole.OPERADOR
    setor: Optional[str] = None
    is_lider: bool = False

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
def ensure_database_schema():
    global database_initialized

    if database_initialized:
        return

    try:
        Base.metadata.create_all(bind=engine)
        # Schema migrations for new columns
        _migrations = [
            "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS api_key VARCHAR(64) UNIQUE",
            "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS plano_trial_expira_em TIMESTAMPTZ",
            "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS contato_enterprise_solicitado BOOLEAN DEFAULT FALSE",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS setor VARCHAR(100)",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS monitoramento_ativo BOOLEAN DEFAULT FALSE",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS status_saude VARCHAR(20) DEFAULT 'NORMAL'",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS rul_estimado_dias INTEGER",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS mttr_horas FLOAT",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS mtbf_horas FLOAT",
            "ALTER TABLE equipamentos ADD COLUMN IF NOT EXISTS disponibilidade_percent FLOAT",
        ]
        try:
            from sqlalchemy import text as sa_text
            with engine.connect() as conn:
                for sql in _migrations:
                    try:
                        conn.execute(sa_text(sql))
                    except Exception:
                        pass
                conn.commit()
        except Exception as mig_exc:
            logger.warning("Schema migrations skipped: %s", mig_exc)
        database_initialized = True
        logger.info("Database tables created/verified")
    except SQLAlchemyError as exc:
        logger.exception("Database unavailable during schema initialization")
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponivel. Verifique DATABASE_URL/DB_HOST/DB_PORT e a conectividade com o banco."
        ) from exc


def get_db():
    ensure_database_schema()
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

def require_role(*roles: UserRole):
    """FastAPI dependency factory: exige que o usuário tenha um dos perfis informados."""
    async def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Você não tem permissão para esta ação.")
        return current_user
    return dependency


FINANCIAL_FIELDS = {"custo_parada", "valor_pecas", "custo_mao_obra", "custo_total_os"}

def filter_financial_fields(data: dict, user: User, os_setor: str = None) -> dict:
    """
    Remove campos financeiros de acordo com o perfil do usuário.
    ADMIN/SUPER_ADMIN → tudo
    LIDER             → somente do próprio setor
    TECNICO/OPERADOR  → nenhum campo financeiro
    """
    role = user.role
    if role in (UserRole.ADMIN,):
        return data

    if role == UserRole.LIDER:
        # Lider vê campos financeiros só do próprio setor
        if os_setor and user.setor and os_setor.upper() != user.setor.upper():
            return {k: v for k, v in data.items() if k not in FINANCIAL_FIELDS}
        return data

    # TECNICO / OPERADOR — sem campos financeiros
    return {k: v for k, v in data.items() if k not in FINANCIAL_FIELDS}


def criar_notificacao(db: Session, org_id, destinatario_id, tipo: str, titulo: str, mensagem: str, os_id=None):
    """Cria uma notificação in-app para o destinatário."""
    notif = Notificacao(
        org_id=org_id,
        destinatario_id=destinatario_id,
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        os_id=os_id,
    )
    db.add(notif)
    db.commit()


def send_email_notification(db: Session, org: "Organization", destinatario_id, subject: str, html_body: str):
    """Send email if plan includes notificacoes_email and SMTP is configured. Always fails silently."""
    if not PLAN_LIMITS.get(org.plano, {}).get("notificacoes_email"):
        return
    if not SMTP_HOST or not SMTP_USER:
        return
    try:
        dest = db.query(User).filter(User.id == destinatario_id, User.ativo == True).first()
        if not dest:
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AURIX] {subject}"
        msg["From"] = SMTP_FROM
        msg["To"] = dest.email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.sendmail(SMTP_FROM, [dest.email], msg.as_string())
    except Exception as exc:
        logger.warning("Email notification failed: %s", exc)


# ========== MOTOR PREDITIVO ==========

def _linear_slope(values: list) -> float:
    """Slope da regressão linear simples (sem numpy)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den else 0.0


def _zscore(value: float, values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    return (value - mean) / std if std else 0.0


def _estimar_rul(historico: list, threshold_critico: float, slope: float) -> Optional[int]:
    """Dias até o threshold crítico dado o slope diário atual."""
    if not historico or slope <= 0:
        return None
    ultimo = historico[-1]
    if ultimo >= threshold_critico:
        return 0
    dias = (threshold_critico - ultimo) / slope
    return max(0, int(dias))


def processar_leitura_preditiva(db: Session, leitura: LeituraSensor):
    """Analisa uma leitura e cria AlertaPreditivo se necessário."""
    config = db.query(ConfiguracaoMonitoramento).filter(
        ConfiguracaoMonitoramento.equipamento_id == leitura.equipamento_id,
        ConfiguracaoMonitoramento.parametro_nome == leitura.parametro_nome,
        ConfiguracaoMonitoramento.ativo == True,
    ).first()
    if not config:
        return

    janela_inicio = datetime.now(timezone.utc) - timedelta(days=config.tendencia_janela_dias)
    historico_rows = db.query(LeituraSensor).filter(
        LeituraSensor.equipamento_id == leitura.equipamento_id,
        LeituraSensor.parametro_nome == leitura.parametro_nome,
        LeituraSensor.timestamp >= janela_inicio,
    ).order_by(LeituraSensor.timestamp).all()

    historico = [r.valor for r in historico_rows] or [leitura.valor]
    slope = _linear_slope(historico)
    z = _zscore(leitura.valor, historico)

    # Determinar severidade
    if leitura.valor >= config.threshold_critico:
        severidade = "CRITICO"
    elif leitura.valor >= config.threshold_atencao:
        severidade = "ATENCAO"
    elif abs(z) > 3:
        severidade = "ATENCAO"
    else:
        leitura.processado = True
        db.commit()
        return

    # Determinar tendência
    if slope > 0.5:
        tendencia = "CRITICA"
    elif slope > 0.1:
        tendencia = "CRESCENTE"
    else:
        tendencia = "ESTAVEL"

    rul = _estimar_rul(historico, config.threshold_critico, slope)

    # Evitar duplicatas de alerta aberto para o mesmo parâmetro
    existente = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.equipamento_id == leitura.equipamento_id,
        AlertaPreditivo.parametro_nome == leitura.parametro_nome,
        AlertaPreditivo.status == "ABERTO",
    ).first()
    if existente:
        existente.valor_atual = leitura.valor
        existente.severidade = severidade
        existente.tendencia = tendencia
        existente.rul_estimado_dias = rul
        leitura.processado = True
        db.commit()
        return

    equip = db.query(Equipamento).filter(Equipamento.id == leitura.equipamento_id).first()
    descricao = (
        f"{leitura.parametro_nome} = {leitura.valor} {config.unidade or ''} "
        f"(limite {severidade.lower()}: {config.threshold_atencao if severidade == 'ATENCAO' else config.threshold_critico})"
    ).strip()

    alerta = AlertaPreditivo(
        organization_id=leitura.organization_id,
        equipamento_id=leitura.equipamento_id,
        parametro_nome=leitura.parametro_nome,
        severidade=severidade,
        valor_atual=leitura.valor,
        threshold_violado=config.threshold_critico if severidade == "CRITICO" else config.threshold_atencao,
        tendencia=tendencia,
        rul_estimado_dias=rul,
        descricao=descricao,
    )
    db.add(alerta)

    # Atualizar status_saude do equipamento
    if equip:
        if severidade == "CRITICO":
            equip.status_saude = "CRITICO"
        elif getattr(equip, "status_saude", "NORMAL") != "CRITICO":
            equip.status_saude = "ATENCAO"
        if rul is not None:
            equip.rul_estimado_dias = rul

    leitura.processado = True
    db.commit()
    db.refresh(alerta)

    # Notificar admin
    admin = db.query(User).filter(
        User.organization_id == leitura.organization_id,
        User.role == UserRole.ADMIN,
        User.ativo == True,
    ).first()
    org = db.query(Organization).filter(Organization.id == leitura.organization_id).first()
    if admin and org:
        nome_equip = equip.nome if equip else str(leitura.equipamento_id)
        criar_notificacao(
            db, org_id=leitura.organization_id, destinatario_id=admin.id,
            tipo="alerta_preditivo",
            titulo=f"Alerta {severidade}: {nome_equip}",
            mensagem=descricao,
        )
        send_email_notification(
            db, org, admin.id,
            f"Alerta preditivo {severidade} — {nome_equip}",
            f"<p><strong>{descricao}</strong></p>"
            + (f"<p>RUL estimado: {rul} dias</p>" if rul is not None else ""),
        )


def _job_processar_leituras(db: Session):
    """Processa leituras de sensor não processadas (job APScheduler)."""
    leituras = db.query(LeituraSensor).filter(LeituraSensor.processado == False).limit(200).all()
    for l in leituras:
        try:
            processar_leitura_preditiva(db, l)
        except Exception as exc:
            logger.warning("Erro ao processar leitura %s: %s", l.id, exc)


def _job_atualizar_mttr_mtbf(db: Session):
    """Recalcula MTTR/MTBF/disponibilidade de todos os equipamentos."""
    orgs = db.query(Organization).filter(Organization.ativo == True).all()
    for org in orgs:
        equips = db.query(Equipamento).filter(
            Equipamento.organization_id == org.id,
            Equipamento.ativo == True,
        ).all()
        for equip in equips:
            os_list = db.query(OrdemServico).filter(
                OrdemServico.organization_id == org.id,
                OrdemServico.equipamento_id == equip.id,
                OrdemServico.tipo == TipoOS.CORRETIVA,
                OrdemServico.status == StatusOS.FECHADA,
            ).all()
            if len(os_list) >= 2:
                tempos_reparo = [o.tempo_reparo for o in os_list if o.tempo_reparo]
                if tempos_reparo:
                    mttr_min = sum(tempos_reparo) / len(tempos_reparo)
                    equip.mttr_horas = round(mttr_min / 60, 2)
                # MTBF = (total tempo operação) / num_falhas
                datas = sorted([o.created_at for o in os_list if o.created_at])
                if len(datas) >= 2:
                    span_h = (datas[-1] - datas[0]).total_seconds() / 3600
                    equip.mtbf_horas = round(span_h / len(os_list), 2)
                    total_parada = sum((o.tempo_total or 0) for o in os_list) / 60
                    equip.disponibilidade_percent = round(
                        max(0.0, (span_h - total_parada) / span_h * 100) if span_h else 100.0, 1
                    )
    db.commit()


def _job_gerar_os_preventivas(db: Session):
    """Gera OS preventivas para planos com proxima_execucao dentro de antecedencia_alerta_dias."""
    now = datetime.now(timezone.utc)
    planos = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.ativo == True,
        PlanoPreventivo.proxima_execucao != None,
    ).all()
    for plano in planos:
        prazo = plano.proxima_execucao - timedelta(days=7)
        if now >= prazo:
            # Verificar se já existe OS preventiva para este plano recente
            existe = db.query(OrdemServico).filter(
                OrdemServico.organization_id == plano.organization_id,
                OrdemServico.equipamento_id == plano.equipamento_id,
                OrdemServico.tipo == TipoOS.PREVENTIVA,
                OrdemServico.created_at >= now - timedelta(days=7),
            ).first()
            if not existe:
                try:
                    num = get_next_os_number(db, plano.organization_id)
                    equip = db.query(Equipamento).filter(Equipamento.id == plano.equipamento_id).first()
                    os_prev = OrdemServico(
                        numero=num,
                        organization_id=plano.organization_id,
                        equipamento_id=plano.equipamento_id,
                        tipo=TipoOS.PREVENTIVA,
                        prioridade=PrioridadeOS.MEDIA,
                        status=StatusOS.ABERTA,
                        descricao=f"Manutenção preventiva — {plano.nome}",
                        solicitante_id=db.query(User).filter(
                            User.organization_id == plano.organization_id,
                            User.role == UserRole.ADMIN,
                        ).first().id,
                    )
                    db.add(os_prev)
                    db.commit()
                    logger.info("OS preventiva gerada: %s", num)
                except Exception as exc:
                    logger.warning("Erro ao gerar OS preventiva: %s", exc)


def _job_auto_aprovar_sla(db: Session):
    """Auto-aprova OS em aguardando_revisao com review_deadline expirado."""
    now = datetime.now(timezone.utc)
    pendentes = db.query(OrdemServico).filter(
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO,
        OrdemServico.review_deadline != None,
        OrdemServico.review_deadline < now,
    ).all()
    for os in pendentes:
        os.status = StatusOS.REVISADA
        os.revisado_at = now
        os.auto_approved = True
        criar_notificacao(
            db, org_id=os.organization_id, destinatario_id=os.solicitante_id,
            tipo="os_revisada",
            titulo=f"OS #{os.numero} auto-aprovada (SLA expirado)",
            mensagem=f"A OS #{os.numero} foi aprovada automaticamente por expiração do prazo de revisão.",
            os_id=os.id,
        )
    if pendentes:
        db.commit()
        logger.info("Auto-aprovadas %d OS por SLA expirado", len(pendentes))


def _make_db_session():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _run_job(fn):
    """Executa um job com sessão de DB dedicada, falha silenciosamente."""
    db = None
    try:
        db = SessionLocal()
        fn(db)
    except Exception as exc:
        logger.warning("Job %s falhou: %s", fn.__name__, exc)
    finally:
        if db:
            db.close()


_GRUPOS_PADRAO = {
    "MECANICA": ["Manutenção Preventiva", "Manutenção Corretiva", "Manutenção Preditiva", "Utilidades"],
    "TI": ["Infraestrutura", "Sistemas", "Conectividade", "Segurança"],
    "ELETRICA": ["Alta Tensão", "Automação/CLP", "Instrumentação", "Utilidades"],
}

def seed_grupos_padrao(db: Session, org_id):
    """Cria grupos e subgrupos padrão por setor para uma nova organização."""
    for setor, subgrupos in _GRUPOS_PADRAO.items():
        grp = Grupo(organization_id=org_id, nome=setor, descricao=f"Grupo padrão {setor}")
        db.add(grp)
        db.flush()
        for sg_nome in subgrupos:
            db.add(Subgrupo(organization_id=org_id, grupo_id=grp.id, nome=sg_nome))
    db.commit()


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
    Returns (allowed: bool, message: str). -1 = unlimited."""
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])

    limit_map = {
        "equipamentos": ("max_equipamentos", usage["equipamentos"]),
        "users": ("max_users", usage["users"]),
        "os": ("max_os_mes", usage["os_mes"]),
    }

    if resource not in limit_map:
        return True, ""

    limit_key, current = limit_map[resource]
    max_val = limits[limit_key]

    if max_val == -1:
        return True, ""

    if current >= max_val:
        plan_label = limits["label"]
        return False, (
            f"Limite do plano {plan_label} atingido: {current}/{max_val} {resource}. "
            f"Faça upgrade para continuar."
        )

    return True, ""

def build_os_response(o, db: Session, user=None) -> OSResponse:
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

    # Apply financial visibility: only ADMIN sees custo_parada
    if user is not None and user.role not in (UserRole.ADMIN,):
        custo_parada = None

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
app = FastAPI(title="AURIX — Tecnologia para a Gestão Industrial", version="2.0.0")
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
    org = Organization(
        nome=org_nome,
        plano_trial_expira_em=datetime.now(timezone.utc) + timedelta(days=10),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    seed_grupos_padrao(db, org.id)
    
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
        "setor": user.setor,
        "is_lider": user.is_lider or False,
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "access_token": access_token,
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logout realizado com sucesso"}

@api_router.get("/auth/me")
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
        "organization_id": str(user.organization_id),
        "ativo": user.ativo,
        "org_plano": org.plano.value if org else "demo",
        "features": features,
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
        setor=u.setor, is_lider=u.is_lider or False,
        organization_id=str(u.organization_id), ativo=u.ativo, created_at=u.created_at,
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
        setor=data.setor,
        is_lider=data.is_lider,
        organization_id=user.organization_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        id=str(new_user.id), email=new_user.email, nome=new_user.nome, role=new_user.role.value,
        setor=new_user.setor, is_lider=new_user.is_lider or False,
        organization_id=str(new_user.organization_id), ativo=new_user.ativo, created_at=new_user.created_at,
    )

class UserUpdate(BaseModel):
    nome: Optional[str] = None
    role: Optional[UserRole] = None
    setor: Optional[str] = None
    is_lider: Optional[bool] = None
    ativo: Optional[bool] = None

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode editar usuários")
    
    target_user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == user.organization_id
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Prevent admin from demoting themselves
    if str(target_user.id) == str(user.id) and data.role and data.role != UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="Você não pode alterar seu próprio cargo de admin")
    
    if data.nome is not None:
        target_user.nome = data.nome
    if data.role is not None:
        target_user.role = data.role
    if data.setor is not None:
        target_user.setor = data.setor
    if data.is_lider is not None:
        target_user.is_lider = data.is_lider
    if data.ativo is not None:
        if str(target_user.id) == str(user.id) and not data.ativo:
            raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta")
        target_user.ativo = data.ativo

    db.commit()
    db.refresh(target_user)
    create_audit_log(db, str(user.organization_id), str(user.id), "user", str(target_user.id), "update")

    return UserResponse(
        id=str(target_user.id), email=target_user.email, nome=target_user.nome, role=target_user.role.value,
        setor=target_user.setor, is_lider=target_user.is_lider or False,
        organization_id=str(target_user.organization_id), ativo=target_user.ativo, created_at=target_user.created_at,
    )

@api_router.delete("/users/{user_id}")
async def deactivate_user(user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode desativar usuários")
    
    if str(user_id) == str(user.id):
        raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta")
    
    target_user = db.query(User).filter(
        User.id == user_id,
        User.organization_id == user.organization_id
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    target_user.ativo = False
    db.commit()
    
    create_audit_log(db, str(user.organization_id), str(user.id), "user", str(target_user.id), "deactivate")
    
    return {"message": "Usuário desativado com sucesso"}

# ========== ORGANIZATION SETTINGS ==========
class OrganizationUpdate(BaseModel):
    nome: Optional[str] = None
    cnpj: Optional[str] = None

@api_router.get("/organization")
async def get_organization(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current organization details"""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    usage = get_org_usage(db, org.id)
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])

    feature_labels = {
        "relatorios": "Relatórios avançados",
        "dashboard_avancado": "Dashboard avançado",
        "kanban": "Kanban de OS",
        "modulo_preditivo": "Análise preditiva",
        "planos_preventivos": "Manutenção preventiva",
        "aprovacao_setor": "Aprovação por setor",
        "notificacoes_email": "Notificações por e-mail",
        "exportacao_pdf": "Exportação PDF",
        "api_iot": "API IoT / Webhooks",
        "sso": "SSO / Login único",
        "grupos_subgrupos": "Grupos e subgrupos",
    }
    features_list = [label for key, label in feature_labels.items() if limits.get(key)]

    return {
        "id": str(org.id),
        "nome": org.nome,
        "cnpj": org.cnpj,
        "plano": org.plano.value,
        "subscription_status": org.subscription_status,
        "ativo": org.ativo,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "limits": {
            "max_equipamentos": limits["max_equipamentos"],
            "max_users": limits["max_users"],
            "max_os_mes": limits["max_os_mes"],
        },
        "usage": usage,
        "features": features_list,
        "plan_features": limits,
        "has_api_key": bool(org.api_key),
        "api_key_preview": (org.api_key[:12] + "..." if org.api_key else None),
    }

@api_router.put("/organization")
async def update_organization(data: OrganizationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update organization details (admin only)"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode editar a organização")
    
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    if data.nome:
        org.nome = data.nome
    if data.cnpj is not None:
        org.cnpj = data.cnpj
    
    db.commit()
    db.refresh(org)
    
    create_audit_log(db, str(user.organization_id), str(user.id), "organization", str(org.id), "update")
    
    return {"message": "Organização atualizada", "nome": org.nome}

# ========== API KEY MANAGEMENT ==========

@api_router.post("/organization/generate-api-key")
async def generate_api_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate (or regenerate) API key for the organization. Admin only."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode gerenciar API keys")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    _require_feature(org, "api_iot")
    new_key = "aurix_" + secrets.token_hex(28)
    org.api_key = new_key
    db.commit()
    create_audit_log(db, str(user.organization_id), str(user.id), "organization", str(org.id), "generate_api_key")
    return {"api_key": new_key}


@api_router.delete("/organization/api-key")
async def revoke_api_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke the organization's API key. Admin only."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas admin pode gerenciar API keys")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    org.api_key = None
    db.commit()
    create_audit_log(db, str(user.organization_id), str(user.id), "organization", str(org.id), "revoke_api_key")
    return {"message": "API key revogada"}


# ========== IoT TELEMETRIA ==========

class IoTTelemetria(BaseModel):
    equipamento_id: str
    sensor: str
    valor: float
    unidade: Optional[str] = None
    timestamp: Optional[datetime] = None
    alerta: Optional[bool] = False
    mensagem: Optional[str] = None


async def _get_iot_org(request: Request, db: Session = Depends(get_db)) -> Organization:
    """Authenticate IoT requests via X-API-Key header."""
    api_key_header = request.headers.get("X-API-Key")
    if not api_key_header:
        raise HTTPException(status_code=401, detail="X-API-Key header obrigatório")
    org = db.query(Organization).filter(
        Organization.api_key == api_key_header,
        Organization.ativo == True,
    ).first()
    if not org:
        raise HTTPException(status_code=401, detail="API key inválida ou organização inativa")
    _require_feature(org, "api_iot")
    return org


@api_router.post("/iot/telemetria", status_code=201)
async def receive_telemetria(
    payload: IoTTelemetria,
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive sensor telemetry from IoT devices. Authenticated via X-API-Key."""
    org = await _get_iot_org(request, db)

    equip = db.query(Equipamento).filter(
        Equipamento.id == payload.equipamento_id,
        Equipamento.organization_id == org.id,
    ).first()
    if not equip:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    result = {
        "recebido": True,
        "equipamento": equip.nome,
        "sensor": payload.sensor,
        "valor": payload.valor,
        "timestamp": (payload.timestamp or datetime.now(timezone.utc)).isoformat(),
        "os_criada": False,
    }

    # Auto-create corrective OS on alert
    if payload.alerta:
        num = get_next_os_number(db, org.id)
        desc = payload.mensagem or f"Alerta IoT: {payload.sensor} = {payload.valor} {payload.unidade or ''}".strip()
        os_alert = OrdemServico(
            numero=num,
            organization_id=org.id,
            equipamento_id=equip.id,
            tipo=TipoOS.CORRETIVA,
            prioridade=PrioridadeOS.ALTA,
            status=StatusOS.ABERTA,
            descricao=desc,
            falha_tipo="iot_alert",
            reincidente=check_reincidencia(db, str(org.id), payload.equipamento_id, "iot_alert"),
        )
        db.add(os_alert)
        db.commit()
        db.refresh(os_alert)
        result["os_criada"] = True
        result["os_numero"] = os_alert.numero

        # Notify admin
        admin = db.query(User).filter(
            User.organization_id == org.id,
            User.role == UserRole.ADMIN,
            User.ativo == True,
        ).first()
        if admin:
            criar_notificacao(
                db, org_id=org.id, destinatario_id=admin.id,
                tipo="iot_alert",
                titulo=f"Alerta IoT: {equip.nome}",
                mensagem=desc,
                os_id=os_alert.id,
            )
            send_email_notification(
                db, org, admin.id,
                f"Alerta IoT — {equip.nome}",
                f"<p><strong>Sensor:</strong> {payload.sensor}<br><strong>Valor:</strong> {payload.valor} {payload.unidade or ''}<br>{desc}</p>",
            )

    return result


# ========== PASSWORD RESET ==========
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

@api_router.post("/auth/change-password")
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
    
    return [build_os_response(o, db, user=user) for o in ordens]

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

    return build_os_response(os, db, user=user)

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
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
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
                criar_notificacao(
                    db, org_id=os.organization_id, destinatario_id=leader.id,
                    tipo="revisao_pendente",
                    titulo=f"OS #{os.numero} aguarda sua revisão",
                    mensagem=f"A OS #{os.numero} foi concluída e aguarda revisão. Prazo: 24 horas.",
                    os_id=os.id,
                )
                if org:
                    send_email_notification(
                        db, org, leader.id,
                        f"OS #{os.numero} aguarda sua revisão",
                        f"<p>A OS <strong>#{os.numero}</strong> foi concluída e aguarda sua revisão.</p><p>Prazo: 24 horas.</p>",
                    )

            # Set 24h review deadline
            os.review_deadline = now + timedelta(hours=24)

        elif data.status == StatusOS.REVISADA:
            os.revisado_at = now
            os.revisor_id = user.id
            criar_notificacao(
                db, org_id=os.organization_id, destinatario_id=os.solicitante_id,
                tipo="os_revisada",
                titulo=f"OS #{os.numero} revisada",
                mensagem=f"Sua ordem de serviço #{os.numero} foi revisada e está sendo encerrada.",
                os_id=os.id,
            )
            if org:
                send_email_notification(
                    db, org, os.solicitante_id,
                    f"OS #{os.numero} revisada",
                    f"<p>Sua ordem de serviço <strong>#{os.numero}</strong> foi revisada e está sendo encerrada.</p>",
                )

        elif data.status == StatusOS.FECHADA:
            os.fechado_at = now
            criar_notificacao(
                db, org_id=os.organization_id, destinatario_id=os.solicitante_id,
                tipo="os_fechada",
                titulo=f"OS #{os.numero} encerrada",
                mensagem=f"Sua ordem de serviço #{os.numero} foi oficialmente encerrada.",
                os_id=os.id,
            )
            if org:
                send_email_notification(
                    db, org, os.solicitante_id,
                    f"OS #{os.numero} encerrada",
                    f"<p>Sua ordem de serviço <strong>#{os.numero}</strong> foi oficialmente encerrada.</p>",
                )
    
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
    
    return build_os_response(os, db, user=user)

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
        resp = build_os_response(o, db, user=user)
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
    return build_os_response(os, db, user=user)

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
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "planos_preventivos")
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
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "planos_preventivos")
    
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

# ========== NOTIFICAÇÕES ENDPOINTS ==========
@api_router.get("/notificacoes")
async def list_notificacoes(
    apenas_nao_lidas: bool = False,
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
        Notificacao.org_id == user.organization_id,
    )
    if apenas_nao_lidas:
        query = query.filter(Notificacao.lida == False)
    notifs = query.order_by(Notificacao.criada_em.desc()).limit(limit).all()
    return [
        {
            "id": str(n.id),
            "tipo": n.tipo,
            "titulo": n.titulo,
            "mensagem": n.mensagem,
            "os_id": str(n.os_id) if n.os_id else None,
            "lida": n.lida,
            "criada_em": n.criada_em.isoformat(),
            "lida_em": n.lida_em.isoformat() if n.lida_em else None,
        }
        for n in notifs
    ]


@api_router.get("/notificacoes/count")
async def count_nao_lidas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
        Notificacao.org_id == user.organization_id,
        Notificacao.lida == False,
    ).count()
    return {"nao_lidas": count}


@api_router.post("/notificacoes/{notif_id}/ler")
async def marcar_lida(notif_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.query(Notificacao).filter(
        Notificacao.id == notif_id,
        Notificacao.destinatario_id == user.id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    notif.lida = True
    notif.lida_em = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@api_router.post("/notificacoes/ler-todas")
async def marcar_todas_lidas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notificacao).filter(
        Notificacao.destinatario_id == user.id,
        Notificacao.org_id == user.organization_id,
        Notificacao.lida == False,
    ).update({"lida": True, "lida_em": datetime.now(timezone.utc)})
    db.commit()
    return {"ok": True}


# ========== BILLING ENDPOINTS ==========
@api_router.get("/billing/plan")
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

@api_router.get("/billing/portal")
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

@api_router.post("/billing/cancelar")
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

@api_router.get("/confiabilidade")
async def get_confiabilidade(
    t: float = 24.0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calcula indicadores de confiabilidade por equipamento:
    - λ (lambda) = falhas / tempo_operacao (taxa de falha)
    - R(t) = e^(-λ*t) (confiabilidade exponencial)
    - Risco = (1 - R(t)) * criticidade_equipamento (probabilidade × impacto)
    - Alertas automáticos por nível de risco

    Query param 't' = horizonte de tempo em horas para projeção (default: 24h)
    """
    from sqlalchemy import func

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")

    org_id = user.organization_id

    # Buscar todos equipamentos ativos
    equipamentos = db.query(Equipamento).filter(
        Equipamento.organization_id == org_id,
        Equipamento.ativo == True
    ).all()

    if not equipamentos:
        return {
            "horizonte_horas": t,
            "resumo": {"total_equipamentos": 0, "alertas_criticos": 0, "alertas_atencao": 0, "confiabilidade_media": 100.0, "lambda_medio": 0.0},
            "equipamentos": [],
            "alertas": []
        }

    now = datetime.now(timezone.utc)

    # Primeira OS corretiva global (para calcular janela de operação)
    first_os_global = db.query(OrdemServico).filter(
        OrdemServico.organization_id == org_id,
        OrdemServico.tipo == TipoOS.CORRETIVA
    ).order_by(OrdemServico.created_at).first()

    resultados = []
    alertas = []

    for equip in equipamentos:
        # Buscar somente OS corretivas com parada para este equipamento
        os_corretivas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == org_id,
            OrdemServico.equipamento_id == equip.id,
            OrdemServico.tipo == TipoOS.CORRETIVA,
            OrdemServico.status.in_([StatusOS.FECHADA, StatusOS.REVISADA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO])
        ).all()

        falhas = len(os_corretivas)

        # Tempo total parado (minutos → horas)
        tempo_parado_horas = sum(o.tempo_total or 0 for o in os_corretivas) / 60

        # Tempo de operação: desde a criação do equipamento ou primeira OS, até agora, menos tempo parado
        ref_date = equip.created_at or (first_os_global.created_at if first_os_global else now)
        tempo_total_horas = max((now - ref_date).total_seconds() / 3600, 1)  # no mínimo 1h
        tempo_operacao = max(tempo_total_horas - tempo_parado_horas, 1)  # no mínimo 1h

        # λ (lambda) = falhas / tempo_operacao
        lam = falhas / tempo_operacao if tempo_operacao > 0 else 0

        # MTBF = 1/λ (horas)
        mtbf = (1 / lam) if lam > 0 else tempo_operacao

        # R(t) = e^(-λ*t) — confiabilidade no horizonte t
        r_t = math.exp(-lam * t) if lam > 0 else 1.0
        r_t_percent = round(r_t * 100, 2)

        # Probabilidade de falha no horizonte
        prob_falha = 1 - r_t

        # Risco = probabilidade × impacto (criticidade 1-5 normalizada para 0-1)
        impacto_normalizado = equip.criticidade / 5.0
        risco = prob_falha * impacto_normalizado
        risco_percent = round(risco * 100, 2)

        # Custo de risco projetado (probabilidade × custo/hora × horizonte)
        custo_risco = round(prob_falha * equip.valor_hora * t, 2) if equip.valor_hora else 0

        # Classificação de risco
        if risco_percent >= 60:
            nivel_risco = "critico"
        elif risco_percent >= 30:
            nivel_risco = "alto"
        elif risco_percent >= 10:
            nivel_risco = "atencao"
        else:
            nivel_risco = "normal"

        # Classificação de lambda
        if lam >= 0.05:
            lambda_status = "instavel"
        elif lam >= 0.01:
            lambda_status = "atencao"
        else:
            lambda_status = "estavel"

        resultado = {
            "equipamento_id": str(equip.id),
            "codigo": equip.codigo,
            "nome": equip.nome,
            "criticidade": equip.criticidade,
            "valor_hora": equip.valor_hora,
            "falhas": falhas,
            "tempo_operacao_horas": round(tempo_operacao, 2),
            "tempo_parado_horas": round(tempo_parado_horas, 2),
            "lambda": round(lam, 6),
            "lambda_status": lambda_status,
            "mtbf_horas": round(mtbf, 2),
            "confiabilidade_percent": r_t_percent,
            "prob_falha_percent": round(prob_falha * 100, 2),
            "risco_percent": risco_percent,
            "nivel_risco": nivel_risco,
            "custo_risco_projetado": custo_risco,
        }
        resultados.append(resultado)

        # Gerar alertas automáticos
        if nivel_risco == "critico":
            alertas.append({
                "tipo": "critico",
                "equipamento": equip.nome,
                "codigo": equip.codigo,
                "mensagem": f"⚠️ RISCO CRÍTICO: {equip.nome} ({equip.codigo}) — confiabilidade {r_t_percent}% em {t}h. λ={round(lam, 4)} falhas/h. Ação imediata necessária.",
                "lambda": round(lam, 4),
                "confiabilidade": r_t_percent,
                "risco": risco_percent,
            })
        elif nivel_risco == "alto":
            alertas.append({
                "tipo": "alto",
                "equipamento": equip.nome,
                "codigo": equip.codigo,
                "mensagem": f"🔶 RISCO ALTO: {equip.nome} ({equip.codigo}) — confiabilidade {r_t_percent}% em {t}h. Priorizar RCA e preventiva.",
                "lambda": round(lam, 4),
                "confiabilidade": r_t_percent,
                "risco": risco_percent,
            })
        elif nivel_risco == "atencao":
            alertas.append({
                "tipo": "atencao",
                "equipamento": equip.nome,
                "codigo": equip.codigo,
                "mensagem": f"🟡 ATENÇÃO: {equip.nome} ({equip.codigo}) — confiabilidade {r_t_percent}% em {t}h. Monitorar tendência.",
                "lambda": round(lam, 4),
                "confiabilidade": r_t_percent,
                "risco": risco_percent,
            })

    # Ordenar equipamentos por risco (maior primeiro)
    resultados.sort(key=lambda x: x["risco_percent"], reverse=True)
    alertas.sort(key=lambda x: x["risco"], reverse=True)

    # Resumo
    lambdas = [r["lambda"] for r in resultados if r["lambda"] > 0]
    confiabilidades = [r["confiabilidade_percent"] for r in resultados]

    resumo = {
        "total_equipamentos": len(resultados),
        "alertas_criticos": len([a for a in alertas if a["tipo"] == "critico"]),
        "alertas_alto": len([a for a in alertas if a["tipo"] == "alto"]),
        "alertas_atencao": len([a for a in alertas if a["tipo"] == "atencao"]),
        "confiabilidade_media": round(sum(confiabilidades) / len(confiabilidades), 2) if confiabilidades else 100.0,
        "lambda_medio": round(sum(lambdas) / len(lambdas), 6) if lambdas else 0,
        "equipamentos_instáveis": len([r for r in resultados if r["lambda_status"] == "instavel"]),
    }

    return {
        "horizonte_horas": t,
        "resumo": resumo,
        "equipamentos": resultados,
        "alertas": alertas,
    }

@api_router.get("/confiabilidade/{equipamento_id}/curva")
async def get_curva_confiabilidade(
    equipamento_id: str,
    max_t: float = 168.0,
    pontos: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gera a curva de confiabilidade R(t) = e^(-λt) para um equipamento específico.
    Retorna pontos da curva para plotar gráfico.

    - max_t: horizonte máximo em horas (default: 168h = 1 semana)
    - pontos: número de pontos na curva (default: 50)
    """
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")

    equip = db.query(Equipamento).filter(
        Equipamento.id == equipamento_id,
        Equipamento.organization_id == user.organization_id
    ).first()

    if not equip:
        raise HTTPException(status_code=404, detail="Equipamento não encontrado")

    now = datetime.now(timezone.utc)

    # Buscar OS corretivas
    os_corretivas = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.equipamento_id == equip.id,
        OrdemServico.tipo == TipoOS.CORRETIVA,
        OrdemServico.status.in_([StatusOS.FECHADA, StatusOS.REVISADA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO])
    ).all()

    falhas = len(os_corretivas)
    tempo_parado = sum(o.tempo_total or 0 for o in os_corretivas) / 60
    ref_date = equip.created_at or now
    tempo_total = max((now - ref_date).total_seconds() / 3600, 1)
    tempo_operacao = max(tempo_total - tempo_parado, 1)

    lam = falhas / tempo_operacao if tempo_operacao > 0 else 0
    mtbf = (1 / lam) if lam > 0 else tempo_operacao

    # Gerar pontos da curva
    curva = []
    step = max_t / pontos
    for i in range(pontos + 1):
        t_val = round(step * i, 2)
        r_val = math.exp(-lam * t_val) if lam > 0 else 1.0
        curva.append({
            "t": t_val,
            "R_t": round(r_val * 100, 2),
            "prob_falha": round((1 - r_val) * 100, 2),
        })

    return {
        "equipamento": {
            "id": str(equip.id),
            "codigo": equip.codigo,
            "nome": equip.nome,
            "criticidade": equip.criticidade,
        },
        "parametros": {
            "lambda": round(lam, 6),
            "mtbf_horas": round(mtbf, 2),
            "falhas": falhas,
            "tempo_operacao_horas": round(tempo_operacao, 2),
        },
        "curva": curva,
    }

# ========== RELATÓRIOS ==========

def sugerir_upgrade(plano_atual: PlanoSaaS, feature: str) -> str:
    ordem = [PlanoSaaS.DEMO, PlanoSaaS.ESSENCIAL, PlanoSaaS.PROFISSIONAL, PlanoSaaS.AVANCADO, PlanoSaaS.ENTERPRISE]
    idx = ordem.index(plano_atual) if plano_atual in ordem else 0
    for p in ordem[idx + 1:]:
        if PLAN_LIMITS.get(p, {}).get(feature):
            return p.value
    return PlanoSaaS.ENTERPRISE.value


def _require_feature(org: Organization, feature: str):
    plano = org.plano if org else PlanoSaaS.DEMO
    limits = PLAN_LIMITS.get(plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    if not limits.get(feature, False):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "feature_locked",
                "feature": feature,
                "mensagem": f"O recurso '{feature}' não está disponível no plano {limits.get('label', str(plano))}.",
                "plano_atual": plano.value if hasattr(plano, "value") else str(plano),
                "upgrade_sugerido": sugerir_upgrade(plano, feature),
                "url_upgrade": "/billing",
            }
        )


@api_router.get("/relatorios/os")
async def relatorio_os(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    status: Optional[str] = None,
    tipo: Optional[str] = None,
    equipamento_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")

    query = db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id)

    if data_inicio:
        try:
            dt = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at >= dt)
        except ValueError:
            pass
    if data_fim:
        try:
            dt = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at <= dt)
        except ValueError:
            pass
    if status:
        query = query.filter(OrdemServico.status == status)
    if tipo:
        query = query.filter(OrdemServico.tipo == tipo)
    if equipamento_id:
        query = query.filter(OrdemServico.equipamento_id == equipamento_id)

    ordens = query.order_by(OrdemServico.created_at.desc()).all()

    # Enrich with equipment names
    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}
    user_map = {str(u.id): u.nome for u in db.query(User).filter(User.organization_id == user.organization_id).all()}

    rows = []
    for o in ordens:
        rows.append({
            "numero": o.numero,
            "equipamento": eq_map.get(str(o.equipamento_id), "—"),
            "tipo": o.tipo.value,
            "prioridade": o.prioridade.value,
            "status": o.status.value,
            "descricao": o.descricao,
            "solicitante": user_map.get(str(o.solicitante_id), "—"),
            "tecnico": user_map.get(str(o.tecnico_id), "—") if o.tecnico_id else "—",
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "tempo_resposta_min": o.tempo_resposta,
            "tempo_reparo_min": o.tempo_reparo,
            "tempo_total_min": o.tempo_total,
            "dentro_sla": o.dentro_sla,
            "reincidente": o.reincidente,
            "falha_tipo": o.falha_tipo,
        })

    total = len(ordens)
    por_status = {}
    for o in ordens:
        por_status[o.status.value] = por_status.get(o.status.value, 0) + 1
    por_tipo = {}
    for o in ordens:
        por_tipo[o.tipo.value] = por_tipo.get(o.tipo.value, 0) + 1

    fechadas = [o for o in ordens if o.status in (StatusOS.FECHADA, StatusOS.REVISADA)]
    sla_ok = sum(1 for o in fechadas if o.dentro_sla)
    tempos_reparo = [o.tempo_reparo for o in fechadas if o.tempo_reparo]
    media_reparo = round(sum(tempos_reparo) / len(tempos_reparo), 1) if tempos_reparo else None

    return {
        "total": total,
        "por_status": por_status,
        "por_tipo": por_tipo,
        "sla_percent": round(sla_ok / len(fechadas) * 100, 1) if fechadas else None,
        "media_reparo_min": media_reparo,
        "ordens": rows,
    }


@api_router.get("/relatorios/custos")
async def relatorio_custos(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")
    if user.role not in (UserRole.ADMIN,):
        raise HTTPException(status_code=403, detail="Apenas administradores podem acessar relatório financeiro.")

    query = db.query(CustoOS).filter(CustoOS.organization_id == user.organization_id)
    if data_inicio:
        try:
            dt = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            query = query.filter(CustoOS.created_at >= dt)
        except ValueError:
            pass
    if data_fim:
        try:
            dt = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            query = query.filter(CustoOS.created_at <= dt)
        except ValueError:
            pass

    custos = query.all()

    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}
    os_map = {str(o.id): o for o in db.query(OrdemServico).filter(OrdemServico.organization_id == user.organization_id).all()}

    total_geral = sum(c.valor * c.quantidade for c in custos)

    por_tipo: dict = {}
    for c in custos:
        tipo = c.tipo.value
        por_tipo[tipo] = por_tipo.get(tipo, 0) + c.valor * c.quantidade

    por_equipamento: dict = {}
    for c in custos:
        os = os_map.get(str(c.ordem_servico_id))
        if os:
            eq_nome = eq_map.get(str(os.equipamento_id), "Desconhecido")
            por_equipamento[eq_nome] = por_equipamento.get(eq_nome, 0) + c.valor * c.quantidade

    por_equip_sorted = sorted(
        [{"equipamento": k, "total": round(v, 2)} for k, v in por_equipamento.items()],
        key=lambda x: x["total"], reverse=True
    )

    return {
        "total_geral": round(total_geral, 2),
        "por_tipo": {k: round(v, 2) for k, v in por_tipo.items()},
        "por_equipamento": por_equip_sorted,
        "total_registros": len(custos),
    }


@api_router.get("/relatorios/pareto")
async def relatorio_pareto(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")

    query = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.tipo == TipoOS.CORRETIVA,
    )
    if data_inicio:
        try:
            dt = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at >= dt)
        except ValueError:
            pass
    if data_fim:
        try:
            dt = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc)
            query = query.filter(OrdemServico.created_at <= dt)
        except ValueError:
            pass

    ordens = query.all()
    total = len(ordens)

    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}

    por_tipo_falha: dict = {}
    por_equipamento: dict = {}
    por_causa: dict = {}

    for o in ordens:
        if o.falha_tipo:
            por_tipo_falha[o.falha_tipo] = por_tipo_falha.get(o.falha_tipo, 0) + 1
        eq_nome = eq_map.get(str(o.equipamento_id), "Desconhecido")
        por_equipamento[eq_nome] = por_equipamento.get(eq_nome, 0) + 1
        if o.falha_causa:
            por_causa[o.falha_causa] = por_causa.get(o.falha_causa, 0) + 1

    def build_pareto(d: dict):
        items = sorted([{"label": k, "count": v} for k, v in d.items()], key=lambda x: x["count"], reverse=True)
        acc = 0
        for item in items:
            acc += item["count"]
            item["percent"] = round(item["count"] / total * 100, 1) if total else 0
            item["acumulado"] = round(acc / total * 100, 1) if total else 0
        return items

    return {
        "total_corretivas": total,
        "por_tipo_falha": build_pareto(por_tipo_falha),
        "por_equipamento": build_pareto(por_equipamento),
        "por_causa": build_pareto(por_causa),
    }


@api_router.get("/relatorios/preventivos")
async def relatorio_preventivos(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")

    now = datetime.now(timezone.utc)
    planos = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.organization_id == user.organization_id,
        PlanoPreventivo.ativo == True,
    ).all()

    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}

    total = len(planos)
    vencidos = [p for p in planos if p.proxima_execucao and p.proxima_execucao < now]
    proximos_7d = [p for p in planos if p.proxima_execucao and now <= p.proxima_execucao <= now + timedelta(days=7)]
    executados = [p for p in planos if p.ultima_execucao]

    compliance = round(len(executados) / total * 100, 1) if total else 0

    rows = []
    for p in sorted(planos, key=lambda x: (x.proxima_execucao or datetime.max.replace(tzinfo=timezone.utc))):
        dias_atraso = None
        if p.proxima_execucao and p.proxima_execucao < now:
            dias_atraso = (now - p.proxima_execucao).days
        rows.append({
            "id": str(p.id),
            "nome": p.nome,
            "equipamento": eq_map.get(str(p.equipamento_id), "—"),
            "frequencia_dias": p.frequencia_dias,
            "ultima_execucao": p.ultima_execucao.isoformat() if p.ultima_execucao else None,
            "proxima_execucao": p.proxima_execucao.isoformat() if p.proxima_execucao else None,
            "status": "vencido" if dias_atraso is not None else ("proximo" if p in proximos_7d else "ok"),
            "dias_atraso": dias_atraso,
        })

    return {
        "total": total,
        "compliance_percent": compliance,
        "vencidos": len(vencidos),
        "proximos_7d": len(proximos_7d),
        "executados_alguma_vez": len(executados),
        "planos": rows,
    }


@api_router.get("/relatorios/kpis")
async def relatorio_kpis(
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")
    now = datetime.now(timezone.utc)
    dt_inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc) if data_inicio else now - timedelta(days=30)
    dt_fim = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc) if data_fim else now

    os_list = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.created_at >= dt_inicio,
        OrdemServico.created_at <= dt_fim,
        OrdemServico.tipo == TipoOS.CORRETIVA,
        OrdemServico.status == StatusOS.FECHADA,
    ).all()

    tempos_reparo = [o.tempo_reparo for o in os_list if o.tempo_reparo]
    mttr = round(sum(tempos_reparo) / len(tempos_reparo) / 60, 2) if tempos_reparo else 0.0

    equips = {}
    for o in os_list:
        eid = str(o.equipamento_id)
        equips.setdefault(eid, []).append(o)
    mtbf_vals = []
    disp_vals = []
    for eid, os_eq in equips.items():
        if len(os_eq) >= 2:
            datas = sorted([o.created_at for o in os_eq])
            span_h = (datas[-1] - datas[0]).total_seconds() / 3600
            mtbf_vals.append(span_h / len(os_eq))
            parada_h = sum((o.tempo_total or 0) for o in os_eq) / 60
            disp_vals.append(max(0.0, (span_h - parada_h) / span_h * 100) if span_h else 100.0)

    mtbf = round(sum(mtbf_vals) / len(mtbf_vals), 2) if mtbf_vals else 0.0
    disponibilidade = round(sum(disp_vals) / len(disp_vals), 1) if disp_vals else 100.0

    return {
        "periodo": {"inicio": dt_inicio.isoformat(), "fim": dt_fim.isoformat()},
        "mttr_horas": mttr,
        "mtbf_horas": mtbf,
        "disponibilidade_percent": disponibilidade,
        "total_os_corretivas": len(os_list),
        "total_equipamentos_com_falha": len(equips),
    }


@api_router.get("/relatorios/equipamentos")
async def relatorio_equipamentos(
    equipamento_id: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "relatorios")
    now = datetime.now(timezone.utc)
    dt_inicio = datetime.fromisoformat(data_inicio).replace(tzinfo=timezone.utc) if data_inicio else now - timedelta(days=90)
    dt_fim = datetime.fromisoformat(data_fim).replace(tzinfo=timezone.utc) if data_fim else now

    equips_q = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id, Equipamento.ativo == True)
    if equipamento_id:
        equips_q = equips_q.filter(Equipamento.id == equipamento_id)
    equips = equips_q.all()

    resultado = []
    for e in equips:
        os_list = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.equipamento_id == e.id,
            OrdemServico.created_at >= dt_inicio,
            OrdemServico.created_at <= dt_fim,
        ).all()
        corretivas = [o for o in os_list if o.tipo == TipoOS.CORRETIVA]
        tempos = [o.tempo_reparo for o in corretivas if o.tempo_reparo]
        mttr = round(sum(tempos) / len(tempos) / 60, 2) if tempos else None
        resultado.append({
            "id": str(e.id), "codigo": e.codigo, "nome": e.nome,
            "localizacao": e.localizacao, "criticidade": e.criticidade,
            "total_os": len(os_list),
            "os_corretivas": len(corretivas),
            "os_preventivas": len([o for o in os_list if o.tipo == TipoOS.PREVENTIVA]),
            "mttr_horas": mttr,
            "status_saude": getattr(e, "status_saude", "NORMAL"),
            "disponibilidade_percent": getattr(e, "disponibilidade_percent", None),
        })
    return sorted(resultado, key=lambda x: x["os_corretivas"], reverse=True)


# ========== MÓDULO PREDITIVO COMPLETO ==========

class ConfigMonitoramentoCreate(BaseModel):
    equipamento_id: str
    parametro_nome: str
    unidade: Optional[str] = None
    threshold_atencao: float
    threshold_critico: float
    tendencia_janela_dias: int = 7

class LeituraCreate(BaseModel):
    equipamento_id: str
    parametro_nome: str
    valor: float
    unidade: Optional[str] = None
    fonte: str = "manual"
    timestamp: Optional[datetime] = None

class LeiturasBulk(BaseModel):
    leituras: List[LeituraCreate]

class AlertaIgnorar(BaseModel):
    motivo: str


@api_router.post("/preditivo/configuracoes", status_code=201)
async def criar_config_monitoramento(
    data: ConfigMonitoramentoCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    limits = PLAN_LIMITS.get(org.plano, PLAN_LIMITS[PlanoSaaS.DEMO])
    max_pred = limits.get("max_equipamentos_preditivo", 0)
    if max_pred != -1:
        atual = db.query(ConfiguracaoMonitoramento).filter(
            ConfiguracaoMonitoramento.organization_id == user.organization_id,
            ConfiguracaoMonitoramento.ativo == True,
        ).distinct(ConfiguracaoMonitoramento.equipamento_id).count()
        if atual >= max_pred:
            raise HTTPException(status_code=402, detail={
                "code": "limite_atingido",
                "mensagem": f"Limite de {max_pred} equipamentos monitorados atingido no plano {limits.get('label')}.",
                "upgrade_sugerido": sugerir_upgrade(org.plano, "max_equipamentos_preditivo"),
                "url_upgrade": "/billing",
            })
    cfg = ConfiguracaoMonitoramento(
        organization_id=user.organization_id,
        equipamento_id=data.equipamento_id,
        parametro_nome=data.parametro_nome,
        unidade=data.unidade,
        threshold_atencao=data.threshold_atencao,
        threshold_critico=data.threshold_critico,
        tendencia_janela_dias=data.tendencia_janela_dias,
    )
    db.add(cfg)
    equip = db.query(Equipamento).filter(Equipamento.id == data.equipamento_id).first()
    if equip:
        equip.monitoramento_ativo = True
    db.commit()
    db.refresh(cfg)
    return {"id": str(cfg.id), "mensagem": "Monitoramento configurado"}


@api_router.get("/preditivo/configuracoes")
async def listar_configs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    cfgs = db.query(ConfiguracaoMonitoramento).filter(
        ConfiguracaoMonitoramento.organization_id == user.organization_id,
    ).all()
    equips = {str(e.id): e.nome for e in db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id).all()}
    return [{"id": str(c.id), "equipamento_id": str(c.equipamento_id),
             "equipamento_nome": equips.get(str(c.equipamento_id), ""),
             "parametro_nome": c.parametro_nome, "unidade": c.unidade,
             "threshold_atencao": c.threshold_atencao, "threshold_critico": c.threshold_critico,
             "tendencia_janela_dias": c.tendencia_janela_dias, "ativo": c.ativo} for c in cfgs]


@api_router.put("/preditivo/configuracoes/{cfg_id}")
async def atualizar_config(
    cfg_id: str, data: ConfigMonitoramentoCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    cfg = db.query(ConfiguracaoMonitoramento).filter(
        ConfiguracaoMonitoramento.id == cfg_id,
        ConfiguracaoMonitoramento.organization_id == user.organization_id,
    ).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Configuração não encontrada")
    cfg.threshold_atencao = data.threshold_atencao
    cfg.threshold_critico = data.threshold_critico
    cfg.tendencia_janela_dias = data.tendencia_janela_dias
    cfg.unidade = data.unidade
    db.commit()
    return {"mensagem": "Atualizado"}


@api_router.post("/preditivo/leituras", status_code=201)
async def registrar_leitura(
    data: LeituraCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    leitura = LeituraSensor(
        organization_id=user.organization_id,
        equipamento_id=data.equipamento_id,
        parametro_nome=data.parametro_nome,
        valor=data.valor,
        unidade=data.unidade,
        fonte=data.fonte,
        registrado_por=user.id,
        timestamp=data.timestamp or datetime.now(timezone.utc),
    )
    db.add(leitura)
    db.commit()
    db.refresh(leitura)
    processar_leitura_preditiva(db, leitura)
    return {"id": str(leitura.id), "processado": leitura.processado}


@api_router.post("/preditivo/leituras/bulk", status_code=201)
async def registrar_leituras_bulk(
    data: LeiturasBulk,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    criadas = 0
    for item in data.leituras[:100]:  # limite de 100 por batch
        leitura = LeituraSensor(
            organization_id=user.organization_id,
            equipamento_id=item.equipamento_id,
            parametro_nome=item.parametro_nome,
            valor=item.valor,
            unidade=item.unidade,
            fonte=item.fonte or "api_externa",
            registrado_por=user.id,
            timestamp=item.timestamp or datetime.now(timezone.utc),
        )
        db.add(leitura)
        criadas += 1
    db.commit()
    return {"criadas": criadas, "mensagem": "Leituras agendadas para processamento"}


@api_router.get("/preditivo/leituras/{equipamento_id}")
async def historico_leituras(
    equipamento_id: str,
    parametro: Optional[str] = None,
    dias: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    q = db.query(LeituraSensor).filter(
        LeituraSensor.organization_id == user.organization_id,
        LeituraSensor.equipamento_id == equipamento_id,
        LeituraSensor.timestamp >= inicio,
    )
    if parametro:
        q = q.filter(LeituraSensor.parametro_nome == parametro)
    rows = q.order_by(LeituraSensor.timestamp).limit(500).all()
    return [{"id": str(r.id), "parametro_nome": r.parametro_nome, "valor": r.valor,
             "unidade": r.unidade, "fonte": r.fonte,
             "timestamp": r.timestamp.isoformat()} for r in rows]


@api_router.get("/preditivo/alertas")
async def listar_alertas(
    severidade: Optional[str] = None,
    status: Optional[str] = None,
    equipamento_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    q = db.query(AlertaPreditivo).filter(AlertaPreditivo.organization_id == user.organization_id)
    if severidade:
        q = q.filter(AlertaPreditivo.severidade == severidade.upper())
    if status:
        q = q.filter(AlertaPreditivo.status == status.upper())
    else:
        q = q.filter(AlertaPreditivo.status == "ABERTO")
    if equipamento_id:
        q = q.filter(AlertaPreditivo.equipamento_id == equipamento_id)
    alertas = q.order_by(AlertaPreditivo.criado_em.desc()).limit(100).all()
    equips = {str(e.id): e.nome for e in db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id).all()}
    return [{"id": str(a.id), "equipamento_id": str(a.equipamento_id),
             "equipamento_nome": equips.get(str(a.equipamento_id), ""),
             "parametro_nome": a.parametro_nome, "severidade": a.severidade,
             "valor_atual": a.valor_atual, "threshold_violado": a.threshold_violado,
             "tendencia": a.tendencia, "rul_estimado_dias": a.rul_estimado_dias,
             "descricao": a.descricao, "status": a.status,
             "criado_em": a.criado_em.isoformat()} for a in alertas]


@api_router.post("/preditivo/alertas/{alerta_id}/gerar-os")
async def gerar_os_alerta(
    alerta_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alerta = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.id == alerta_id,
        AlertaPreditivo.organization_id == user.organization_id,
    ).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    if alerta.status != "ABERTO":
        raise HTTPException(status_code=400, detail="Alerta já tratado")
    num = get_next_os_number(db, user.organization_id)
    os_new = OrdemServico(
        numero=num,
        organization_id=user.organization_id,
        equipamento_id=alerta.equipamento_id,
        tipo=TipoOS.PREDITIVA,
        prioridade=PrioridadeOS.CRITICA if alerta.severidade == "CRITICO" else PrioridadeOS.ALTA,
        status=StatusOS.ABERTA,
        descricao=alerta.descricao,
        falha_tipo="preditivo",
        solicitante_id=user.id,
    )
    db.add(os_new)
    alerta.status = "OS_GERADA"
    alerta.os_gerada_id = os_new.id
    db.commit()
    return {"os_numero": num, "mensagem": f"OS #{num} criada a partir do alerta"}


@api_router.post("/preditivo/alertas/{alerta_id}/ignorar")
async def ignorar_alerta(
    alerta_id: str, data: AlertaIgnorar,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(data.motivo.strip()) < 10:
        raise HTTPException(status_code=400, detail="Motivo deve ter pelo menos 10 caracteres")
    alerta = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.id == alerta_id,
        AlertaPreditivo.organization_id == user.organization_id,
    ).first()
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    alerta.status = "IGNORADO"
    alerta.ignorado_por = user.id
    alerta.motivo_ignorado = data.motivo
    alerta.resolvido_em = datetime.now(timezone.utc)
    db.commit()
    return {"mensagem": "Alerta ignorado"}


@api_router.get("/preditivo/dashboard")
async def dashboard_preditivo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")

    equips = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.monitoramento_ativo == True,
    ).all()
    total_mon = len(equips)
    normal = sum(1 for e in equips if getattr(e, "status_saude", "NORMAL") == "NORMAL")
    atencao = sum(1 for e in equips if getattr(e, "status_saude", "NORMAL") == "ATENCAO")
    critico = sum(1 for e in equips if getattr(e, "status_saude", "NORMAL") == "CRITICO")

    alertas_abertos = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.organization_id == user.organization_id,
        AlertaPreditivo.status == "ABERTO",
    ).all()
    alertas_criticos = [a for a in alertas_abertos if a.severidade == "CRITICO"]

    rul_vals = [e.rul_estimado_dias for e in equips if e.rul_estimado_dias is not None]
    media_rul = round(sum(rul_vals) / len(rul_vals), 1) if rul_vals else None

    menor_rul_equip = None
    if equips:
        candidatos = [(e, e.rul_estimado_dias) for e in equips if e.rul_estimado_dias is not None]
        if candidatos:
            e_min, rul_min = min(candidatos, key=lambda x: x[1])
            menor_rul_equip = {"nome": e_min.nome, "rul_dias": rul_min}

    # Histórico 30d de saúde (simplificado — conta alertas por dia)
    inicio_30d = datetime.now(timezone.utc) - timedelta(days=30)
    alertas_30d = db.query(AlertaPreditivo).filter(
        AlertaPreditivo.organization_id == user.organization_id,
        AlertaPreditivo.criado_em >= inicio_30d,
    ).all()
    hist = {}
    for a in alertas_30d:
        d = a.criado_em.strftime("%Y-%m-%d")
        hist.setdefault(d, {"data": d, "atencao": 0, "critico": 0})
        hist[d][a.severidade.lower()] += 1

    top_risco = sorted(
        [{"equipamento_id": str(e.id), "nome": e.nome,
          "rul_dias": e.rul_estimado_dias,
          "status_saude": getattr(e, "status_saude", "NORMAL"),
          "custo_hora_parada": e.valor_hora}
         for e in equips],
        key=lambda x: (x["rul_dias"] or 9999),
    )[:5]

    return {
        "total_equipamentos_monitorados": total_mon,
        "equipamentos_normal": normal,
        "equipamentos_atencao": atencao,
        "equipamentos_critico": critico,
        "alertas_abertos": len(alertas_abertos),
        "alertas_criticos_abertos": len(alertas_criticos),
        "media_rul_dias": media_rul,
        "equipamento_menor_rul": menor_rul_equip,
        "historico_saude_30d": sorted(hist.values(), key=lambda x: x["data"]),
        "top_risco": top_risco,
    }


@api_router.get("/preditivo/saude-equipamentos")
async def saude_equipamentos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "modulo_preditivo")
    equips = db.query(Equipamento).filter(
        Equipamento.organization_id == user.organization_id,
        Equipamento.ativo == True,
    ).all()
    alertas_abertos = {
        str(a.equipamento_id): a for a in db.query(AlertaPreditivo).filter(
            AlertaPreditivo.organization_id == user.organization_id,
            AlertaPreditivo.status == "ABERTO",
        ).all()
    }
    return [{"id": str(e.id), "nome": e.nome, "codigo": e.codigo,
             "localizacao": e.localizacao,
             "monitoramento_ativo": getattr(e, "monitoramento_ativo", False),
             "status_saude": getattr(e, "status_saude", "NORMAL"),
             "rul_estimado_dias": getattr(e, "rul_estimado_dias", None),
             "mttr_horas": getattr(e, "mttr_horas", None),
             "mtbf_horas": getattr(e, "mtbf_horas", None),
             "disponibilidade_percent": getattr(e, "disponibilidade_percent", None),
             "alerta_ativo": str(e.id) in alertas_abertos,
             "alerta_severidade": alertas_abertos[str(e.id)].severidade if str(e.id) in alertas_abertos else None,
             "valor_hora": e.valor_hora} for e in equips]


# ========== DASHBOARD AVANÇADO ==========

@api_router.get("/dashboard/tendencia")
async def get_tendencia(
    dias: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna série temporal de OS abertas nos últimos N dias (dashboard avançado)."""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "dashboard_avancado")

    now = datetime.now(timezone.utc)
    from sqlalchemy import func, cast, Date as SADate

    result = []
    for i in range(dias - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        total = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.created_at >= day_start,
            OrdemServico.created_at < day_end,
        ).count()
        corretivas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.created_at >= day_start,
            OrdemServico.created_at < day_end,
            OrdemServico.tipo == TipoOS.CORRETIVA,
        ).count()
        fechadas = db.query(OrdemServico).filter(
            OrdemServico.organization_id == user.organization_id,
            OrdemServico.created_at >= day_start,
            OrdemServico.created_at < day_end,
            OrdemServico.status == StatusOS.FECHADA,
        ).count()
        result.append({
            "data": day_start.strftime("%d/%m"),
            "total": total,
            "corretivas": corretivas,
            "fechadas": fechadas,
        })

    return {"dias": dias, "serie": result}


# ========== KANBAN ==========

@api_router.get("/kanban")
async def get_kanban(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna OS agrupadas por status para o board Kanban."""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    _require_feature(org, "kanban")

    ordens = db.query(OrdemServico).filter(
        OrdemServico.organization_id == user.organization_id,
        OrdemServico.status != StatusOS.FECHADA,
    ).order_by(OrdemServico.created_at.desc()).all()

    eq_map = {str(e.id): e.nome for e in db.query(Equipamento).filter(Equipamento.organization_id == user.organization_id).all()}
    user_map = {str(u.id): u.nome for u in db.query(User).filter(User.organization_id == user.organization_id).all()}

    columns = {s.value: [] for s in [StatusOS.ABERTA, StatusOS.EM_ATENDIMENTO, StatusOS.AGUARDANDO_REVISAO, StatusOS.REVISADA]}

    for o in ordens:
        col = o.status.value
        if col not in columns:
            continue
        columns[col].append({
            "id": str(o.id),
            "numero": o.numero,
            "equipamento": eq_map.get(str(o.equipamento_id), "—"),
            "tipo": o.tipo.value,
            "prioridade": o.prioridade.value,
            "tecnico": user_map.get(str(o.tecnico_id), None) if o.tecnico_id else None,
            "descricao": (o.descricao or "")[:80],
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "dentro_sla": o.dentro_sla,
            "reincidente": o.reincidente,
            "tempo_resposta": o.tempo_resposta,
        })

    return {
        "columns": [
            {"id": "aberta",              "label": "Aberta",           "cards": columns["aberta"]},
            {"id": "em_atendimento",      "label": "Em Atendimento",   "cards": columns["em_atendimento"]},
            {"id": "aguardando_revisao",  "label": "Ag. Revisão",      "cards": columns["aguardando_revisao"]},
            {"id": "revisada",            "label": "Revisada",         "cards": columns["revisada"]},
        ]
    }


# ========== SEED DATA ==========
@api_router.post("/seed-demo")
async def seed_demo_data(reset: bool = False, db: Session = Depends(get_db)):
    """Cria dados de demonstração completos com usuários por setor"""
    ORG_NOME = "Indústria AURIX Demo Ltda."
    ORG_NOME_OLD = "Empresa Demo"

    demo_org = (
        db.query(Organization).filter(Organization.nome == ORG_NOME).first()
        or db.query(Organization).filter(Organization.nome == ORG_NOME_OLD).first()
    )
    if demo_org and not reset:
        return {
            "message": "Dados de demonstração já existem. Use ?reset=true para recriar.",
            "email": "admin@demo.aurix", "senha": "admin123"
        }

    import random as _random
    from sqlalchemy import text as sa_text

    # ── Reset: deletar org existente em ordem de dependência ─────────────────
    if demo_org and reset:
        oid = str(demo_org.id)
        for table, col in [
            ("auditoria_logs",               "organization_id"),
            ("notificacoes",                 "org_id"),
            ("custos_os",                    "organization_id"),
            ("alertas_preditivos",           "organization_id"),
            ("leituras_sensor",              "organization_id"),
            ("configuracoes_monitoramento",  "organization_id"),
            ("ordens_servico",               "organization_id"),
            ("planos_preventivos",           "organization_id"),
            ("equipamentos",                 "organization_id"),
            ("subgrupos",                    "organization_id"),
            ("grupos",                       "organization_id"),
            ("payment_transactions",         "organization_id"),
            ("users",                        "organization_id"),
        ]:
            db.execute(sa_text(f"DELETE FROM {table} WHERE {col} = :oid"), {"oid": oid})
        db.execute(sa_text("DELETE FROM organizations WHERE id = :oid"), {"oid": oid})
        db.commit()
        db.expire_all()

    rng = _random.Random(42)  # deterministic for reproducibility
    now = datetime.now(timezone.utc)

    # ── Organização ──────────────────────────────────────────────────────────
    org = Organization(
        nome=ORG_NOME,
        cnpj="12.345.678/0001-90",
        plano=PlanoSaaS.AVANCADO,
        limite_equipamentos=50,
        limite_usuarios=100,
        limite_os_mes=-1,
        plano_trial_expira_em=now + timedelta(days=365),
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    org_id = org.id

    # ── Grupos e Subgrupos ────────────────────────────────────────────────────
    G = {}  # nome → Grupo
    S = {}  # nome → Subgrupo
    estrutura = {
        "MECÂNICA":   ["Manutenção Preventiva", "Manutenção Corretiva", "Hidráulica", "Pneumática"],
        "ELÉTRICA":   ["Alta Tensão", "Automação/CLP", "Instrumentação", "Motores"],
        "T.I.":       ["Infraestrutura", "Sistemas", "Conectividade", "Segurança"],
        "UTILIDADES": ["Caldeiraria", "HVAC", "Compressores", "Utilidades Gerais"],
    }
    for grp_nome, subgrps in estrutura.items():
        grp = Grupo(organization_id=org_id, nome=grp_nome, descricao=f"Setor {grp_nome}")
        db.add(grp); db.flush(); G[grp_nome] = grp
        for sg in subgrps:
            s = Subgrupo(organization_id=org_id, grupo_id=grp.id, nome=sg)
            db.add(s); db.flush(); S[sg] = s
    db.commit()

    # ── Usuários (12 — todos os setores) ─────────────────────────────────────
    def _u(email, nome, role, setor=None, is_lider=False, senha="Aurix@2025"):
        return User(email=email, password_hash=hash_password(senha), nome=nome,
                    role=role, organization_id=org_id, setor=setor, is_lider=is_lider)

    u_admin     = _u("admin@demo.aurix",          "Carlos Mendes",          UserRole.ADMIN,    senha="admin123")
    u_lmec      = _u("lider.mecanica@demo.aurix",  "Roberto Souza",          UserRole.LIDER,    "MECÂNICA", True)
    u_t1mec     = _u("joao.silva@demo.aurix",      "João Silva",             UserRole.TECNICO,  "MECÂNICA")
    u_t2mec     = _u("pedro.costa@demo.aurix",     "Pedro Costa",            UserRole.TECNICO,  "MECÂNICA")
    u_opmec     = _u("marcos.lima@demo.aurix",     "Marcos Lima",            UserRole.OPERADOR, "MECÂNICA")
    u_lele      = _u("lider.eletrica@demo.aurix",  "Fernanda Rocha",         UserRole.LIDER,    "ELÉTRICA", True)
    u_t1ele     = _u("ana.santos@demo.aurix",      "Ana Santos",             UserRole.TECNICO,  "ELÉTRICA")
    u_t2ele     = _u("carlos.ferreira@demo.aurix", "Carlos Ferreira",        UserRole.TECNICO,  "ELÉTRICA")
    u_opele     = _u("lucia.pereira@demo.aurix",   "Lúcia Pereira",          UserRole.OPERADOR, "ELÉTRICA")
    u_lti       = _u("lider.ti@demo.aurix",        "Rafael Oliveira",        UserRole.LIDER,    "T.I.", True)
    u_t1ti      = _u("rodrigo.alves@demo.aurix",   "Rodrigo Alves",          UserRole.TECNICO,  "T.I.")
    u_opti      = _u("julia.moura@demo.aurix",     "Júlia Moura",            UserRole.OPERADOR, "T.I.")

    all_users = [u_admin,u_lmec,u_t1mec,u_t2mec,u_opmec,u_lele,u_t1ele,u_t2ele,u_opele,u_lti,u_t1ti,u_opti]
    db.add_all(all_users); db.commit()
    for u in all_users: db.refresh(u)

    # ── Equipamentos (15) ─────────────────────────────────────────────────────
    eq_defs = [
        # MECÂNICA
        ("EQ-001","Prensa Hidráulica 200T",    "Setor A — Prensas",        "MECÂNICA",   650,5, G["MECÂNICA"],S["Hidráulica"],         True),
        ("EQ-002","Torno CNC MAZAK QT200",     "Setor B — Usinagem",       "MECÂNICA",   900,5, G["MECÂNICA"],S["Manutenção Preventiva"],True),
        ("EQ-003","Fresadora Vertical Romi",   "Setor B — Usinagem",       "MECÂNICA",   750,4, G["MECÂNICA"],S["Manutenção Corretiva"], False),
        ("EQ-004","Compressor Atlas Copco GA55","Sala de Compressores",     "MECÂNICA",   350,4, G["MECÂNICA"],S["Pneumática"],          True),
        ("EQ-005","Bomba Centrífuga KSB 200",  "Setor A — Utilidades",     "MECÂNICA",   280,3, G["MECÂNICA"],S["Hidráulica"],          False),
        # ELÉTRICA
        ("EQ-006","Quadro Elétrico Principal", "Subestação",               "ELÉTRICA",   500,5, G["ELÉTRICA"],S["Alta Tensão"],         True),
        ("EQ-007","Motor Trifásico WEG 75kW",  "Setor C — Movimentação",   "ELÉTRICA",   420,4, G["ELÉTRICA"],S["Motores"],             True),
        ("EQ-008","CLP Siemens S7-1500",       "Painel Automação PA-01",   "ELÉTRICA",   600,5, G["ELÉTRICA"],S["Automação/CLP"],       False),
        ("EQ-009","Drive Inversor ABB ACS880", "Painel Automação PA-02",   "ELÉTRICA",   450,4, G["ELÉTRICA"],S["Automação/CLP"],       False),
        ("EQ-010","Gerador CAT DE500GC",       "Casa de Força",            "ELÉTRICA",   800,5, G["ELÉTRICA"],S["Instrumentação"],      True),
        # T.I.
        ("EQ-011","Servidor Dell PowerEdge R750","Data Center — Rack 01",  "T.I.",       300,4, G["T.I."],    S["Infraestrutura"],      True),
        ("EQ-012","Switch Core Cisco Cat.9500","Data Center — Rack 02",    "T.I.",       200,3, G["T.I."],    S["Conectividade"],       False),
        ("EQ-013","UPS APC Smart-UPS 10kVA",  "Data Center — Rack 03",    "T.I.",       150,4, G["T.I."],    S["Infraestrutura"],      False),
        # UTILIDADES
        ("EQ-014","Caldeira Thermax 500kg/h",  "Casa de Caldeiras",        "UTILIDADES", 720,5, G["UTILIDADES"],S["Caldeiraria"],       True),
        ("EQ-015","Sistema HVAC Carrier 100TR","Cobertura Industrial",      "UTILIDADES", 320,3, G["UTILIDADES"],S["HVAC"],             False),
    ]
    E = {}
    for (cod,nome,loc,setor,vh,crit,grp,sgrp,mon) in eq_defs:
        eq = Equipamento(organization_id=org_id, codigo=cod, nome=nome, localizacao=loc,
                         valor_hora=float(vh), grupo_id=grp.id, subgrupo_id=sgrp.id, criticidade=crit)
        db.add(eq); db.flush(); E[cod] = eq
    db.commit()

    # Set unmapped columns via raw SQL
    for (cod,_,_,setor,_,_,_,_,mon) in eq_defs:
        db.execute(sa_text(
            "UPDATE equipamentos SET setor=:s, monitoramento_ativo=:m WHERE id=:id"
        ), {"s": setor, "m": mon, "id": str(E[cod].id)})
    db.commit()

    # ── Configurações de Monitoramento ────────────────────────────────────────
    mon_cfgs = [
        ("EQ-001","Temperatura do Óleo",     "°C",   70,  85,  7),
        ("EQ-001","Pressão Hidráulica",       "bar",  200, 230, 7),
        ("EQ-002","Temperatura do Fuso",      "°C",   65,  80, 14),
        ("EQ-002","Vibração do Fuso",         "mm/s", 3.5, 6.0,14),
        ("EQ-004","Temperatura de Descarga",  "°C",   75,  90,  7),
        ("EQ-004","Nível de Óleo",            "%",    30,  15,  3),
        ("EQ-006","Temperatura do Barramento","°C",   55,  70,  7),
        ("EQ-007","Temperatura da Bobina",    "°C",   80, 100,  7),
        ("EQ-007","Vibração",                 "mm/s", 4.0, 7.0,14),
        ("EQ-010","Temperatura do Óleo",      "°C",   80,  95,  7),
        ("EQ-011","Temperatura da CPU",       "°C",   70,  85,  3),
        ("EQ-011","Uso de Disco",             "%",    80,  92,  7),
        ("EQ-014","Pressão do Vapor",         "bar",  8.0,10.0, 3),
        ("EQ-014","Temperatura da Câmara",    "°C",  180, 200,  3),
    ]
    CM = {}
    for (cod,param,un,at,cr,jd) in mon_cfgs:
        cm = ConfiguracaoMonitoramento(organization_id=org_id, equipamento_id=E[cod].id,
                                       parametro_nome=param, unidade=un,
                                       threshold_atencao=at, threshold_critico=cr,
                                       tendencia_janela_dias=jd, ativo=True)
        db.add(cm); db.flush(); CM[(cod,param)] = cm
    db.commit()

    # ── Leituras de sensor (30 dias, tendências variadas) ─────────────────────
    # (eq_code, param): (tipo, base_valor, slope_por_dia)
    # tipo "crescente"=subindo, "normal"=estável com ruído, "critico"=já alto
    tendencias = {
        ("EQ-001","Temperatura do Óleo"):      ("crescente", 52.0,  1.1),
        ("EQ-001","Pressão Hidráulica"):        ("normal",   172.0,  0.0),
        ("EQ-002","Temperatura do Fuso"):       ("normal",    45.0,  0.0),
        ("EQ-002","Vibração do Fuso"):          ("crescente",  1.8,  0.08),
        ("EQ-004","Temperatura de Descarga"):   ("normal",    61.0,  0.0),
        ("EQ-004","Nível de Óleo"):             ("crescente", 86.0, -1.9),
        ("EQ-006","Temperatura do Barramento"): ("normal",    42.0,  0.0),
        ("EQ-007","Temperatura da Bobina"):     ("critico",   83.0,  1.4),
        ("EQ-007","Vibração"):                  ("crescente",  3.0,  0.13),
        ("EQ-010","Temperatura do Óleo"):       ("normal",    65.0,  0.0),
        ("EQ-011","Temperatura da CPU"):        ("crescente", 61.0,  0.6),
        ("EQ-011","Uso de Disco"):              ("crescente", 73.0,  0.45),
        ("EQ-014","Pressão do Vapor"):          ("normal",     6.6,  0.0),
        ("EQ-014","Temperatura da Câmara"):     ("critico",  183.0,  2.0),
    }
    unidade_lookup = {(cod,param): un for (cod,param,un,_,_,_) in mon_cfgs}
    for (cod,param), (tipo,base,slope) in tendencias.items():
        eq = E[cod]
        un = unidade_lookup.get((cod,param), "")
        for day in range(30, 0, -1):
            idx = 30 - day
            noise = rng.uniform(-0.8, 0.8)
            if tipo == "crescente":
                val = base + slope * idx + noise
            elif tipo == "critico":
                val = base + slope * (idx * 0.4) + noise
            else:
                val = base + noise * 1.5
            val = max(0.0, round(val, 2))
            db.add(LeituraSensor(
                organization_id=org_id, equipamento_id=eq.id,
                parametro_nome=param, valor=val, unidade=un,
                fonte="sensor_iot", timestamp=now - timedelta(days=day), processado=True,
            ))
    db.commit()

    # ── Alertas Preditivos ────────────────────────────────────────────────────
    alertas_defs = [
        ("EQ-007","Temperatura da Bobina","CRITICO", 91.5, 80, "CRESCENTE",12,"Temperatura da bobina do Motor WEG 75kW acima do limiar crítico. Risco de queima do isolamento.","ABERTO"),
        ("EQ-014","Temperatura da Câmara","CRITICO",196.0,180, "CRITICA",   5,"Temperatura da câmara da Caldeira Thermax crítica. Ação imediata necessária.","ABERTO"),
        ("EQ-001","Temperatura do Óleo",  "ATENCAO", 68.5, 70, "CRESCENTE",28,"Temperatura do óleo hidráulico da Prensa 200T em tendência crescente.","ABERTO"),
        ("EQ-002","Vibração do Fuso",     "ATENCAO",  3.3, 3.5,"CRESCENTE",18,"Vibração do fuso do Torno CNC aumentando. Possível desgaste dos mancais.","ABERTO"),
        ("EQ-011","Uso de Disco",         "ATENCAO", 86.2, 80, "CRESCENTE",22,"Uso de disco do Servidor Dell acima de 80%. Planejar expansão.","ABERTO"),
        ("EQ-004","Nível de Óleo",        "ATENCAO", 31.0, 30, "CRESCENTE", 3,"Nível de óleo do Compressor próximo ao mínimo. Agendar reabastecimento.","OS_GERADA"),
        ("EQ-007","Vibração",             "ATENCAO",  3.9, 4.0,"CRESCENTE",15,"Vibração do Motor WEG próxima ao limiar de atenção.","RESOLVIDO"),
    ]
    for (cod,param,sev,val,thresh,tend,rul,desc,status_a) in alertas_defs:
        db.add(AlertaPreditivo(
            organization_id=org_id, equipamento_id=E[cod].id,
            parametro_nome=param, severidade=sev, valor_atual=val,
            threshold_violado=thresh, tendencia=tend, rul_estimado_dias=rul,
            descricao=desc, status=status_a,
            criado_em=now - timedelta(days=rng.randint(1,5)),
            resolvido_em=now - timedelta(hours=6) if status_a=="RESOLVIDO" else None,
        ))
    db.commit()

    # Atualizar status_saude via SQL (colunas não mapeadas no ORM)
    saude_map = {
        "EQ-001":("ATENCAO",28),"EQ-002":("ATENCAO",18),"EQ-004":("ATENCAO",3),
        "EQ-006":("NORMAL",None),"EQ-007":("CRITICO",12),"EQ-010":("NORMAL",None),
        "EQ-011":("ATENCAO",22),"EQ-014":("CRITICO",5),
    }
    for cod,(saude,rul) in saude_map.items():
        db.execute(sa_text(
            "UPDATE equipamentos SET status_saude=:s, rul_estimado_dias=:r WHERE id=:id"
        ), {"s": saude, "r": rul, "id": str(E[cod].id)})
    db.commit()

    # ── Ordens de Serviço (50 OS) ─────────────────────────────────────────────
    tipos_falha   = ["Mecânica","Elétrica","Hidráulica","Pneumática","Software","Instrumentação","Estrutural"]
    modos_falha   = ["Desgaste","Quebra","Vazamento","Curto-circuito","Travamento","Superaquecimento","Vibração excessiva"]
    causas_falha  = ["Uso inadequado","Falta de lubrificação","Fim de vida útil","Sobrecarga","Defeito de fábrica","Contaminação","Operação fora de faixa"]
    descricoes_cor = [
        "Prensa sem pressão — verificar bomba hidráulica e válvulas",
        "Torno parado por alarme de temperatura do fuso",
        "Fresadora com vibração anormal no eixo Z — rolamento suspeito",
        "Compressor não atinge pressão nominal — verificar válvulas",
        "Bomba com ruído anormal e perda de vazão na sucção",
        "Quadro elétrico com disjuntor disparando repetidamente",
        "Motor WEG com superaquecimento após 2h de operação contínua",
        "CLP em fault — falha na comunicação Profinet com periféricos",
        "Drive ABB com sobrecorrente — equipamento parado",
        "Gerador não participa do sincronismo com a rede",
        "Servidor com temperatura crítica da CPU — risco de desligamento",
        "Switch core com perda de uplink — link redundante ativo",
        "UPS em bypass — bateria descarregada, sem proteção",
        "Caldeira sem ignição — falha detectada na válvula de gás",
        "HVAC com mau funcionamento do compressor de refrigeração",
        "Prensa hidráulica com vazamento de óleo no cilindro principal",
        "Esteira transportadora com corrente solta no trecho 3",
        "Painel elétrico com arco-voltaico detectado no barramento",
    ]
    descricoes_prev = [
        "Troca de fluido hidráulico e substituição de filtros — preventiva mensal",
        "Inspeção de rolamentos, ajuste de correias e tensão de correntes",
        "Limpeza geral, lubrificação de guias e reaperto de fixações",
        "Inspeção elétrica completa, aperto de conexões e medição de isolamento",
        "Calibração de sensores de pressão, temperatura e nível",
        "Limpeza de condensadores, evaporadores e drenos de HVAC",
        "Inspeção de vedações, mangueiras e conexões hidráulicas",
        "Leitura de parâmetros do inversor de frequência e backup de configurações",
    ]
    solucoes = [
        "Peça substituída e equipamento testado em carga.",
        "Ajuste de parâmetros e recalibração realizada com sucesso.",
        "Limpeza profunda e lubrificação executadas conforme procedimento.",
        "Regulagem concluída e equipamento liberado para produção.",
        "Firmware atualizado e comunicação restabelecida.",
        "Componente danificado substituído por novo do estoque.",
        "Vazamento eliminado com troca do retentores e vedações.",
        "Conexões refeitas e disjuntor substituído — funcionamento normal.",
    ]

    # Setor → (equips, tecnicos, operador, lider)
    setor_map = {
        "MECÂNICA":   ([E["EQ-001"],E["EQ-002"],E["EQ-003"],E["EQ-004"],E["EQ-005"]], [u_t1mec,u_t2mec], u_opmec, u_lmec),
        "ELÉTRICA":   ([E["EQ-006"],E["EQ-007"],E["EQ-008"],E["EQ-009"],E["EQ-010"]], [u_t1ele,u_t2ele], u_opele, u_lele),
        "T.I.":       ([E["EQ-011"],E["EQ-012"],E["EQ-013"]],                          [u_t1ti],          u_opti,  u_lti),
        "UTILIDADES": ([E["EQ-014"],E["EQ-015"]],                                      [u_t1mec,u_t1ele], u_opmec, u_lmec),
    }
    setores_ciclo = list(setor_map.items())
    all_os = []

    for i in range(50):
        setor_nome, (s_equips, s_tecs, s_op, s_lider) = setores_ciclo[i % len(setores_ciclo)]
        eq = rng.choice(s_equips)
        tipo = rng.choices([TipoOS.CORRETIVA,TipoOS.PREVENTIVA,TipoOS.PREDITIVA], weights=[60,30,10])[0]
        prioridade = rng.choices(list(PrioridadeOS), weights=[15,40,30,15])[0]
        status = rng.choices(
            [StatusOS.ABERTA,StatusOS.EM_ATENDIMENTO,StatusOS.AGUARDANDO_REVISAO,StatusOS.REVISADA,StatusOS.FECHADA],
            weights=[20,15,15,10,40]
        )[0]
        created_at = now - timedelta(days=rng.randint(0, 90))
        if tipo == TipoOS.CORRETIVA:
            desc = rng.choice(descricoes_cor)
            ft = rng.choice(tipos_falha); fm = rng.choice(modos_falha); fc = rng.choice(causas_falha)
        elif tipo == TipoOS.PREVENTIVA:
            desc = rng.choice(descricoes_prev); ft = fm = fc = None
        else:
            desc = f"OS gerada por alerta preditivo — {eq.nome}"; ft = fm = fc = None
        tec = rng.choice(s_tecs)
        os_obj = OrdemServico(
            numero=i+1, organization_id=org_id,
            equipamento_id=eq.id, grupo_id=eq.grupo_id, subgrupo_id=eq.subgrupo_id,
            tipo=tipo, prioridade=prioridade, status=status, descricao=desc,
            solicitante_id=s_op.id, falha_tipo=ft, falha_modo=fm, falha_causa=fc,
            created_at=created_at,
        )
        if status in (StatusOS.EM_ATENDIMENTO,StatusOS.AGUARDANDO_REVISAO,StatusOS.REVISADA,StatusOS.FECHADA):
            delay = rng.randint(5, 180)
            os_obj.tecnico_id = tec.id
            os_obj.inicio_atendimento = created_at + timedelta(minutes=delay)
            os_obj.tempo_resposta = delay
            os_obj.dentro_sla = calculate_sla(prioridade, delay)
        if status in (StatusOS.AGUARDANDO_REVISAO,StatusOS.REVISADA,StatusOS.FECHADA):
            repair = rng.randint(30, 720)
            os_obj.fim_atendimento = os_obj.inicio_atendimento + timedelta(minutes=repair)
            os_obj.tempo_reparo = repair
            os_obj.tempo_total = (os_obj.tempo_resposta or 0) + repair
            os_obj.solucao = rng.choice(solucoes)
        if status in (StatusOS.REVISADA, StatusOS.FECHADA):
            os_obj.revisado_at = os_obj.fim_atendimento + timedelta(hours=rng.randint(1,8))
            os_obj.revisor_id = s_lider.id
        if status == StatusOS.FECHADA:
            os_obj.fechado_at = os_obj.revisado_at
        db.add(os_obj); all_os.append(os_obj)
    db.commit()
    for o in all_os: db.refresh(o)

    # ── Custos ────────────────────────────────────────────────────────────────
    descs_custo = {
        TipoCusto.CONSUMO:      ["Óleo lubrificante 20L","Graxa industrial 5kg","Fluido hidráulico 10L","Filtro de ar","Mangueira hidráulica"],
        TipoCusto.SUBSTITUICAO: ["Rolamento SKF 6205","Correia V-Belt A-65","Vedação de eixo","Capacitor 450V 40µF","Fusível NH3 200A","Contator Schneider 40A"],
        TipoCusto.MAO_OBRA:     ["Mão de obra técnica","Hora extra técnico","Serviço terceirizado Siemens","Consultor ABB"],
    }
    for os_obj in all_os:
        if os_obj.status in (StatusOS.FECHADA, StatusOS.REVISADA):
            for _ in range(rng.choices([0,1,2,3], weights=[15,45,30,10])[0]):
                tc = rng.choice(list(TipoCusto))
                db.add(CustoOS(
                    ordem_servico_id=os_obj.id, tipo=tc,
                    descricao=rng.choice(descs_custo[tc]),
                    valor=round(rng.uniform(30,1200),2),
                    quantidade=rng.randint(1,4),
                    organization_id=org_id,
                ))
    db.commit()

    # ── Planos Preventivos (12) ───────────────────────────────────────────────
    planos_defs = [
        ("EQ-001","Troca de Óleo Hidráulico",          30, 45, 5),
        ("EQ-002","Inspeção de Mancais do Fuso",        14, 10, 4),
        ("EQ-003","Lubrificação e Ajuste Geral",        30,  8,22),
        ("EQ-004","Troca de Filtro do Compressor",       7, 12,-5),   # vencido
        ("EQ-005","Inspeção de Vedações da Bomba",      60, 50,10),
        ("EQ-006","Termografia e Aperto Elétrico",      30, 20,10),
        ("EQ-007","Inspeção do Motor e Rolamentos",     14, 18,-4),   # vencido
        ("EQ-008","Backup e Atualização do CLP",        90, 30,60),
        ("EQ-010","Troca de Óleo do Gerador",          180, 90,90),
        ("EQ-011","Limpeza e Verificação do Servidor",  30, 25, 5),
        ("EQ-014","Inspeção de Segurança da Caldeira",  30, 35,-5),   # vencido
        ("EQ-015","Limpeza de Condensadores HVAC",      60, 40,20),
    ]
    for (cod,nome,freq,dias_atras,prox_delta) in planos_defs:
        db.add(PlanoPreventivo(
            organization_id=org_id, equipamento_id=E[cod].id,
            nome=nome, descricao=f"Manutenção preventiva — {nome.lower()}",
            frequencia_dias=freq,
            ultima_execucao=now - timedelta(days=dias_atras),
            proxima_execucao=now + timedelta(days=prox_delta),
        ))
    db.commit()

    # ── Notificações ─────────────────────────────────────────────────────────
    notifs = [
        (u_lele,  "alerta_critico", "Alerta Crítico", "Motor WEG 75kW com temperatura acima do limiar crítico. Verifique imediatamente.",  1),
        (u_admin, "alerta_critico", "Alerta Crítico", "Caldeira Thermax com temperatura próxima ao limite de segurança. Ação necessária.", 2),
        (u_lmec,  "preventivo_vencido","Preventivo Vencido","Troca de Filtro do Compressor (EQ-004) está vencida há 5 dias.",               3),
        (u_lele,  "preventivo_vencido","Preventivo Vencido","Inspeção do Motor WEG (EQ-007) está vencida há 4 dias.",                       4),
        (u_lmec,  "aprovacao_pendente","OS Aguardando Revisão","OS #3 — Compressor Atlas Copco aguarda sua revisão.",                       8),
        (u_lti,   "alerta_critico","Espaço em Disco","Servidor Dell PowerEdge com uso de disco acima de 86%. Planejar expansão.",           12),
    ]
    for (dest, tipo_n, titulo_n, msg, h) in notifs:
        db.add(Notificacao(
            org_id=org_id, destinatario_id=dest.id,
            tipo=tipo_n, titulo=titulo_n, mensagem=msg,
            lida=False, criada_em=now - timedelta(hours=h),
        ))
    db.commit()

    return {
        "message": "Dados de demonstração criados com sucesso.",
        "organizacao": ORG_NOME,
        "plano": "AVANCADO",
        "credenciais": {
            "admin":             {"email": "admin@demo.aurix",          "senha": "admin123",   "role": "admin",    "setor": None},
            "lider_mecanica":    {"email": "lider.mecanica@demo.aurix", "senha": "Aurix@2025", "role": "lider",    "setor": "MECÂNICA"},
            "tecnico_mec_1":     {"email": "joao.silva@demo.aurix",     "senha": "Aurix@2025", "role": "tecnico",  "setor": "MECÂNICA"},
            "tecnico_mec_2":     {"email": "pedro.costa@demo.aurix",    "senha": "Aurix@2025", "role": "tecnico",  "setor": "MECÂNICA"},
            "operador_mec":      {"email": "marcos.lima@demo.aurix",    "senha": "Aurix@2025", "role": "operador", "setor": "MECÂNICA"},
            "lider_eletrica":    {"email": "lider.eletrica@demo.aurix", "senha": "Aurix@2025", "role": "lider",    "setor": "ELÉTRICA"},
            "tecnico_ele_1":     {"email": "ana.santos@demo.aurix",     "senha": "Aurix@2025", "role": "tecnico",  "setor": "ELÉTRICA"},
            "tecnico_ele_2":     {"email": "carlos.ferreira@demo.aurix","senha": "Aurix@2025", "role": "tecnico",  "setor": "ELÉTRICA"},
            "operador_ele":      {"email": "lucia.pereira@demo.aurix",  "senha": "Aurix@2025", "role": "operador", "setor": "ELÉTRICA"},
            "lider_ti":          {"email": "lider.ti@demo.aurix",       "senha": "Aurix@2025", "role": "lider",    "setor": "T.I."},
            "tecnico_ti":        {"email": "rodrigo.alves@demo.aurix",  "senha": "Aurix@2025", "role": "tecnico",  "setor": "T.I."},
            "operador_ti":       {"email": "julia.moura@demo.aurix",    "senha": "Aurix@2025", "role": "operador", "setor": "T.I."},
        },
        "estatisticas": {
            "usuarios": 12, "equipamentos": 15, "ordens_servico": 50,
            "planos_preventivos": 12, "configs_monitoramento": len(mon_cfgs),
            "leituras_sensor": len(tendencias) * 30, "alertas_preditivos": len(alertas_defs),
        },
    }

# Include router
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "AURIX — Tecnologia para a Gestão Industrial", "version": "3.0.0"}

_scheduler = None

@app.on_event("startup")
async def startup():
    global _scheduler
    logger.info("Starting AURIX application...")
    try:
        ensure_database_schema()
    except HTTPException as exc:
        logger.warning("Application started without database connectivity: %s", exc.detail)

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
        _scheduler.add_job(lambda: _run_job(_job_processar_leituras),      "interval", minutes=15,  id="proc_leituras")
        _scheduler.add_job(lambda: _run_job(_job_auto_aprovar_sla),         "interval", minutes=30,  id="auto_aprovar")
        _scheduler.add_job(lambda: _run_job(_job_gerar_os_preventivas),     "cron",     hour=7, minute=0, id="os_preventivas")
        _scheduler.add_job(lambda: _run_job(_job_atualizar_mttr_mtbf),      "cron",     hour=0, minute=0, id="mttr_mtbf")
        _scheduler.start()
        logger.info("APScheduler iniciado com 4 jobs")
    except ImportError:
        logger.warning("APScheduler não disponível — jobs em background desabilitados")
    except Exception as exc:
        logger.warning("APScheduler falhou ao iniciar: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
    logger.info("Shutting down AURIX application...")
