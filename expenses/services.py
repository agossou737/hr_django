from django.urls import reverse
from django.utils import timezone

from config.pdfdocs import build_letter_pdf
from leaves import services as lsv
from notifications.services import notify

from .models import ExpenseClaim


def notify_new(claim):
    notify(lsv.reviewers_of(claim), f"Note de frais à valider : {claim.employee.full_name}",
           f"{claim.title} — {claim.amount:,.0f} FCFA".replace(",", " "), reverse("expenses:pending"))


def review(claim, user, approve, comment=""):
    claim.status = ExpenseClaim.Status.APPROVED if approve else ExpenseClaim.Status.REJECTED
    claim.reviewed_by, claim.reviewed_at, claim.review_comment = user, timezone.now(), comment[:255]
    claim.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment"])
    if claim.employee.user_id:
        notify([claim.employee.user], f"Votre note de frais a été {'approuvée' if approve else 'refusée'}", comment,
               reverse("expenses:mine"))


def mark_paid(claim, date=None):
    claim.status, claim.paid_at = ExpenseClaim.Status.PAID, date or timezone.localdate()
    claim.save(update_fields=["status", "paid_at"])
    if claim.employee.user_id:
        notify([claim.employee.user], "Note de frais remboursée", claim.title, reverse("expenses:mine"))


def can_view(user, claim):
    return user.is_authenticated and user.company_id == claim.company_id and (
        user.can_manage_hr or claim.employee.user_id == user.pk or lsv.can_review(user, claim))


def claim_pdf(c):
    e = c.employee
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Date", f"{c.date:%d/%m/%Y}"), ("Objet", c.title),
             ("Catégorie", c.get_category_display()), ("Montant", f"{c.amount:,.0f} FCFA".replace(",", " ")),
             ("Justificatif", "Joint" if c.receipt else "Non fourni"), ("Statut", c.get_status_display())]
    paras = [("Commentaire", c.review_comment)] if c.review_comment else []
    if c.paid_at:
        paras.append(("Remboursement", f"Remboursée le {c.paid_at:%d/%m/%Y}."))
    return build_letter_pdf(c.company, "Note de frais", c.reference, facts, paras or ["—"],
                            signatures=[("L'employé", e.full_name, ""),
                                        ("Validation", c.reviewed_by.get_full_name() if c.reviewed_by else "", "")])
