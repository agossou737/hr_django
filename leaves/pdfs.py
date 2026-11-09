from django.utils import timezone

from config.pdfdocs import build_letter_pdf


def leave_pdf(leave):
    e = leave.employee
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Poste", str(e.position or "—")),
             ("Type", leave.leave_type.name), ("Période", f"du {leave.start_date:%d/%m/%Y} au {leave.end_date:%d/%m/%Y}"),
             ("Jours ouvrés", f"{leave.days:g}"), ("Rémunéré", "Oui" if leave.leave_type.is_paid else "Non")]
    if leave.replacement_id:
        facts.append(("Intérim assuré par", leave.replacement.full_name))
    paras = [f"La Direction autorise {e.full_name} à s'absenter pour la période indiquée ci-dessus."]
    if leave.review_comment:
        paras.append(("Observation", leave.review_comment))
    by = leave.reviewed_by.get_full_name() if leave.reviewed_by else ""
    return build_letter_pdf(leave.company, "Autorisation de congé", f"CONGE-{leave.pk:05d}", facts, paras,
                            signatures=[("L'employé", e.full_name, ""),
                                        ("La Direction", by, f"Approuvé le {timezone.localtime(leave.reviewed_at):%d/%m/%Y}" if leave.reviewed_at else "")],
                            stamp="APPROUVÉ")


def permission_pdf(p):
    e = p.employee
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Date", f"{p.date:%d/%m/%Y}"),
             ("Créneau", f"de {p.start_time:%H:%M} à {p.end_time:%H:%M} ({p.hours:g} h)"), ("Motif", p.reason)]
    by = p.reviewed_by.get_full_name() if p.reviewed_by else ""
    return build_letter_pdf(p.company, "Autorisation d'absence (permission)", p.reference, facts,
                            ["La Direction autorise l'employé à s'absenter pendant le créneau indiqué."],
                            signatures=[("L'employé", e.full_name, ""), ("La Direction", by, "")], stamp="ACCORDÉE")
