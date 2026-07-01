"""
Serviço de armazenamento de arquivos — S3/R2 via boto3.

Regras de segurança (ASVS V12):
- Validação dupla: Content-Type declarado + magic bytes do conteúdo real.
- Allowlist estrita: apenas JPEG, PNG, WebP e PDF.
- Arquivo renomeado para UUID no storage — nome original vai apenas como metadado.
- URLs de download pré-assinadas com expiração curta (STORAGE_PRESIGN_EXPIRES seg.).
- Content-Disposition: attachment para bloquear execução de HTML/SVG.
- Nunca servir o arquivo do mesmo domínio da aplicação.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Limites ──────────────────────────────────────────────────────────────────
# Lidos em runtime para que possam vir de env vars via settings
MAX_FILE_BYTES: int = int(os.environ.get("STORAGE_MAX_FILE_BYTES", str(20 * 1024 * 1024)))  # 20 MB
MAX_ANEXOS_PER_OS: int = int(os.environ.get("STORAGE_MAX_ANEXOS_PER_OS", "20"))
PRESIGN_EXPIRES: int = int(os.environ.get("STORAGE_PRESIGN_EXPIRES", "300"))  # 5 min

# ─── Allowlist de tipos ───────────────────────────────────────────────────────
ALLOWED_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

# Magic bytes para validação de conteúdo real (evita bypass via extensão falsa)
_MAGIC: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png":  b"\x89PNG\r\n\x1a\n",
    "application/pdf": b"%PDF",
}


class StorageError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def validate_upload(content: bytes, declared_mime: str, filename: str) -> str:
    """
    Valida mime declarado e magic bytes do conteúdo.
    Retorna o mime validado ou levanta StorageError.
    """
    if declared_mime not in ALLOWED_MIMES:
        raise StorageError(
            f"Tipo de arquivo não permitido: {declared_mime}. "
            "Permitidos: JPEG, PNG, WebP, PDF."
        )

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise StorageError(f"Extensão não permitida: {ext}.")

    if len(content) == 0:
        raise StorageError("Arquivo vazio.")

    if len(content) > MAX_FILE_BYTES:
        mb = MAX_FILE_BYTES // (1024 * 1024)
        raise StorageError(f"Arquivo excede o limite de {mb} MB.", status_code=413)

    # Validação de magic bytes
    if declared_mime == "image/webp":
        # WebP: bytes 0-3 = RIFF, bytes 8-11 = WEBP
        if len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
            raise StorageError("Conteúdo não corresponde a um arquivo WebP válido.")
    else:
        magic = _MAGIC.get(declared_mime)
        if magic and not content.startswith(magic):
            raise StorageError(
                f"Conteúdo do arquivo não corresponde ao tipo declarado ({declared_mime}). "
                "Possível tentativa de spoofing de extensão."
            )

    return declared_mime


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _get_s3_client():
    """Retorna cliente boto3 configurado via env vars."""
    import boto3

    endpoint = os.environ.get("S3_ENDPOINT_URL") or None
    kwargs: dict = {
        "aws_access_key_id": os.environ.get("S3_ACCESS_KEY_ID", ""),
        "aws_secret_access_key": os.environ.get("S3_SECRET_ACCESS_KEY", ""),
        "region_name": os.environ.get("S3_REGION", "us-east-1"),
    }
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _bucket() -> str:
    b = os.environ.get("S3_BUCKET", "")
    if not b:
        raise StorageError(
            "Storage não configurado. Defina S3_BUCKET, S3_ACCESS_KEY_ID e "
            "S3_SECRET_ACCESS_KEY nas variáveis de ambiente.",
            status_code=503,
        )
    return b


def upload_file(
    content: bytes,
    mime: str,
    organization_id: str,
    os_id: str,
) -> str:
    """
    Faz upload do conteúdo para S3 e retorna a storage_key.
    A key segue o padrão: <org_id>/<os_id>/<uuid>
    Extensão é derivada do mime validado — nunca do nome original.
    """
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }
    ext = ext_map.get(mime, ".bin")
    file_uuid = uuid.uuid4().hex
    storage_key = f"anexos/{organization_id}/{os_id}/{file_uuid}{ext}"

    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=_bucket(),
            Key=storage_key,
            Body=content,
            ContentType=mime,
            # Content-Disposition: attachment previne que browser execute HTML/SVG
            ContentDisposition="attachment",
            # Server-Side Encryption
            ServerSideEncryption="AES256",
        )
        logger.info("[STORAGE] Upload OK: %s (%d bytes)", storage_key, len(content))
    except StorageError:
        raise
    except Exception as exc:
        logger.error("[STORAGE] Upload falhou: %s", exc)
        raise StorageError("Falha no upload do arquivo. Tente novamente.", status_code=500)

    return storage_key


def generate_presigned_url(storage_key: str, expires: int = PRESIGN_EXPIRES) -> str:
    """Gera URL pré-assinada com expiração curta para download seguro."""
    try:
        client = _get_s3_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": _bucket(),
                "Key": storage_key,
                "ResponseContentDisposition": "attachment",
            },
            ExpiresIn=expires,
        )
        return url
    except StorageError:
        raise
    except Exception as exc:
        logger.error("[STORAGE] Presign falhou para %s: %s", storage_key, exc)
        raise StorageError("Falha ao gerar URL de download.", status_code=500)


def delete_file(storage_key: str) -> None:
    """Remove arquivo do S3 (chamado em soft-delete confirmado)."""
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=_bucket(), Key=storage_key)
        logger.info("[STORAGE] Deletado: %s", storage_key)
    except StorageError:
        raise
    except Exception as exc:
        logger.warning("[STORAGE] Falha ao deletar %s: %s", storage_key, exc)
