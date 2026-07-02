"""
WhatsApp Business — notificações via Meta Cloud API (Fase 5.4)

Requer:
  - WHATSAPP_ACCESS_TOKEN env var (token permanente do app Meta)
  - WHATSAPP_PHONE_NUMBER_ID env var (Phone Number ID do remetente)
  - Template aprovado no Meta Business Suite

Fallback para Twilio se WHATSAPP_PROVIDER=twilio.
LGPD: só envia se user.whatsapp_optin=True e user.whatsapp_numero preenchido.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_META_API = "https://graph.facebook.com/v19.0"
_PROVIDER = os.environ.get("WHATSAPP_PROVIDER", "meta")  # meta | twilio


def _meta_send(to_number: str, template_name: str, params: list[str]) -> bool:
    """Envia mensagem via Meta Cloud API (template aprovado)."""
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        logger.debug("WhatsApp Meta não configurado (sem token/phone_id)")
        return False

    try:
        import httpx
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number.lstrip("+"),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "pt_BR"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in params],
                    }
                ],
            },
        }
        resp = httpx.post(
            f"{_META_API}/{phone_id}/messages",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.warning("WhatsApp Meta API error %s: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.warning("WhatsApp send error: %s", exc)
        return False


def _twilio_send(to_number: str, body_text: str) -> bool:
    """Envia via Twilio WhatsApp (sandox ou produção)."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_num = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # sandbox
    if not sid or not token:
        return False
    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            body=body_text,
            from_=from_num,
            to=f"whatsapp:{to_number}",
        )
        return True
    except Exception as exc:
        logger.warning("Twilio send error: %s", exc)
        return False


def send_notification(
    to_number: str,
    message_type: str,
    params: dict,
) -> bool:
    """
    Envia notificação WhatsApp.
    message_type mapeado para template Meta ou texto Twilio.
    Retorna True se enviado com sucesso.
    """
    if not to_number:
        return False

    # Templates disponíveis (devem estar aprovados no Meta Business Suite)
    TEMPLATES = {
        "os_critica":      ("aurix_os_critica",      [params.get("os_numero",""), params.get("equipamento","")]),
        "sla_estourado":   ("aurix_sla_estourado",   [params.get("os_numero",""), params.get("horas","")]),
        "os_aprovada":     ("aurix_os_aprovada",     [params.get("os_numero","")]),
        "alerta_preditivo":("aurix_alerta_pred",     [params.get("equipamento",""), params.get("severidade","")]),
    }

    if _PROVIDER == "twilio":
        texts = {
            "os_critica":       f"AURIX ⚠️ OS #{params.get('os_numero')} CRÍTICA — {params.get('equipamento')}",
            "sla_estourado":    f"AURIX ⏰ OS #{params.get('os_numero')} com SLA estourado há {params.get('horas')}h",
            "os_aprovada":      f"AURIX ✅ OS #{params.get('os_numero')} aprovada",
            "alerta_preditivo": f"AURIX 🔴 Alerta {params.get('severidade')} — {params.get('equipamento')}",
        }
        return _twilio_send(to_number, texts.get(message_type, "Notificação AURIX"))

    if message_type in TEMPLATES:
        tmpl, tmpl_params = TEMPLATES[message_type]
        return _meta_send(to_number, tmpl, tmpl_params)

    return False


def notify_os_critica(db, os_obj) -> bool:
    """Notifica técnico/líder via WhatsApp quando OS crítica é criada."""
    from ..models.core import User, UserRole
    lider = db.query(User).filter(
        User.organization_id == os_obj.organization_id,
        User.role.in_([UserRole.LIDER, UserRole.ADMIN]),
        User.ativo == True,
    ).first()

    if not lider:
        return False
    if not getattr(lider, "whatsapp_optin", False) or not getattr(lider, "whatsapp_numero", None):
        return False

    equip = db.query(__import__("app.models.core", fromlist=["Equipamento"]).Equipamento).filter(
        __import__("app.models.core", fromlist=["Equipamento"]).Equipamento.id == os_obj.equipamento_id
    ).first()

    return send_notification(
        to_number=lider.whatsapp_numero,
        message_type="os_critica",
        params={
            "os_numero": str(os_obj.numero),
            "equipamento": equip.nome if equip else "Desconhecido",
        },
    )
