"""Resume text extraction for PDF, DOCX and plain-text uploads."""
from __future__ import annotations

import io
import re


def extract_text(filename: str, data: bytes) -> str:
    """Return plain text from an uploaded resume regardless of format."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        text = _from_pdf(data)
    elif name.endswith(".docx"):
        text = _from_docx(data)
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="ignore")
    else:
        # Last resort: try PDF, then decode as text.
        text = _from_pdf(data) or data.decode("utf-8", errors="ignore")
    return _normalise(text)


def _from_pdf(data: bytes) -> str:
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover
        return ""
    out = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
    except Exception:
        return ""
    return "\n".join(out)


def _from_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError:  # pragma: no cover
        return ""
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception:
        return ""
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def _normalise(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_YEAR_RE = re.compile(r"(19|20)\d{2}")
_TITLE_SEP_RE = re.compile(r"\s[—–]\s")
_ACHIEVEMENT_HEADERS = ("experience", "employment", "work history", "project", "internship")


def split_bullets(text: str) -> list[str]:
    """
    Extract genuine achievement bullets from the Experience/Projects sections.

    This is section-aware on purpose: scoring "impact" and "action language" over
    skill lists, contact lines or section headers would badly skew the result, so
    we only evaluate lines that live under an experience/projects heading and that
    read like accomplishments (not role titles or project titles with dates).
    """
    bullets: list[str] = []
    in_section = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        letters = [c for c in line if c.isalpha()]
        is_header = bool(letters) and line.upper() == line and len(line.split()) <= 4
        if is_header:
            in_section = any(h in low for h in _ACHIEVEMENT_HEADERS)
            continue
        if not in_section:
            continue
        clean = line.lstrip("•·-–—*▪◦●○»›").strip()
        if len(clean.split()) < 4:
            continue
        # Skip role/company headers (carry a year) and project titles ("Name — stack").
        if _YEAR_RE.search(clean) or _TITLE_SEP_RE.search(clean):
            continue
        bullets.append(clean)
    return bullets
