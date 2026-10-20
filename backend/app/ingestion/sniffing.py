"""Content-signature format detection. Extensions are never trusted alone."""
from app.ingestion.constants import (
    FMT_CSV,
    FMT_HTML_TABLE,
    FMT_NATIVE_XLS,
    FMT_PDF,
    FMT_UNKNOWN,
    FMT_XLSX,
)

_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy XLS (and other OLE2) container
_PDF = b"%PDF-"
_ZIP = b"PK\x03\x04"  # xlsx/docx container


def detect_format(path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if head.startswith(_OLE2):
        return FMT_NATIVE_XLS
    if head.startswith(_ZIP):
        return FMT_XLSX
    if head.startswith(_PDF):
        return FMT_PDF
    stripped = head.lstrip()
    if stripped[:1] in (b"<", b"#") or _looks_like_html(stripped):
        return FMT_HTML_TABLE
    # CSV-ish text: printable single-byte text WITHOUT NULs or control noise.
    if b"\x00" not in head and all(9 <= b <= 13 or 32 <= b <= 126 for b in head):
        return FMT_CSV
    return FMT_UNKNOWN


def _looks_like_html(data: bytes) -> bool:
    low = data[:2048].decode("utf-8", errors="replace").lower()
    return any(tag in low for tag in ("<html", "<table", "<!doctype", "<tbody", "<thead"))
