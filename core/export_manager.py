import io
import re
from datetime import date
from xml.sax.saxutils import escape as _xml_escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def _strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s*',      '', text, flags=re.MULTILINE)
    text = re.sub(r'^-{3,}$',   '', text, flags=re.MULTILINE)
    return text.strip()


def _pdf_safe(text: str) -> str:
    text = re.sub(r'[^\x00-\xFF]', '', text)
    return _xml_escape(text)


def export_to_docx(messages: list[dict], gp_name: str, year: int) -> bytes:
    doc = Document()

    title = doc.add_heading(f"{gp_name} {year} — Análisis F1", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Exportado el {date.today().strftime('%d/%m/%Y')}")

    pending_heading = None
    for msg in messages:
        if msg["role"] == "user":
            pending_heading = msg["content"].strip()
        elif msg["role"] == "assistant":
            heading = pending_heading or "Análisis"
            doc.add_heading(heading[:120], level=1)
            pending_heading = None
            for line in _strip_markdown(msg["content"]).split("\n"):
                line = line.strip()
                if line:
                    doc.add_paragraph(line)
            doc.add_paragraph("")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_to_pdf(messages: list[dict], gp_name: str, year: int) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("f1_title", parent=styles["Title"],   fontSize=16, spaceAfter=4)
    head_style  = ParagraphStyle("f1_head",  parent=styles["Heading1"], fontSize=13, spaceBefore=12, spaceAfter=6)
    body_style  = ParagraphStyle("f1_body",  parent=styles["Normal"],   fontSize=10, leading=14, spaceAfter=4)
    meta_style  = ParagraphStyle("f1_meta",  parent=styles["Normal"],   fontSize=9)

    story = [
        Paragraph(_pdf_safe(f"{gp_name} {year} — Análisis F1"), title_style),
        Paragraph(_pdf_safe(f"Exportado el {date.today().strftime('%d/%m/%Y')}"), meta_style),
        Spacer(1, 0.5 * cm),
    ]

    pending_heading = None
    for msg in messages:
        if msg["role"] == "user":
            pending_heading = msg["content"].strip()
        elif msg["role"] == "assistant":
            heading = pending_heading or "Análisis"
            story.append(Paragraph(_pdf_safe(heading[:120]), head_style))
            pending_heading = None
            for line in _strip_markdown(msg["content"]).split("\n"):
                line = line.strip()
                if line:
                    story.append(Paragraph(_pdf_safe(line), body_style))
            story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
    return buf.getvalue()
