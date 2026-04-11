"""
SQLAlchemy ORM Models for the PCM SaaS platform.
All models enforce multi-tenancy via organization_id foreign key.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean,
    ForeignKey, Text, Enum as SQLEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base
from ..config import (
    UserRole, TipoOS, PrioridadeOS, StatusOS, TipoCusto, PlanoSaaS
)


class Organization(Base):
    """
    Core multi-tenant entity. Every data record belongs to an organization.
    Tracks subscription plan, Stripe integration, and usage limits.
    """
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

    # Relationships
    users = relationship("User", back_populates="organization", lazy="dynamic")
    equipamentos = relationship("Equipamento", back_populates="organization", lazy="dynamic")


class User(Base):
    """
    User model with role-based access control.
    Each user belongs to exactly one organization.
    """
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

    # Relationships
    organization = relationship("Organization", back_populates="users")


class Grupo(Base):
    """Equipment classification group (e.g., Mechanical, Electrical)."""
    __tablename__ = "grupos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Subgrupo(Base):
    """Sub-classification within a group (e.g., Hydraulic under Mechanical)."""
    __tablename__ = "subgrupos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Equipamento(Base):
    """
    Industrial equipment asset tracked by the maintenance system.
    valor_hora represents the cost per hour of machine downtime.
    """
    __tablename__ = "equipamentos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    localizacao = Column(String(255), nullable=True)
    valor_hora = Column(Float, default=0.0)
    grupo_id = Column(UUID(as_uuid=True), ForeignKey("grupos.id"), nullable=True)
    subgrupo_id = Column(UUID(as_uuid=True), ForeignKey("subgrupos.id"), nullable=True)
    ativo = Column(Boolean, default=True)
    criticidade = Column(Integer, default=1)  # 1-5
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index('idx_equipamento_org', 'organization_id'),)

    # Relationships
    organization = relationship("Organization", back_populates="equipamentos")


class OrdemServico(Base):
    """
    Work Order (Ordem de Serviço) — the core operational entity.
    Tracks the full lifecycle from request to completion with timing metrics.
    """
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

    # Users
    solicitante_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tecnico_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revisor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    inicio_atendimento = Column(DateTime(timezone=True), nullable=True)
    fim_atendimento = Column(DateTime(timezone=True), nullable=True)
    revisado_at = Column(DateTime(timezone=True), nullable=True)
    fechado_at = Column(DateTime(timezone=True), nullable=True)

    # Computed timing (in minutes)
    tempo_resposta = Column(Integer, nullable=True)
    tempo_reparo = Column(Integer, nullable=True)
    tempo_total = Column(Integer, nullable=True)

    # SLA
    dentro_sla = Column(Boolean, default=True)

    # Failure analysis
    falha_tipo = Column(String(100), nullable=True)
    falha_modo = Column(String(100), nullable=True)
    falha_causa = Column(String(100), nullable=True)
    reincidente = Column(Boolean, default=False)

    # Block stop
    bloco_parada_id = Column(UUID(as_uuid=True), nullable=True)

    # Review workflow
    review_deadline = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    auto_approved = Column(Boolean, default=False)

    __table_args__ = (Index('idx_os_org', 'organization_id'),)


class CustoOS(Base):
    """Cost line item attached to a work order."""
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
    """Preventive maintenance schedule for an equipment."""
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
    """Audit trail for all data mutations, scoped per organization."""
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
    """Tracks login attempts for brute-force protection."""
    __tablename__ = "login_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identifier = Column(String(255), nullable=False, index=True)
    attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PasswordResetToken(Base):
    """Password reset token for user recovery flow."""
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PaymentTransaction(Base):
    """Stripe payment transaction record."""
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
