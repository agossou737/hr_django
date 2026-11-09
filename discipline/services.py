from django.urls import reverse
from django.utils import timezone

from config.pdfdocs import build_letter_pdf
from notifications.services import notify


def notify_employee(s):
    if s.employee.user_id:
        notify([s.employee.user], f"Mesure disciplinaire : {s.get_kind_display()}", s.reason, reverse("discipline:mine"))


def acknowledge(s):
    s.acknowledged_at = timezone.now()
    s.save(update_fields=["acknowledged_at"])


def sanction_pdf(s):
    e = s.employee
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Nature", s.get_kind_display()),
             ("Date", f"{s.date:%d/%m/%Y}"), ("Motif", s.reason)]
    if s.suspension_days:
        facts.append(("Durée de la mise à pied", f"{s.suspension_days} jour(s)"))
    if s.explanation_id:
        facts.append(("Explication liée", s.explanation.reference))
    paras = [("Faits reprochés", s.details or s.reason),
             "Cette mesure est notifiée à l'intéressé(e), qui en prend connaissance. Elle est versée à son dossier."]
    ack = (f"Pris connaissance le {timezone.localtime(s.acknowledged_at):%d/%m/%Y}" if s.acknowledged_at else "")
    return build_letter_pdf(s.company, "Notification de mesure disciplinaire", s.reference, facts, paras,
                            signatures=[("L'employeur", s.issued_by.get_full_name() if s.issued_by else "", ""),
                                        ("L'employé(e)", e.full_name, ack)])
