"""
Testes unitários de upload / validação de arquivos — Fase 4.3

Cobre: magic bytes (JPEG, PNG, WebP, PDF), extensão, MIME, tamanho.
Não requer servidor, S3 ou banco de dados.
"""
import pytest
from app.services.storage_service import validate_upload, StorageError


# ── Helpers: bytes mínimos de cada tipo ───────────────────────────────────────

def _jpeg(size=100) -> bytes:
    header = b"\xff\xd8\xff\xe0" + b"\x00" * (size - 4)
    return header


def _png(size=100) -> bytes:
    header = b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8)
    return header


def _pdf(size=100) -> bytes:
    return b"%PDF-1.4" + b"\x00" * (size - 8)


def _webp(size=100) -> bytes:
    return b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * (size - 12)


# ── Tipos válidos ─────────────────────────────────────────────────────────────

def test_valid_jpeg():
    result = validate_upload(_jpeg(), "image/jpeg", "foto.jpg")
    assert result == "image/jpeg"


def test_valid_png():
    result = validate_upload(_png(), "image/png", "imagem.png")
    assert result == "image/png"


def test_valid_pdf():
    result = validate_upload(_pdf(), "application/pdf", "laudo.pdf")
    assert result == "application/pdf"


def test_valid_webp():
    result = validate_upload(_webp(), "image/webp", "thumb.webp")
    assert result == "image/webp"


# ── MIME não permitido ────────────────────────────────────────────────────────

def test_reject_text_plain():
    with pytest.raises(StorageError, match="não permitido"):
        validate_upload(b"hello world", "text/plain", "script.txt")


def test_reject_svg():
    with pytest.raises(StorageError, match="não permitido"):
        validate_upload(b"<svg/>", "image/svg+xml", "icon.svg")


def test_reject_exe():
    with pytest.raises(StorageError, match="não permitido"):
        validate_upload(b"MZ\x90\x00", "application/octet-stream", "virus.exe")


# ── Extensão incorreta ────────────────────────────────────────────────────────

def test_reject_wrong_extension():
    with pytest.raises(StorageError, match="Extensão"):
        validate_upload(_jpeg(), "image/jpeg", "foto.gif")


def test_reject_no_extension():
    with pytest.raises(StorageError, match="Extensão"):
        validate_upload(_jpeg(), "image/jpeg", "foto")


# ── Magic bytes errados ───────────────────────────────────────────────────────

def test_reject_jpeg_with_wrong_magic():
    # Declara JPEG mas conteúdo é texto puro
    with pytest.raises(StorageError, match="não corresponde"):
        validate_upload(b"FAKEJPEGCONTENT" * 10, "image/jpeg", "fake.jpg")


def test_reject_pdf_with_wrong_magic():
    with pytest.raises(StorageError, match="não corresponde"):
        validate_upload(b"NOTAPDF" * 10, "application/pdf", "fake.pdf")


def test_reject_webp_with_wrong_magic():
    with pytest.raises(StorageError, match="WebP"):
        validate_upload(b"NOTAWEBPFILE" * 10, "image/webp", "fake.webp")


# ── Arquivo vazio ─────────────────────────────────────────────────────────────

def test_reject_empty_file():
    with pytest.raises(StorageError, match="vazio"):
        validate_upload(b"", "image/jpeg", "foto.jpg")


# ── Arquivo muito grande ──────────────────────────────────────────────────────

def test_reject_oversized_file():
    oversized = _jpeg(size=21 * 1024 * 1024)  # 21 MB
    with pytest.raises(StorageError, match="limite"):
        validate_upload(oversized, "image/jpeg", "grande.jpg")
