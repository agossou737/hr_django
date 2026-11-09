"""Génération du bulletin de paie au format PDF (reportlab)."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import PayrollSettings, PayslipItem

PRIMARY = colors.HexColor("#4f46e5")


def fcfa(value):
    """12345678 → '12 345 678' (séparateur de milliers)."""
    return f"{int(value):,}".replace(",", " ")


def build_payslip_pdf(payslip):
    company, employee, period = payslip.company, payslip.employee, payslip.period
    settings = PayrollSettings.for_company(company)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Bulletin de paie {period.label} — {employee.full_name}", author=company.name,
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#475569"))
    normal = ParagraphStyle("n", parent=styles["Normal"], fontSize=9, leading=12)
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=15, textColor=PRIMARY, alignment=0, spaceAfter=2)
    story = []

    header = Table(
        [[
            Paragraph(f"<b>{company.name}</b><br/>{company.address or ''} {company.city or ''}<br/>"
                      f"IFU : {company.ifu or '—'} · RCCM : {company.rccm or '—'}<br/>N° employeur CNSS : {company.cnss_number or '—'}", normal),
            Paragraph(f"<b>BULLETIN DE PAIE</b><br/>{period.label}", ParagraphStyle("r", parent=normal, alignment=2, fontSize=12, leading=16)),
        ]],
        colWidths=[110 * mm, 70 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, PRIMARY),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [header, Spacer(1, 5 * mm)]

    contract = employee.contracts.filter(is_current=True).first()
    info = Table(
        [
            [Paragraph(f"<b>{employee.full_name}</b>", normal), Paragraph(f"Matricule : {employee.matricule}", normal)],
            [Paragraph(f"Poste : {employee.position or '—'}", normal), Paragraph(f"Département : {employee.department or '—'}", normal)],
            [Paragraph(f"N° CNSS : {employee.cnss_number or '—'}", normal), Paragraph(f"IFU : {employee.ifu or '—'}", normal)],
            [Paragraph(f"Embauche : {employee.hire_date:%d/%m/%Y}", normal),
             Paragraph(f"Contrat : {contract.get_contract_type_display() if contract else '—'}", normal)],
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    info.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                              ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [info, Spacer(1, 5 * mm)]

    rows = [["Désignation", "Base", "Taux", "Gains", "Retenues"]]
    rows.append(["Salaire de base", "", "", fcfa(payslip.base_salary), ""])
    if payslip.unpaid_deduction:
        rows.append([f"Absences non rémunérées ({payslip.unpaid_days:g} j)", "", "", "", fcfa(payslip.unpaid_deduction)])
    for item in payslip.items.all():
        label = item.label + ("" if item.subject_to_contributions or item.kind == PayslipItem.Kind.DEDUCTION else " (non imposable)")
        if item.kind == PayslipItem.Kind.EARNING:
            rows.append([label, "", "", fcfa(item.amount), ""])
    rows.append(["Salaire brut", "", "", fcfa(payslip.gross), ""])
    rows.append(["CNSS salarié (vieillesse)", fcfa(payslip.contribution_base), f"{settings.cnss_employee_rate:g} %", "", fcfa(payslip.cnss_employee)])
    rows.append(["Impôt sur traitements et salaires (ITS)", fcfa(payslip.its_base), "barème", "", fcfa(payslip.its)])
    for item in payslip.items.all():
        if item.kind == PayslipItem.Kind.DEDUCTION:
            rows.append([item.label, "", "", "", fcfa(item.amount)])
    table = Table(rows, colWidths=[78 * mm, 28 * mm, 20 * mm, 27 * mm, 27 * mm], repeatRows=1)
    gross_row = next(i for i, r in enumerate(rows) if r[0] == "Salaire brut")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("FONTNAME", (0, gross_row), (-1, gross_row), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [table, Spacer(1, 4 * mm)]

    net = Table([[Paragraph("<b>NET À PAYER</b>", ParagraphStyle("nn", parent=normal, textColor=colors.white, fontSize=11)),
                  Paragraph(f"<b>{fcfa(payslip.net)} FCFA</b>", ParagraphStyle("nv", parent=normal, textColor=colors.white, fontSize=12, alignment=2))]],
                colWidths=[90 * mm, 90 * mm])
    net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PRIMARY), ("TOPPADDING", (0, 0), (-1, -1), 6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [net, Spacer(1, 5 * mm)]

    employer = Table(
        [["Charges patronales (information)", "Montant"],
         ["CNSS employeur (vieillesse, prestations familiales, risques professionnels)", fcfa(payslip.cnss_employer)],
         [f"VPS ({settings.vps_rate:g} %)", fcfa(payslip.vps)],
         ["Coût total employeur", fcfa(payslip.employer_cost)]],
        colWidths=[150 * mm, 30 * mm],
    )
    employer.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                                  ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                                  ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#475569"))]))
    story += [employer, Spacer(1, 6 * mm),
              Paragraph("Bulletin à conserver sans limitation de durée. Document généré par Ruche RH.", small)]
    doc.build(story)
    return buffer.getvalue()
