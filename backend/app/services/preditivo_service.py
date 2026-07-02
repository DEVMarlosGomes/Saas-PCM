"""
Motor preditivo — processamento de leituras de sensor e geração de alertas.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models.core import (
    AlertaPreditivo, ConfiguracaoMonitoramento, Equipamento,
    LeituraSensor, Organization, User, UserRole,
)
from ..deps import criar_notificacao, send_email_notification


def _linear_slope(values: list) -> float:
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
    if not historico or slope <= 0:
        return None
    ultimo = historico[-1]
    if ultimo >= threshold_critico:
        return 0
    return max(0, int((threshold_critico - ultimo) / slope))


def processar_leitura_preditiva(db: Session, leitura: LeituraSensor):
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

    tendencia = "CRITICA" if slope > 0.5 else ("CRESCENTE" if slope > 0.1 else "ESTAVEL")
    rul = _estimar_rul(historico, config.threshold_critico, slope)

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
        f"(limite {severidade.lower()}: "
        f"{config.threshold_atencao if severidade == 'ATENCAO' else config.threshold_critico})"
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

    admin = db.query(User).filter(
        User.organization_id == leitura.organization_id,
        User.role == UserRole.ADMIN, User.ativo == True,
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
