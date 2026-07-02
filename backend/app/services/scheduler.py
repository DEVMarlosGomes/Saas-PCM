"""
APScheduler jobs — processamento em background do AURIX.

Os 4 jobs são registrados no startup do server.py e executados com sessão
de banco dedicada via `run_job()`.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.core import (
    Equipamento, LeituraSensor, Organization, OrdemServico,
    PlanoPreventivo, PrioridadeOS, StatusOS, TipoOS, User, UserRole,
)
from ..deps import criar_notificacao, get_next_os_number
from . import preditivo_service

logger = logging.getLogger(__name__)


def job_processar_leituras(db: Session) -> None:
    """Processa leituras de sensor não processadas."""
    leituras = (
        db.query(LeituraSensor)
        .filter(LeituraSensor.processado == False)
        .limit(200)
        .all()
    )
    for leitura in leituras:
        try:
            preditivo_service.processar_leitura_preditiva(db, leitura)
        except Exception as exc:
            logger.warning("Erro ao processar leitura %s: %s", leitura.id, exc)


def job_atualizar_mttr_mtbf(db: Session) -> None:
    """Recalcula MTTR/MTBF/disponibilidade de todos os equipamentos ativos."""
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
                datas = sorted([o.created_at for o in os_list if o.created_at])
                if len(datas) >= 2:
                    span_h = (datas[-1] - datas[0]).total_seconds() / 3600
                    equip.mtbf_horas = round(span_h / len(os_list), 2)
                    total_parada = sum((o.tempo_total or 0) for o in os_list) / 60
                    equip.disponibilidade_percent = round(
                        max(0.0, (span_h - total_parada) / span_h * 100)
                        if span_h else 100.0,
                        1,
                    )
    db.commit()


def job_gerar_os_preventivas(db: Session) -> None:
    """Gera OS preventivas para planos com proxima_execucao dentro de 7 dias."""
    now = datetime.now(timezone.utc)
    planos = db.query(PlanoPreventivo).filter(
        PlanoPreventivo.ativo == True,
        PlanoPreventivo.proxima_execucao != None,
    ).all()
    for plano in planos:
        prazo = plano.proxima_execucao - timedelta(days=7)
        if now < prazo:
            continue
        existe = db.query(OrdemServico).filter(
            OrdemServico.organization_id == plano.organization_id,
            OrdemServico.equipamento_id == plano.equipamento_id,
            OrdemServico.tipo == TipoOS.PREVENTIVA,
            OrdemServico.created_at >= now - timedelta(days=7),
        ).first()
        if existe:
            continue
        try:
            admin = db.query(User).filter(
                User.organization_id == plano.organization_id,
                User.role == UserRole.ADMIN,
            ).first()
            if not admin:
                continue
            num = get_next_os_number(db, plano.organization_id)
            os_prev = OrdemServico(
                numero=num,
                organization_id=plano.organization_id,
                equipamento_id=plano.equipamento_id,
                tipo=TipoOS.PREVENTIVA,
                prioridade=PrioridadeOS.MEDIA,
                status=StatusOS.ABERTA,
                descricao=f"Manutenção preventiva — {plano.nome}",
                solicitante_id=admin.id,
            )
            db.add(os_prev)
            db.commit()
            logger.info("OS preventiva gerada: #%s", num)
        except Exception as exc:
            logger.warning("Erro ao gerar OS preventiva (plano %s): %s", plano.id, exc)


def job_auto_aprovar_sla(db: Session) -> None:
    """Auto-aprova OS em aguardando_revisao com review_deadline expirado."""
    now = datetime.now(timezone.utc)
    pendentes = db.query(OrdemServico).filter(
        OrdemServico.status == StatusOS.AGUARDANDO_REVISAO,
        OrdemServico.review_deadline != None,
        OrdemServico.review_deadline < now,
    ).all()
    for os_obj in pendentes:
        os_obj.status = StatusOS.REVISADA
        os_obj.revisado_at = now
        os_obj.auto_approved = True
        criar_notificacao(
            db,
            org_id=os_obj.organization_id,
            destinatario_id=os_obj.solicitante_id,
            tipo="os_revisada",
            titulo=f"OS #{os_obj.numero} auto-aprovada (SLA expirado)",
            mensagem=(
                f"A OS #{os_obj.numero} foi aprovada automaticamente "
                "por expiração do prazo de revisão."
            ),
            os_id=os_obj.id,
        )
    if pendentes:
        db.commit()
        logger.info("Auto-aprovadas %d OS por SLA expirado", len(pendentes))


def run_job(fn) -> None:
    """Executa um job com sessão de DB dedicada; falhas são silenciosas."""
    db = None
    try:
        db = SessionLocal()
        fn(db)
    except Exception as exc:
        logger.warning("Job %s falhou: %s", fn.__name__, exc)
    finally:
        if db:
            db.close()
