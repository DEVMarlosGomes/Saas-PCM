"""
Schemas Pydantic v2 para o módulo de Almoxarifado.
Toda entrada do cliente é validada aqui antes de chegar ao service/router.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Fornecedor ────────────────────────────────────────────────────────────────

class FornecedorCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    cnpj: Optional[str] = Field(None, max_length=20)
    contato: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    telefone: Optional[str] = Field(None, max_length=30)
    observacoes: Optional[str] = None


class FornecedorUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    cnpj: Optional[str] = Field(None, max_length=20)
    contato: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    telefone: Optional[str] = Field(None, max_length=30)
    observacoes: Optional[str] = None
    ativo: Optional[bool] = None


class FornecedorResponse(BaseModel):
    id: str
    organization_id: str
    nome: str
    cnpj: Optional[str]
    contato: Optional[str]
    email: Optional[str]
    telefone: Optional[str]
    observacoes: Optional[str]
    ativo: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ── Peça ──────────────────────────────────────────────────────────────────────

class PecaCreate(BaseModel):
    codigo: str = Field(..., min_length=1, max_length=50)
    descricao: str = Field(..., min_length=2, max_length=500)
    unidade: str = Field(default="un", max_length=20)
    custo_unitario: Decimal = Field(..., ge=0, decimal_places=4)
    ponto_pedido: float = Field(default=0, ge=0)
    lote_economico: Optional[float] = Field(None, ge=0)
    fornecedor_principal_id: Optional[str] = None
    permitir_saldo_negativo: bool = False

    @field_validator("codigo")
    @classmethod
    def _codigo_upper(cls, v: str) -> str:
        return v.strip().upper()


class PecaUpdate(BaseModel):
    descricao: Optional[str] = Field(None, min_length=2, max_length=500)
    unidade: Optional[str] = Field(None, max_length=20)
    custo_unitario: Optional[Decimal] = Field(None, ge=0)
    ponto_pedido: Optional[float] = Field(None, ge=0)
    lote_economico: Optional[float] = Field(None, ge=0)
    fornecedor_principal_id: Optional[str] = None
    permitir_saldo_negativo: Optional[bool] = None
    ativo: Optional[bool] = None


class PecaResponse(BaseModel):
    id: str
    organization_id: str
    codigo: str
    descricao: str
    unidade: str
    custo_unitario: Decimal
    custo_medio: Decimal
    ponto_pedido: float
    lote_economico: Optional[float]
    fornecedor_principal_id: Optional[str]
    fornecedor_nome: Optional[str] = None   # enriquecido pelo router
    ativo: bool
    permitir_saldo_negativo: bool
    criado_em: datetime
    # Agregados calculados pelo router
    saldo_total: float = 0
    abaixo_ponto_pedido: bool = False

    model_config = {"from_attributes": True}


# ── Depósito ──────────────────────────────────────────────────────────────────

class DepositoCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255)
    localizacao: Optional[str] = Field(None, max_length=500)


class DepositoUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    localizacao: Optional[str] = Field(None, max_length=500)
    ativo: Optional[bool] = None


class DepositoResponse(BaseModel):
    id: str
    organization_id: str
    nome: str
    localizacao: Optional[str]
    ativo: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


# ── Saldo de Estoque ──────────────────────────────────────────────────────────

class SaldoResponse(BaseModel):
    peca_id: str
    peca_codigo: str
    peca_descricao: str
    peca_unidade: str
    deposito_id: str
    deposito_nome: str
    quantidade: float
    custo_medio: Decimal
    valor_total: Decimal
    ponto_pedido: float
    abaixo_ponto_pedido: bool
    atualizado_em: datetime

    model_config = {"from_attributes": True}


# ── Movimento de Estoque ──────────────────────────────────────────────────────

class MovimentoCreate(BaseModel):
    peca_id: str
    deposito_id: str
    tipo: str = Field(..., pattern="^(entrada|saida|ajuste)$")
    quantidade: float = Field(..., gt=0)
    custo_unitario: Optional[Decimal] = Field(None, ge=0)
    motivo: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def _valida_custo_entrada(self) -> "MovimentoCreate":
        if self.tipo == "entrada" and self.custo_unitario is None:
            raise ValueError("custo_unitario é obrigatório para entradas.")
        return self


class MovimentoResponse(BaseModel):
    id: str
    organization_id: str
    peca_id: str
    peca_codigo: str = ""
    peca_descricao: str = ""
    deposito_id: str
    deposito_nome: str = ""
    tipo: str
    quantidade: float
    custo_unitario: Optional[Decimal]
    custo_total: Optional[Decimal]
    os_id: Optional[str]
    usuario_id: Optional[str]
    usuario_nome: Optional[str] = None
    motivo: Optional[str]
    criado_em: datetime

    model_config = {"from_attributes": True}


# ── Consumo de peça em OS ─────────────────────────────────────────────────────

class ConsumoOSCreate(BaseModel):
    peca_id: str
    deposito_id: str
    quantidade: float = Field(..., gt=0)
    motivo: Optional[str] = Field(None, max_length=500)


class ConsumoOSResponse(BaseModel):
    movimento_id: str
    peca_id: str
    peca_codigo: str
    peca_descricao: str
    quantidade: float
    custo_unitario: Decimal
    custo_total: Decimal
    saldo_atual: float
    abaixo_ponto_pedido: bool


# ── Relatório de consumo por equipamento ──────────────────────────────────────

class ConsumoEquipamentoItem(BaseModel):
    equipamento_id: str
    equipamento_nome: str
    total_pecas: int
    custo_total: Decimal
    movimentos: list[MovimentoResponse] = []
