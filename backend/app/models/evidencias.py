"""
Models para Fase 2 — Evidências e Compliance Operacional.
Todas as tabelas incluem organization_id para isolamento de tenant.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..database import Base


class AnexoOS(Base):
    __tablename__ = "anexos_os"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    os_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id", ondelete="CASCADE"), nullable=False)
    storage_key = Column(String(500), nullable=False)     # chave no S3/R2 (UUID-based)
    nome_original = Column(String(500), nullable=False)   # nome enviado pelo usuário (metadado)
    mime = Column(String(100), nullable=False)
    tamanho = Column(Integer, nullable=False)              # bytes
    hash_sha256 = Column(String(64), nullable=False)       # integridade do arquivo
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    descricao = Column(String(500), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deletado_em = Column(DateTime(timezone=True), nullable=True)  # soft delete

    __table_args__ = (
        Index("idx_anexos_os_os_id", "os_id"),
        Index("idx_anexos_os_org", "organization_id"),
    )


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    tipo_os = Column(String(50), nullable=True)              # corretiva|preventiva|preditiva|null=todos
    equipamento_grupo_id = Column(UUID(as_uuid=True), nullable=True)  # filtro opcional por grupo
    # itens: [{id, descricao, obrigatorio: bool}]
    itens = Column(JSONB, nullable=False, default=list)
    obrigatorio_ao_fechar = Column(Boolean, default=True)    # bloqueia fechamento se não preenchido
    ativo = Column(Boolean, default=True)
    criado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_checklist_tmpl_org", "organization_id"),
    )


class ChecklistExecucao(Base):
    __tablename__ = "checklist_execucoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    os_id = Column(UUID(as_uuid=True), ForeignKey("ordens_servico.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("checklist_templates.id"), nullable=False)
    # respostas: {str(item_id): {resposta: ok|nok|na, observacao: str}}
    respostas = Column(JSONB, nullable=False, default=dict)
    executado_por = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    executado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    assinatura_imagem_key = Column(String(500), nullable=True)  # imagem de assinatura (canvas)

    __table_args__ = (
        Index("idx_checklist_exec_os", "os_id"),
        Index("idx_checklist_exec_org", "organization_id"),
    )
