"""
Event bus in-process para Server-Sent Events (SSE).

Cada conexão SSE registra uma asyncio.Queue identificada pelo org_id.
Ao publicar um evento (OS mudou, notificação criada, estoque abaixo do ponto),
percorre todas as filas do tenant e insere a mensagem — zero vazamento entre orgs.

Isolamento de tenant:
- subscribe(org_id) → cria fila associada à org
- publish(org_id, ...) → entrega apenas às filas daquela org
- Conexões de orgs distintas nunca compartilham fila

Limitações desta implementação:
- Funciona em processo único (Uvicorn sem workers múltiplos).
- Para múltiplos workers: trocar por Redis Pub/Sub ou similar.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import DefaultDict, Set

logger = logging.getLogger(__name__)

# {org_id: {Queue, ...}}
_channels: DefaultDict[str, Set[asyncio.Queue]] = defaultdict(set)


def subscribe(org_id: str) -> asyncio.Queue:
    """Registra nova fila para o tenant e retorna ela."""
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _channels[str(org_id)].add(q)
    logger.debug("[SSE] +subscriber org=%s total=%d", org_id, len(_channels[str(org_id)]))
    return q


def unsubscribe(org_id: str, q: asyncio.Queue) -> None:
    """Remove fila do tenant (chamado ao fechar a conexão SSE)."""
    _channels[str(org_id)].discard(q)
    if not _channels[str(org_id)]:
        _channels.pop(str(org_id), None)
    logger.debug("[SSE] -subscriber org=%s", org_id)


async def publish(org_id: str, event_type: str, payload: dict) -> None:
    """Publica evento apenas para os subscribers do tenant (async)."""
    message = json.dumps({"type": event_type, "data": payload})
    dead: list[asyncio.Queue] = []
    for q in list(_channels.get(str(org_id), set())):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(q)  # conexão lenta — remover
    for q in dead:
        _channels[str(org_id)].discard(q)


def publish_sync(org_id: str, event_type: str, payload: dict) -> None:
    """
    Versão thread-safe para chamar de código síncrono (endpoints FastAPI normais).
    Agenda a publicação no event loop em execução.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(publish(str(org_id), event_type, payload))
        )
    except RuntimeError:
        # Nenhum loop rodando (ex: teste unitário) — ignora silenciosamente
        pass
