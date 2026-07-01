"""
Modelos do módulo de Almoxarifado / Gestão de Peças — Fase 1.

Todos os modelos são tenant-scoped por organization_id.
Índices compostos garantem isolamento e performance.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean,
    ForeignKey, Text, UniqueConstraint, Index,
    Enum as SQLEnum, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class TipoMovimento(str, enum.Enum):
    ENTRADA = "entrada"
    SAIDA = "saida"
    AJUSTE = "ajuste"


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(255), nullable=False)
    cnpj = Column(String(20), nullable=True)
    contato = Column(String(255), nullable=True)   # nome do contato
    email = Column(String(255), nullable=True)
    telefone = Column(String(30), nullable=True)
    observacoes = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    pecas = relationship("Peca", back_populates="fornecedor_principal", foreign_keys="Peca.fornecedor_principal_id")

    __table_args__ = (
        Index("ix_fornecedores_org", "organization_id"),
        Index("ix_fornecedores_org_cnpj", "organization_id", "cnpj"),
    )


class Peca(Base):
    __tablename__ = "pecas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    codigo = Column(String(50), nullable=False)          # código interno / SKU
    descricao = Column(String(500), nullable=False)
    unidade = Column(String(20), nullable=False, default="un")   # un, kg, m, L, etc.
    custo_unitario = Column(Numeric(14, 4), nullable=False, default=0)
    custo_medio = Column(Numeric(14, 4), nullable=False, default=0)   # custo médio ponderado
    ponto_pedido = Column(Float, nullable=False, default=0)     # quantidade mínima antes de alertar
    lote_economico = Column(Float, nullable=True, default=0)    # quantidade sugerida de compra
    fornecedor_principal_id = Column(UUID(as_uuid=True), ForeignKey("fornecedores.id"), nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    permitir_saldo_negativo = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    fornecedor_principal = relationship("Fornecedor", back_populates="pecas", foreign_keys=[fornecedor_principal_id])
    saldos = relationship("SaldoEstoque", back_populates="peca", cascade="all, delete-orphan")
    movimentos = relationship("MovimentoEstoque", back_populates="peca")

    __table_args__ = (
        UniqueConstraint("organization_id", "codigo", name="uq_peca_org_codigo"),
        Index("ix_pecas_org", "organization_id"),
        Index("ix_pecas_org_ativo", "organization_id", "ativo"),
    )


class Deposito(Base):
    __tablename__ = "depositos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(255), nullable=False)
    localizacao = Column(String(500), nullable=True)   # corredor/prateleira/sala
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    saldos = relationship("SaldoEstoque", back_populates="deposito", cascade="all, delete-orphan")
    movimentos = relationship("MovimentoEstoque", back_populates="deposito")

    __table_args__ = (
        UniqueConstraint("organization_id", "nome", name="uq_deposito_org_nome"),
        Index("ix_depositos_org", "organization_id"),
    )


class SaldoEstoque(Base):
    __tablename__ = "saldo_estoque"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    peca_id = Column(UUID(as_uuid=True), ForeignKey("pecas.id"), nullable=False)
    deposito_id = Column(UUID(as_uuid=True), ForeignKey("depositos.id"), nullable=False)
    quantidade = Column(Float, nullable=False, default=0)
    atualizado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    peca = relationship("Peca", back_populates="saldos")
    deposito = relationship("Deposito", back_populates="saldos")

    __table_args__ = (
        UniqueConstraint("peca_id", "deposito_id", name="uq_saldo_peca_deposito"),
        Index("ix_saldo_org", "organization_id"),
        Index("ix_saldo_peca_deposito", "peca_id", "deposito_id"),
    )


class MovimentoEstoque(Base):
    __tablename__ = "movimentos_estoque"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    peca_id = Column(UUID(as_uuid=True), ForeignKey("pecas.id"), nullable=False)
    deposito_id = Column(UUID(as_uuid=True), ForeignKey("depositos.id"), nullable=False)
    tipo = Column(SQLEnum(TipoMovimento), nullable=False)
    quantidade = Column(Float, nullable=False)
    custo_unitario = Column(Numeric(14, 4), nullable=True)    # custo na data do movimento
    custo_total = Column(Numeric(14, 4), nullable=True)       # quantidade * custo_unitario
    os_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id"), nullable=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    motivo = Column(String(500), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    peca = relationship("Peca", back_populates="movimentos")
    deposito = relationship("Deposito", back_populates="movimentos")

    __table_args__ = (
        Index("ix_movimento_org", "organization_id"),
        Index("ix_movimento_peca", "peca_id"),
        Index("ix_movimento_os", "os_id"),
        Index("ix_movimento_criado", "organization_id", "criado_em"),
    )
