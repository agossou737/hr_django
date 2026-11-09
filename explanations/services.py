import datetime

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from config.pdfdocs import build_letter_pdf
from notifications.services import hr_users, notify

from .models import Explanation

MAX_REMINDERS = 3


def _employee_users(employee):
    return [employee.user] if employee.user_id and employee.user.is_active else []


def create_for_lateness(record):
    """Crée (une seule fois par pointage) la demande d'explication d'un retard et prévient l'employé."""
    company = record.company
    if Explanation.objects.filter(attendance=record, kind=Explanation.Kind.LATE).exists():
        return None
    employee = record.employee
    local_in = timezone.localtime(record.check_in)
    message = (
        f"Vous avez pointé à {local_in:%H:%M} le {record.date:%d/%m/%Y} alors que l'heure de début est "
        f"{company.work_start_time:%H:%M} : retard de {record.late_minutes} minute(s). "
        "Nous vous demandons de bien vouloir préciser les raisons de ce retard."
    )
    try:
        with transaction.atomic():
            exp = Explanation.objects.create(
                company=company, employee=employee, attendance=record, kind=Explanation.Kind.LATE, date=record.date,
                subject=f"Retard du {record.date:%d/%m/%Y} ({record.late_minutes} min)", message=message,
                late_minutes=record.late_minutes, automatic=True,
                deadline=record.date + datetime.timedelta(days=company.explanation_deadline_days),
            )
    except IntegrityError:
        return None
    notify(_employee_users(employee), "Demande d'explication : " + exp.subject,
           "Une demande d'explication vous a été adressée. Merci d'y répondre avant le "
           f"{exp.deadline:%d/%m/%Y}.", reverse("explanations:detail", args=[exp.pk]))
    return exp


def create_manual(company, employee, user, kind, date, subject, message, late_minutes=0):
    exp = Explanation.objects.create(
        company=company, employee=employee, kind=kind, date=date, subject=subject, message=message,
        late_minutes=late_minutes, requested_by=user,
        deadline=timezone.localdate() + datetime.timedelta(days=company.explanation_deadline_days),
    )
    notify(_employee_users(employee), "Demande d'explication : " + subject,
           f"Merci de répondre avant le {exp.deadline:%d/%m/%Y}.", reverse("explanations:detail", args=[exp.pk]))
    return exp


def answer(exp, text):
    exp.answer = text.strip()
    exp.answered_at = timezone.now()
    exp.status = Explanation.Status.ANSWERED
    exp.save(update_fields=["answer", "answered_at", "status"])
    notify(hr_users(exp.company), f"Réponse de {exp.employee.full_name} — {exp.subject}",
           exp.answer[:300], reverse("explanations:detail", args=[exp.pk]))
    return exp


def decide(exp, user, justified, comment=""):
    exp.status = Explanation.Status.JUSTIFIED if justified else Explanation.Status.UNJUSTIFIED
    exp.decided_by, exp.decided_at, exp.decision_comment = user, timezone.now(), comment[:255]
    exp.save(update_fields=["status", "decided_by", "decided_at", "decision_comment"])
    notify(_employee_users(exp.employee), f"Votre explication a été {'acceptée' if justified else 'non retenue'}",
           comment, reverse("explanations:detail", args=[exp.pk]))
    return exp


def can_view(user, exp):
    return user.is_authenticated and user.company_id == exp.company_id and (
        user.can_manage_hr or exp.employee.user_id == user.pk
    )


def send_reminders(today=None, company=None):
    """Relance les employés dont l'explication est en retard (1 relance par jour, 3 au maximum)."""
    today = today or timezone.localdate()
    qs = Explanation.objects.filter(status=Explanation.Status.PENDING, deadline__lt=today,
                                    reminders_sent__lt=MAX_REMINDERS).select_related("employee__user", "company")
    if company:
        qs = qs.filter(company=company)
    count = 0
    for exp in qs:
        if exp.last_reminder_at == today:
            continue
        exp.reminders_sent += 1
        exp.last_reminder_at = today
        exp.save(update_fields=["reminders_sent", "last_reminder_at"])
        notify(_employee_users(exp.employee), f"Relance : {exp.subject}",
               f"Votre réponse était attendue avant le {exp.deadline:%d/%m/%Y}. Merci de répondre sans délai.",
               reverse("explanations:detail", args=[exp.pk]))
        if exp.reminders_sent >= MAX_REMINDERS:
            notify(hr_users(exp.company), f"Sans réponse après {MAX_REMINDERS} relances : {exp.employee.full_name}",
                   exp.subject, reverse("explanations:detail", args=[exp.pk]))
        count += 1
    return count


def request_pdf(exp):
    e = exp.employee
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Poste", str(e.position or "—")),
             ("Date concernée", f"{exp.date:%d/%m/%Y}"), ("Nature", exp.get_kind_display()),
             ("Réponse attendue avant le", f"{exp.deadline:%d/%m/%Y}")]
    if exp.late_minutes:
        facts.append(("Retard constaté", f"{exp.late_minutes} minute(s)"))
    return build_letter_pdf(
        exp.company, "Demande d'explication", exp.reference, facts,
        [f"Objet : {exp.subject}", exp.message or "Merci de bien vouloir nous faire connaître les raisons de ce manquement.",
         "Votre réponse doit être saisie dans l'application, rubrique « Explications »."],
        signatures=[("La Direction des Ressources Humaines", exp.requested_by.get_full_name() if exp.requested_by else "Génération automatique",
                     f"Émis le {timezone.localtime(exp.created_at):%d/%m/%Y à %H:%M}")],
    )


def response_pdf(exp):
    e = exp.employee
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Référence", exp.reference),
             ("Objet", exp.subject), ("Date concernée", f"{exp.date:%d/%m/%Y}"),
             ("Répondu le", f"{timezone.localtime(exp.answered_at):%d/%m/%Y à %H:%M}" if exp.answered_at else "—")]
    paras = [("Demande de l'employeur", exp.message or exp.subject), ("Réponse de l'employé", exp.answer or "(aucune réponse)")]
    stamp = ""
    if exp.is_decided:
        stamp = "EXPLICATION " + ("ACCEPTÉE" if exp.status == exp.Status.JUSTIFIED else "NON RETENUE")
        paras.append(("Décision des RH", exp.decision_comment or "Sans commentaire."))
    sigs = [("L'employé", e.full_name, "Réponse saisie dans l'application")]
    if exp.is_decided:
        sigs.append(("Les Ressources Humaines", exp.decided_by.get_full_name() if exp.decided_by else "",
                     f"Décision du {timezone.localtime(exp.decided_at):%d/%m/%Y}"))
    return build_letter_pdf(exp.company, "Réponse à une demande d'explication", exp.reference, facts, paras,
                            signatures=sigs, stamp=stamp)
