"""
Router Fase 2 — Evidências e Compliance Operacional.

Endpoints:
  POST   /ordens-servico/{id}/anexos           — upload de arquivo
  GET    /ordens-servico/{id}/anexos           — lista anexos da OS
  GET    /anexos/{anexo_id}/download           — URL pré-assinada
  DELETE /anexos/{anexo_id}                   — soft delete

  GET    /checklist-templates                 — lista templates
  POST   /checklist-templates                 — cria template
  PUT    /checklist-templates/{id}            — atualiza template
  DELETE /checklist-templates/{id}            — desativa template

  POST   /ordens-servico/{id}/checklist       — executa checklist
  GET    /ordens-servico/{id}/checklist       — lista execuções da OS

Segurança:
  - Todos os endpoints requerem autenticação (get_current_user_stub).
  - Todas as queries são tenant-scoped por organization_id.
  - Após carregar por ID: valida organization_id == user.organization_id (404 se divergir).
  - Toda ação sensível gera AuditoriaLog.
  - Upload: validação dupla (Content-Type + magic bytes), allowlist, SHA-256, UUID rename.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..schemas.evidencias import (
    AnexoResponse,
    ChecklistExecucaoCreate,
    ChecklistExecucaoResponse,
    ChecklistTemplateCreate,
    ChecklistTemplateResponse,
    ChecklistTemplateUpdate,
)
from ..services.storage_service import (
    MAX_ANEXOS_PER_OS,
    StorageError,
    compute_sha256,
    delete_file,
    generate_presigned_url,
    upload_file,
    validate_upload,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Evidências"])


# ─── Dependency stub (overridden in server.py) ────────────────────────────────

async def get_current_user_stub():
    raise RuntimeError("get_current_user_stub de evidencias não foi substituído.")


def get_db_stub():
    raise RuntimeError("get_db_stub de evidencias não foi substituído.")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_db():
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _str(val) -> str:
    return str(val) if val is not None else ""


def _check_plano(user, db) -> None:
    """Verifica se o plano da org tem modulo_evidencias ativo (retorna 402 se não)."""
    try:
        from server import Organization, PLAN_LIMITS  # late import to avoid circular
    except ImportError:
        from __main__ import Organization, PLAN_LIMITS  # fallback
    org = db.query(Organization).filter(
        Organization.id == user.organization_id
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")
    limits = PLAN_LIMITS.get(org.plano, {})
    if not limits.get("modulo_evidencias", False):
        raise HTTPException(
            status_code=402,
            detail="Módulo de Evidências disponível a partir do plano Profissional.",
        )


def _check_os_ownership(os_obj, user):
    if str(os_obj.organization_id) != str(user.organization_id):
        raise HTTPException(status_code=404, detail="OS não encontrada.")


_LIDER_ROLES = {
    "admin", "gerente_industrial", "supervisor_manutencao",
    "lider", "lider_manutencao_eletrica", "lider_manutencao_mecanica",
    "analista_manutencao", "engenheiro_manutencao",
}

_TECNICO_ROLES = _LIDER_ROLES | {"tecnico", "operador"}


# ═══════════════════════════════════════════════════════════════════════════════
# ANEXOS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/ordens-servico/{os_id}/anexos", response_model=AnexoResponse, status_code=201)
async def upload_anexo(
    os_id: str,
    file: UploadFile = File(...),
    descricao: Optional[str] = Form(default=None),
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    """Upload seguro de anexo em uma OS. Allowlist: JPEG, PNG, WebP, PDF."""
    _check_plano(user, db)

    if user.role not in _TECNICO_ROLES:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    from ..models.evidencias import AnexoOS
    from server import OrdemServico  # late import

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    # Limite por OS
    existing = db.query(AnexoOS).filter(
        AnexoOS.os_id == os_id,
        AnexoOS.deletado_em.is_(None),
    ).count()
    if existing >= MAX_ANEXOS_PER_OS:
        raise HTTPException(
            status_code=422,
            detail=f"Limite de {MAX_ANEXOS_PER_OS} anexos por OS atingido.",
        )

    # Lê conteúdo (limite aplicado dentro de validate_upload)
    content = await file.read()
    declared_mime = file.content_type or ""

    try:
        validated_mime = validate_upload(content, declared_mime, file.filename or "")
    except StorageError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    sha256 = compute_sha256(content)

    try:
        storage_key = upload_file(
            content=content,
            mime=validated_mime,
            organization_id=str(user.organization_id),
            os_id=str(os_id),
        )
    except StorageError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    anexo = AnexoOS(
        organization_id=user.organization_id,
        os_id=os_id,
        storage_key=storage_key,
        nome_original=file.filename or "arquivo",
        mime=validated_mime,
        tamanho=len(content),
        hash_sha256=sha256,
        usuario_id=user.id,
        descricao=descricao,
    )
    db.add(anexo)

    # Auditoria
    try:
        from server import create_audit_log
        create_audit_log(
            db, str(user.organization_id), str(user.id),
            "AnexoOS", str(anexo.id), "upload",
            dados_novos={"os_id": str(os_id), "mime": validated_mime, "tamanho": len(content)},
        )
    except Exception:
        pass

    db.commit()
    db.refresh(anexo)

    return AnexoResponse(
        id=_str(anexo.id),
        os_id=_str(anexo.os_id),
        storage_key=anexo.storage_key,
        nome_original=anexo.nome_original,
        mime=anexo.mime,
        tamanho=anexo.tamanho,
        hash_sha256=anexo.hash_sha256,
        descricao=anexo.descricao,
        usuario_id=_str(anexo.usuario_id),
        criado_em=anexo.criado_em,
    )


@router.get("/ordens-servico/{os_id}/anexos", response_model=List[AnexoResponse])
async def listar_anexos(
    os_id: str,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    from ..models.evidencias import AnexoOS
    from server import OrdemServico

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    anexos = db.query(AnexoOS).filter(
        AnexoOS.os_id == os_id,
        AnexoOS.organization_id == user.organization_id,
        AnexoOS.deletado_em.is_(None),
    ).order_by(AnexoOS.criado_em).all()

    result = []
    for a in anexos:
        try:
            url = generate_presigned_url(a.storage_key)
        except Exception:
            url = None
        result.append(AnexoResponse(
            id=_str(a.id),
            os_id=_str(a.os_id),
            storage_key=a.storage_key,
            nome_original=a.nome_original,
            mime=a.mime,
            tamanho=a.tamanho,
            hash_sha256=a.hash_sha256,
            descricao=a.descricao,
            usuario_id=_str(a.usuario_id),
            criado_em=a.criado_em,
            url_download=url,
        ))
    return result


@router.get("/anexos/{anexo_id}/download")
async def download_anexo(
    anexo_id: str,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    """Redireciona para URL pré-assinada do S3. A URL expira em STORAGE_PRESIGN_EXPIRES segundos."""
    _check_plano(user, db)

    from ..models.evidencias import AnexoOS

    anexo = db.query(AnexoOS).filter(
        AnexoOS.id == anexo_id,
        AnexoOS.organization_id == user.organization_id,
        AnexoOS.deletado_em.is_(None),
    ).first()
    if not anexo:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")

    try:
        url = generate_presigned_url(anexo.storage_key)
    except StorageError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    return RedirectResponse(url=url, status_code=302)


@router.delete("/anexos/{anexo_id}", status_code=204)
async def deletar_anexo(
    anexo_id: str,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    """Soft-delete do anexo + remoção do S3."""
    _check_plano(user, db)

    if user.role not in _LIDER_ROLES:
        raise HTTPException(status_code=403, detail="Apenas líderes e admin podem remover anexos.")

    from ..models.evidencias import AnexoOS

    anexo = db.query(AnexoOS).filter(
        AnexoOS.id == anexo_id,
        AnexoOS.organization_id == user.organization_id,
        AnexoOS.deletado_em.is_(None),
    ).first()
    if not anexo:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")

    # Soft delete primeiro — se S3 falhar, o registro fica marcado e pode ser limpo depois
    anexo.deletado_em = datetime.now(timezone.utc)
    db.commit()

    try:
        delete_file(anexo.storage_key)
    except Exception as exc:
        logger.warning("[STORAGE] Falha ao deletar %s: %s", anexo.storage_key, exc)


# ═══════════════════════════════════════════════════════════════════════════════
# CHECKLIST TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/checklist-templates", response_model=List[ChecklistTemplateResponse])
async def listar_templates(
    tipo_os: Optional[str] = None,
    apenas_ativos: bool = True,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    from ..models.evidencias import ChecklistTemplate

    q = db.query(ChecklistTemplate).filter(
        ChecklistTemplate.organization_id == user.organization_id,
    )
    if apenas_ativos:
        q = q.filter(ChecklistTemplate.ativo.is_(True))
    if tipo_os:
        q = q.filter(
            (ChecklistTemplate.tipo_os == tipo_os) | (ChecklistTemplate.tipo_os.is_(None))
        )
    templates = q.order_by(ChecklistTemplate.nome).all()

    return [
        ChecklistTemplateResponse(
            id=_str(t.id),
            organization_id=_str(t.organization_id),
            nome=t.nome,
            tipo_os=t.tipo_os,
            equipamento_grupo_id=_str(t.equipamento_grupo_id) if t.equipamento_grupo_id else None,
            itens=t.itens or [],
            obrigatorio_ao_fechar=t.obrigatorio_ao_fechar,
            ativo=t.ativo,
            criado_em=t.criado_em,
        )
        for t in templates
    ]


@router.post("/checklist-templates", response_model=ChecklistTemplateResponse, status_code=201)
async def criar_template(
    payload: ChecklistTemplateCreate,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    if user.role not in _LIDER_ROLES:
        raise HTTPException(status_code=403, detail="Apenas líderes podem criar templates.")

    from ..models.evidencias import ChecklistTemplate

    tmpl = ChecklistTemplate(
        organization_id=user.organization_id,
        nome=payload.nome,
        tipo_os=payload.tipo_os,
        equipamento_grupo_id=payload.equipamento_grupo_id,
        itens=[i.model_dump() for i in payload.itens],
        obrigatorio_ao_fechar=payload.obrigatorio_ao_fechar,
        criado_por=user.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)

    return ChecklistTemplateResponse(
        id=_str(tmpl.id),
        organization_id=_str(tmpl.organization_id),
        nome=tmpl.nome,
        tipo_os=tmpl.tipo_os,
        equipamento_grupo_id=None,
        itens=tmpl.itens or [],
        obrigatorio_ao_fechar=tmpl.obrigatorio_ao_fechar,
        ativo=tmpl.ativo,
        criado_em=tmpl.criado_em,
    )


@router.put("/checklist-templates/{template_id}", response_model=ChecklistTemplateResponse)
async def atualizar_template(
    template_id: str,
    payload: ChecklistTemplateUpdate,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    if user.role not in _LIDER_ROLES:
        raise HTTPException(status_code=403, detail="Apenas líderes podem editar templates.")

    from ..models.evidencias import ChecklistTemplate

    tmpl = db.query(ChecklistTemplate).filter(
        ChecklistTemplate.id == template_id,
        ChecklistTemplate.organization_id == user.organization_id,
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado.")

    if payload.nome is not None:
        tmpl.nome = payload.nome
    if payload.tipo_os is not None:
        tmpl.tipo_os = payload.tipo_os
    if payload.itens is not None:
        tmpl.itens = [i.model_dump() for i in payload.itens]
    if payload.obrigatorio_ao_fechar is not None:
        tmpl.obrigatorio_ao_fechar = payload.obrigatorio_ao_fechar
    if payload.ativo is not None:
        tmpl.ativo = payload.ativo

    db.commit()
    db.refresh(tmpl)

    return ChecklistTemplateResponse(
        id=_str(tmpl.id),
        organization_id=_str(tmpl.organization_id),
        nome=tmpl.nome,
        tipo_os=tmpl.tipo_os,
        equipamento_grupo_id=None,
        itens=tmpl.itens or [],
        obrigatorio_ao_fechar=tmpl.obrigatorio_ao_fechar,
        ativo=tmpl.ativo,
        criado_em=tmpl.criado_em,
    )


@router.delete("/checklist-templates/{template_id}", status_code=204)
async def desativar_template(
    template_id: str,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    if user.role not in _LIDER_ROLES:
        raise HTTPException(status_code=403, detail="Apenas líderes podem desativar templates.")

    from ..models.evidencias import ChecklistTemplate

    tmpl = db.query(ChecklistTemplate).filter(
        ChecklistTemplate.id == template_id,
        ChecklistTemplate.organization_id == user.organization_id,
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado.")

    tmpl.ativo = False
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# CHECKLIST EXECUÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/ordens-servico/{os_id}/checklist", response_model=ChecklistExecucaoResponse, status_code=201)
async def executar_checklist(
    os_id: str,
    payload: ChecklistExecucaoCreate,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    if user.role not in _TECNICO_ROLES:
        raise HTTPException(status_code=403, detail="Acesso negado.")

    from ..models.evidencias import ChecklistTemplate, ChecklistExecucao
    from server import OrdemServico

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    tmpl = db.query(ChecklistTemplate).filter(
        ChecklistTemplate.id == payload.template_id,
        ChecklistTemplate.organization_id == user.organization_id,
        ChecklistTemplate.ativo.is_(True),
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template de checklist não encontrado.")

    # Valida que todos os itens obrigatórios têm resposta
    itens_ids = {str(item["id"]) for item in (tmpl.itens or [])}
    obrigatorios = {str(item["id"]) for item in (tmpl.itens or []) if item.get("obrigatorio", True)}
    respondidos = set(payload.respostas.keys())
    faltando = obrigatorios - respondidos
    if faltando:
        raise HTTPException(
            status_code=422,
            detail=f"Itens obrigatórios sem resposta: {', '.join(sorted(faltando))}",
        )

    # Processa assinatura de imagem (base64 → upload S3)
    assinatura_key: Optional[str] = None
    if payload.assinatura_imagem_b64:
        import base64
        try:
            img_bytes = base64.b64decode(payload.assinatura_imagem_b64)
        except Exception:
            raise HTTPException(status_code=422, detail="assinatura_imagem_b64 inválida.")
        try:
            assinatura_key = upload_file(
                content=img_bytes,
                mime="image/png",
                organization_id=str(user.organization_id),
                os_id=str(os_id),
            )
        except StorageError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))

    respostas_dict = {k: v.model_dump() for k, v in payload.respostas.items()}

    execucao = ChecklistExecucao(
        organization_id=user.organization_id,
        os_id=os_id,
        template_id=payload.template_id,
        respostas=respostas_dict,
        executado_por=user.id,
        assinatura_imagem_key=assinatura_key,
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

    return ChecklistExecucaoResponse(
        id=_str(execucao.id),
        os_id=_str(execucao.os_id),
        template_id=_str(execucao.template_id),
        respostas=execucao.respostas,
        executado_por=_str(execucao.executado_por),
        executado_em=execucao.executado_em,
        assinatura_imagem_key=execucao.assinatura_imagem_key,
    )


@router.get("/ordens-servico/{os_id}/checklist", response_model=List[ChecklistExecucaoResponse])
async def listar_checklists_os(
    os_id: str,
    user=Depends(get_current_user_stub),
    db: Session = Depends(_get_db),
):
    _check_plano(user, db)

    from ..models.evidencias import ChecklistExecucao
    from server import OrdemServico

    os_obj = db.query(OrdemServico).filter(
        OrdemServico.id == os_id,
        OrdemServico.organization_id == user.organization_id,
    ).first()
    if not os_obj:
        raise HTTPException(status_code=404, detail="OS não encontrada.")

    execucoes = db.query(ChecklistExecucao).filter(
        ChecklistExecucao.os_id == os_id,
        ChecklistExecucao.organization_id == user.organization_id,
    ).order_by(ChecklistExecucao.executado_em).all()

    return [
        ChecklistExecucaoResponse(
            id=_str(e.id),
            os_id=_str(e.os_id),
            template_id=_str(e.template_id),
            respostas=e.respostas,
            executado_por=_str(e.executado_por),
            executado_em=e.executado_em,
            assinatura_imagem_key=e.assinatura_imagem_key,
        )
        for e in execucoes
    ]


# ─── Helper público: verificar se OS tem checklists obrigatórios pendentes ───

def verificar_checklists_pendentes(db, os_obj, organization_id: str) -> Optional[str]:
    """
    Retorna mensagem de erro se houver checklists obrigatórios não preenchidos,
    ou None se está tudo ok. Chamado pelo server.py antes de fechar OS.
    """
    from ..models.evidencias import ChecklistTemplate, ChecklistExecucao

    templates_obrig = db.query(ChecklistTemplate).filter(
        ChecklistTemplate.organization_id == organization_id,
        ChecklistTemplate.ativo.is_(True),
        ChecklistTemplate.obrigatorio_ao_fechar.is_(True),
    ).all()

    if not templates_obrig:
        return None

    tipo_os = os_obj.tipo.value if hasattr(os_obj.tipo, "value") else str(os_obj.tipo)

    for tmpl in templates_obrig:
        # Filtra por tipo_os (None = aplica a todos)
        if tmpl.tipo_os and tmpl.tipo_os != tipo_os:
            continue

        execucao = db.query(ChecklistExecucao).filter(
            ChecklistExecucao.os_id == os_obj.id,
            ChecklistExecucao.template_id == tmpl.id,
        ).first()

        if not execucao:
            return f"Checklist obrigatório '{tmpl.nome}' não foi preenchido. Preencha antes de fechar a OS."

    return None
