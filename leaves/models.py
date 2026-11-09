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

    class ReplacementStatus(models.TextChoices):
        NONE = "none", "Sans remplaçant"
        PENDING = "pending", "Remplaçant à confirmer"
        ACCEPTED = "accepted", "Remplaçant accepté"
        DECLINED = "declined", "Remplaçant refusé"

    replacement = models.ForeignKey(
        "employees.Employee", verbose_name="Remplaçant (intérim)", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="replacements",
    )
    replacement_status = models.CharField("Réponse du remplaçant", max_length=10,
                                          choices=ReplacementStatus.choices, default=ReplacementStatus.NONE)
    replacement_responded_at = models.DateTimeField(null=True, blank=True)
    replacement_comment = models.CharField("Commentaire du remplaçant", max_length=255, blank=True)

    class Meta:
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congé"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} — {self.leave_type} ({self.start_date:%d/%m/%Y})"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING


class PermissionRequest(CompanyOwnedModel):
    """Autorisation d'absence de quelques heures (rendez-vous, démarche, urgence…)."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Accordée"
        REJECTED = "rejected", "Refusée"
        CANCELLED = "cancelled", "Annulée"

    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="permission_requests")
    date = models.DateField("Date")
    start_time = models.TimeField("De")
    end_time = models.TimeField("À")
    reason = models.TextField("Motif")
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Traitée par", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="+")
    reviewed_at = models.DateTimeField("Traitée le", null=True, blank=True)
    review_comment = models.CharField("Commentaire", max_length=255, blank=True)
    created_at = models.DateTimeField("Demandée le", auto_now_add=True)

    class Meta:
        verbose_name = "Demande de permission"
        verbose_name_plural = "Demandes de permission"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.employee} — permission du {self.date:%d/%m/%Y}"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def reference(self):
        return f"PERM-{self.date.year}-{self.pk or 0:05d}"

    @property
    def hours(self):
        import datetime

        a = datetime.datetime.combine(self.date, self.start_time)
        b = datetime.datetime.combine(self.date, self.end_time)
        return round((b - a).total_seconds() / 3600, 1)
