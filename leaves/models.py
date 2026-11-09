from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel


class LeaveType(CompanyOwnedModel):
    """Type de congé ou d'absence autorisée (annuel, maladie, maternité…)."""

    name = models.CharField("Libellé", max_length=100)
    annual_days = models.DecimalField(
        "Jours par an", max_digits=5, decimal_places=1, default=0,
        help_text="Droit annuel en jours ouvrés. Laisser à 0 si le nombre de jours n'est pas plafonné.",
    )
    is_paid = models.BooleanField("Rémunéré", default=True)
    needs_approval = models.BooleanField("Soumis à validation", default=True)

    class Meta:
        verbose_name = "Type de congé"
        verbose_name_plural = "Types de congés"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="uniq_leavetype_per_company")]

    def __str__(self):
        return self.name

    @property
    def is_capped(self):
        return self.annual_days > 0


class LeaveRequest(CompanyOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvé"
        REJECTED = "rejected", "Refusé"
        CANCELLED = "cancelled", "Annulé"

    employee = models.ForeignKey(
        "employees.Employee", verbose_name="Employé", on_delete=models.CASCADE, related_name="leave_requests"
    )
    leave_type = models.ForeignKey(
        LeaveType, verbose_name="Type", on_delete=models.PROTECT, related_name="requests"
    )
    start_date = models.DateField("Du")
    end_date = models.DateField("Au")
    days = models.DecimalField("Jours ouvrés", max_digits=5, decimal_places=1, default=0)
    reason = models.TextField("Motif", blank=True)
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Traité par", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    reviewed_at = models.DateTimeField("Traité le", null=True, blank=True)
    review_comment = models.CharField("Commentaire", max_length=255, blank=True)
    created_at = models.DateTimeField("Demandé le", auto_now_add=True)

    class Meta:
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congé"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} — {self.leave_type} ({self.start_date:%d/%m/%Y})"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING
