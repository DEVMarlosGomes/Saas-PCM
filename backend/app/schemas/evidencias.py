"""
Schemas Pydantic v2 para Fase 2 — Evidências e Compliance Operacional.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Anexos ──────────────────────────────────────────────────────────────────

class AnexoResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    os_id: str
    storage_key: str
    nome_original: str
    mime: str
    tamanho: int
    hash_sha256: str
    descricao: Optional[str] = None
    usuario_id: str
    criado_em: datetime
    url_download: Optional[str] = None   # URL pré-assinada, preenchida pelo endpoint


# ─── Checklist Templates ─────────────────────────────────────────────────────

class ChecklistItemSchema(BaseModel):
    id: int
    descricao: str = Field(min_length=1, max_length=500)
    obrigatorio: bool = True


class ChecklistTemplateCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    tipo_os: Optional[str] = None     # corretiva|preventiva|preditiva|None=todos
    equipamento_grupo_id: Optional[str] = None
    itens: List[ChecklistItemSchema] = Field(min_length=1)
    obrigatorio_ao_fechar: bool = True

    @field_validator("tipo_os")
    @classmethod
    def validar_tipo_os(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("corretiva", "preventiva", "preditiva"):
            raise ValueError("tipo_os deve ser corretiva, preventiva ou preditiva")
        return v


class ChecklistTemplateUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=200)
    tipo_os: Optional[str] = None
    itens: Optional[List[ChecklistItemSchema]] = None
    obrigatorio_ao_fechar: Optional[bool] = None
    ativo: Optional[bool] = None


class ChecklistTemplateResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organization_id: str
    nome: str
    tipo_os: Optional[str] = None
    equipamento_grupo_id: Optional[str] = None
    itens: List[Dict[str, Any]]
    obrigatorio_ao_fechar: bool
    ativo: bool
    criado_em: datetime


# ─── Checklist Execução ───────────────────────────────────────────────────────

class ChecklistRespostaItem(BaseModel):
    resposta: str = Field(pattern="^(ok|nok|na)$")
    observacao: Optional[str] = Field(default="", max_length=1000)


class ChecklistExecucaoCreate(BaseModel):
    template_id: str
    respostas: Dict[str, ChecklistRespostaItem]   # {str(item_id): {resposta, observacao}}
    assinatura_imagem_b64: Optional[str] = None   # base64 PNG do canvas de assinatura


class ChecklistExecucaoResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    os_id: str
    template_id: str
    respostas: Dict[str, Any]
    executado_por: str
    executado_em: datetime
    assinatura_imagem_key: Optional[str] = None


# ─── Assinatura de OS ─────────────────────────────────────────────────────────

class AssinaturaOSResponse(BaseModel):
    assinatura_hash: str
    assinado_por: str
    assinado_em: datetime
