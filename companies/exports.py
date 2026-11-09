"""Exports de tableaux : CSV, Excel (.xlsx) et PDF, avec une API commune."""
import csv
import datetime
import io

from django.http import Http404, HttpResponse
from django.utils import timezone

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FORMATS = ("csv", "xlsx", "pdf")


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M") if timezone.is_aware(value) else value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, datetime.date):
        return value.strftime("%d/%m/%Y")
    return value


def csv_response(filename, header, rows):
    """Réponse CSV compatible Excel français (séparateur « ; », encodage UTF-8 avec BOM)."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return response


def xlsx_response(filename, header, rows, title="Export"):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(list(header))
    fill = PatternFill("solid", fgColor="4F46E5")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    widths = [len(str(h)) for h in header]
    for row in rows:
        values = []
        for i, v in enumerate(row):
            v = _cell(v)
            if hasattr(v, "quantize"):  # Decimal
                v = float(v)
            values.append(v)
            widths[i] = max(widths[i], min(len(str(v)), 50))
        ws.append(values)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w + 3
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    response = HttpResponse(buf.getvalue(), content_type=XLSX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def build_table_pdf(title, header, rows, company_name="", subtitle=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title=title, author=company_name)
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("c", parent=styles["Normal"], fontSize=7.5, leading=9)
    head = ParagraphStyle("h", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    h1 = ParagraphStyle("t", parent=styles["Title"], fontSize=15, alignment=0, textColor=colors.HexColor("#4f46e5"), spaceAfter=2)
    meta = ParagraphStyle("m", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#64748b"))

    def esc(v):
        return str(_cell(v)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    data = [[Paragraph(esc(h), head) for h in header]]
    data += [[Paragraph(esc(v), cell) for v in row] for row in rows]
    usable = page[0] - 20 * mm
    table = Table(data, colWidths=[usable / len(header)] * len(header), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    now = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    story = [Paragraph(esc(title), h1),
             Paragraph(f"{esc(company_name)} · {esc(subtitle)} · édité le {now} · {len(rows)} ligne(s)".replace(" ·  ·", " ·"), meta),
             Spacer(1, 4 * mm), table]

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawRightString(page[0] - 10 * mm, 7 * mm, f"Page {d.page}")
        canvas.drawString(10 * mm, 7 * mm, "Ruche RH")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def pdf_response(filename, title, header, rows, company_name="", subtitle=""):
    response = HttpResponse(build_table_pdf(title, header, list(rows), company_name, subtitle), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_table(fmt, base_name, title, header, rows, company=None, subtitle=""):
    """Point d'entrée unique : `fmt` ∈ csv | xlsx | pdf."""
    if fmt not in FORMATS:
        raise Http404
    rows = [list(r) for r in rows]
    if fmt == "csv":
        return csv_response(f"{base_name}.csv", header, rows)
    if fmt == "xlsx":
        return xlsx_response(f"{base_name}.xlsx", header, rows, title)
    return pdf_response(f"{base_name}.pdf", title, header, rows, getattr(company, "name", ""), subtitle)
