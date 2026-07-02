"""
Testes unitários de estoque — Fase 4.3

Cobre: custo médio ponderado, EstoqueError, baixa com saldo insuficiente.
Não requer banco de dados real — usa mocks para queries SQLAlchemy.
"""
import os
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET", "test-secret-32-characters-for-test!!")

from app.services.estoque_service import EstoqueError


# ── Custo médio ponderado ─────────────────────────────────────────────────────

def _make_movimento(quantidade, custo_unitario, tipo="ENTRADA"):
    m = MagicMock()
    m.quantidade = quantidade
    m.custo_unitario = Decimal(str(custo_unitario))
    m.tipo = tipo
    return m


def test_recalcular_custo_medio_sem_entradas_retorna_custo_cadastrado():
    from app.services.estoque_service import recalcular_custo_medio
    from app.models.estoque import TipoMovimento

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    peca = MagicMock()
    peca.id = "peca-1"
    peca.custo_unitario = Decimal("25.00")

    resultado = recalcular_custo_medio(db, peca, "deposito-1", "org-1")
    assert resultado == Decimal("25.00")


def test_recalcular_custo_medio_uma_entrada():
    from app.services.estoque_service import recalcular_custo_medio
    from app.models.estoque import TipoMovimento

    db = MagicMock()
    entradas = [_make_movimento(10, "50.00")]
    db.query.return_value.filter.return_value.all.return_value = entradas

    peca = MagicMock()
    peca.id = "peca-2"
    peca.custo_unitario = Decimal("0")

    resultado = recalcular_custo_medio(db, peca, "dep", "org")
    assert resultado == Decimal("50.00")


def test_recalcular_custo_medio_ponderado():
    from app.services.estoque_service import recalcular_custo_medio

    db = MagicMock()
    # 10 unidades a R$10 + 20 unidades a R$20 = R$500 / 30 = R$16.67
    entradas = [
        _make_movimento(10, "10.00"),
        _make_movimento(20, "20.00"),
    ]
    db.query.return_value.filter.return_value.all.return_value = entradas

    peca = MagicMock()
    peca.id = "peca-3"
    peca.custo_unitario = Decimal("0")

    resultado = recalcular_custo_medio(db, peca, "dep", "org")
    expected = Decimal("500") / Decimal("30")
    assert abs(resultado - expected) < Decimal("0.01")


# ── EstoqueError ──────────────────────────────────────────────────────────────

def test_estoque_error_has_status_code():
    err = EstoqueError("Saldo insuficiente", status_code=422)
    assert str(err) == "Saldo insuficiente"
    assert err.status_code == 422


def test_estoque_error_default_status_code():
    err = EstoqueError("Erro genérico")
    assert err.status_code == 422


# ── Saída (baixa) atômica: saldo insuficiente ────────────────────────────────

def test_saida_raises_when_insufficient_stock():
    """
    Simula _get_or_create_saldo retornando saldo=0 — registrar_saida deve levantar EstoqueError.
    """
    from app.services.estoque_service import registrar_saida

    db = MagicMock()

    saldo = MagicMock()
    saldo.quantidade = 0.0
    saldo.id = "saldo-1"

    peca = MagicMock()
    peca.id = "peca-1"
    peca.codigo = "EQ-001"
    peca.descricao = "Rolamento SKF"
    peca.unidade = "un"
    peca.permitir_saldo_negativo = False

    deposito = MagicMock()
    deposito.id = "dep-1"

    with patch("app.services.estoque_service._get_or_create_saldo", return_value=saldo):
        with pytest.raises(EstoqueError, match="insuficiente"):
            registrar_saida(
                db=db,
                peca=peca,
                deposito=deposito,
                quantidade=5.0,
                usuario_id="user-1",
                org_id="org-1",
                os_id="os-1",
                motivo="Consumo em OS",
            )


def test_saida_succeeds_when_sufficient_stock():
    from app.services.estoque_service import registrar_saida

    db = MagicMock()

    saldo = MagicMock()
    saldo.quantidade = 10.0

    peca = MagicMock()
    peca.id = "peca-1"
    peca.codigo = "EQ-001"
    peca.descricao = "Rolamento SKF"
    peca.unidade = "un"
    peca.permitir_saldo_negativo = False
    peca.custo_medio = Decimal("100.00")
    peca.custo_unitario = Decimal("100.00")

    deposito = MagicMock()
    deposito.id = "dep-1"

    with patch("app.services.estoque_service._get_or_create_saldo", return_value=saldo):
        mov, sal = registrar_saida(
            db=db,
            peca=peca,
            deposito=deposito,
            quantidade=3.0,
            usuario_id="user-1",
            org_id="org-1",
            os_id="os-1",
            motivo="Consumo",
        )

    assert saldo.quantidade == 7.0
    db.add.assert_called()
    db.flush.assert_called()


def test_saida_rejects_zero_quantity():
    from app.services.estoque_service import registrar_saida

    db = MagicMock()
    peca = MagicMock()
    deposito = MagicMock()

    with pytest.raises(EstoqueError, match="maior que zero"):
        registrar_saida(db, peca, deposito, 0, "user", "org")
