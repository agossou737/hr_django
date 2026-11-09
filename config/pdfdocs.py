"""Courriers PDF (demande d'explication, autorisation, titre de congé…) au format commun."""
import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PRIMARY = colors.HexColor("#4f46e5")


def _esc(value):
    return str(value if value is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def build_letter_pdf(company, title, reference, facts, paragraphs, signatures=(), footer_note="", stamp=""):
    """
    facts : liste de (libellé, valeur) affichée dans un cadre ;
    paragraphs : liste de textes (ou de (titre, texte)) ;
    signatures : liste de (rôle, nom, mention) en bas de page ;
    stamp : mention en rouge/vert (ex. « APPROUVÉ »).
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=title, author=company.name)
    st = getSampleStyleSheet()
    n = ParagraphStyle("n", parent=st["Normal"], fontSize=10, leading=14)
    small = ParagraphStyle("s", parent=n, fontSize=8, leading=10, textColor=colors.HexColor("#64748b"))
    h = ParagraphStyle("h", parent=st["Title"], fontSize=17, textColor=PRIMARY, spaceBefore=8, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=n, fontName="Helvetica-Bold", fontSize=11, spaceBefore=8, spaceAfter=2)

    head = Table([[Paragraph(f"<b>{_esc(company.name)}</b><br/>{_esc(company.address)} {_esc(company.city)}<br/>"
                             f"IFU : {_esc(company.ifu or '—')} · RCCM : {_esc(company.rccm or '—')}", n),
                   Paragraph(f"Réf. {_esc(reference)}<br/>{timezone.localdate():%d/%m/%Y}",
                             ParagraphStyle("r", parent=n, alignment=2))]], colWidths=[110 * mm, 60 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, PRIMARY),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story = [head, Spacer(1, 6 * mm), Paragraph(_esc(title).upper(), h)]
    if stamp:
        story.append(Paragraph(f"<b>{_esc(stamp)}</b>", ParagraphStyle("stamp", parent=n, textColor=PRIMARY, fontSize=11)))
    story.append(Spacer(1, 3 * mm))
    if facts:
        t = Table([[Paragraph(f"<b>{_esc(k)}</b>", n), Paragraph(_esc(v), n)] for k, v in facts], colWidths=[55 * mm, 115 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                               ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                               ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e2e8f0")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story += [t, Spacer(1, 5 * mm)]
    for p in paragraphs:
        if isinstance(p, tuple):
            story.append(Paragraph(_esc(p[0]), sub))
            p = p[1]
        story += [Paragraph(_esc(p), n), Spacer(1, 2 * mm)]
    if signatures:
        story.append(Spacer(1, 10 * mm))
        cells = [[Paragraph(f"<b>{_esc(role)}</b><br/>{_esc(name)}<br/><font size=8 color='#64748b'>{_esc(note)}</font>", n)
                  for role, name, note in signatures]]
        sig = Table(cells, colWidths=[170 * mm / len(signatures)] * len(signatures), rowHeights=[28 * mm])
        sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(sig)
    story += [Spacer(1, 6 * mm), Paragraph(_esc(footer_note) or "Document généré par Ruche RH.", small)]
    doc.build(story)
    return buf.getvalue()
