"""
Resume export to DOCX and PDF.

The rebuilt resume is held as plain text with a simple, deliberate convention:
  * an UPPERCASE line on its own is a section heading
  * a line starting with "-", "*" or a bullet glyph is an achievement bullet
  * the first non-empty line is the candidate's name
  * everything else is a normal paragraph

Both writers read that same structure, so DOCX and PDF stay in sync. Layout is
kept plain on purpose: ATS parsers choke on tables, columns and text boxes.
"""
from __future__ import annotations

import io
import re

BULLET_CHARS = "-*•·–—▪◦●○»›"
_HEADING_MAX_WORDS = 5


def parse_blocks(text: str) -> list[tuple[str, str]]:
    """Turn resume plain text into a list of (kind, content) blocks."""
    blocks: list[tuple[str, str]] = []
    seen_name = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            blocks.append(("blank", ""))
            continue

        letters = [c for c in line if c.isalpha()]
        is_heading = (
            bool(letters)
            and line == line.upper()
            and len(line.split()) <= _HEADING_MAX_WORDS
            and not line[0] in BULLET_CHARS
        )

        if not seen_name and not is_heading:
            blocks.append(("name", line))
            seen_name = True
        elif is_heading:
            blocks.append(("heading", line.title()))
        elif line[0] in BULLET_CHARS:
            blocks.append(("bullet", line.lstrip(BULLET_CHARS).strip()))
        else:
            blocks.append(("body", line))

    # Collapse runs of blanks.
    out: list[tuple[str, str]] = []
    for kind, content in blocks:
        if kind == "blank" and out and out[-1][0] == "blank":
            continue
        out.append((kind, content))
    return out


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
def to_docx(text: str) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()

    section = doc.sections[0]
    for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, attr, Pt(40))

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(3)

    for kind, content in parse_blocks(text):
        if kind == "blank":
            continue

        if kind == "name":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(content)
            run.bold = True
            run.font.size = Pt(19)

        elif kind == "heading":
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(11)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(content.upper())
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
            _bottom_border(p)

        elif kind == "bullet":
            p = doc.add_paragraph(content, style="List Bullet")
            p.paragraph_format.space_after = Pt(2)

        else:
            doc.add_paragraph(content)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _bottom_border(paragraph) -> None:
    """Draw a hairline under a heading (python-docx has no styling API for this)."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    pPr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "999999")
    borders.append(bottom)
    pPr.append(borders)


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
_LATIN_FIXES = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
    "•": "-", "→": "->",
}


def _latin(text: str) -> str:
    """fpdf2's core fonts are Latin-1 only; degrade smart punctuation safely."""
    for bad, good in _LATIN_FIXES.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def to_pdf(text: str) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(16, 14, 16)
    pdf.add_page()
    width = pdf.w - 32

    for kind, content in parse_blocks(text):
        content = _latin(content)

        if kind == "blank":
            pdf.ln(2)

        elif kind == "name":
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(width, 8, content, align="C")
            pdf.ln(1)

        elif kind == "heading":
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 5.5, content.upper(), new_x="LMARGIN", new_y="NEXT")
            y = pdf.get_y()
            pdf.set_draw_color(150, 150, 150)
            pdf.set_line_width(0.2)
            pdf.line(16, y, pdf.w - 16, y)
            pdf.ln(1.5)

        elif kind == "bullet":
            pdf.set_font("Helvetica", "", 10)
            x = pdf.get_x()
            pdf.cell(4, 4.8, chr(149))
            pdf.set_x(x + 4)
            pdf.multi_cell(width - 4, 4.8, content)

        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(width, 4.8, content)

    out = pdf.output()
    return bytes(out)


def safe_filename(base: str, ext: str) -> str:
    """Turn a user-supplied name into something safe for a Content-Disposition header."""
    stem = re.sub(r"\.(pdf|docx|txt|md)$", "", base or "resume", flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)   # collapse spaces/punctuation
    stem = re.sub(r"_+", "_", stem).strip("._-")    # no doubled or dangling separators
    return f"{stem or 'resume'}.{ext}"
