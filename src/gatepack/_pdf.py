"""Page facts of a PDF (count, MediaBox and TrimBox sizes) for the KDP gates, read with pypdf."""
from __future__ import annotations

from pathlib import Path

from .core import GateError

PT = 72.0  # points per inch


def pages(path: str) -> list[dict]:
    """One dict per page: media (w, h) in inches and trim (w, h) or None when the page has no TrimBox."""
    p = Path(path)
    if not p.is_file():
        raise GateError(f"file not found: {path}")
    try:
        import pypdf
    except ImportError as exc:
        raise GateError("this gate needs pypdf: pip install pypdf") from exc
    try:
        reader = pypdf.PdfReader(str(p))
        out = []
        for page in reader.pages:
            media = page.mediabox
            trim = page.trimbox if "/TrimBox" in page else None
            out.append({
                "media": (round(float(media.width) / PT, 3), round(float(media.height) / PT, 3)),
                "trim": (round(float(trim.width) / PT, 3), round(float(trim.height) / PT, 3)) if trim is not None else None,
            })
    except Exception as exc:  # pypdf raises many exception types on damaged files
        raise GateError(f"could not read the PDF: {exc}") from exc
    if not out:
        raise GateError("the PDF contains no pages")
    return out
