from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel


class Explanation(CompanyOwnedModel):
    """Demande d'explication adressée à un employé (retard, absence…), avec sa réponse et la décision RH."""

    class Kind(models.TextChoices):
        LATE = "late", "Retard"
        ABSENCE = "absence", "Absence"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        PENDING = "pending", "À répondre"
        ANSWERED = "answered", "Réponse reçue"
        JUSTIFIED = "justified", "Justifié"
        UNJUSTIFIED = "unjustified", "Non justifié"
        CANCELLED = "cancelled", "Annulée"

    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="explanations")
    attendance = models.ForeignKey("attendance.AttendanceRecord", verbose_name="Pointage", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="explanations")
    kind = models.CharField("Nature", max_length=10, choices=Kind.choices, default=Kind.LATE)
    date = models.DateField("Date concernée")
    subject = models.CharField("Objet", max_length=200)
    message = models.TextField("Message de l'employeur", blank=True)
    late_minutes = models.PositiveIntegerField("Retard (min)", default=0)
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Demandée par", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="+")
    automatic = models.BooleanField("Générée automatiquement", default=False)
    created_at = models.DateTimeField("Émise le", auto_now_add=True)
    deadline = models.DateField("Réponse attendue avant le")

    answer = models.TextField("Réponse de l'employé", blank=True)
    answered_at = models.DateTimeField("Répondu le", null=True, blank=True)

    decision_comment = models.CharField("Commentaire RH", max_length=255, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Décidée par", on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="+")
    decided_at = models.DateTimeField("Décidée le", null=True, blank=True)

    reminders_sent = models.PositiveSmallIntegerField("Relances envoyées", default=0)
    last_reminder_at = models.DateField("Dernière relance", null=True, blank=True)

    class Meta:
        verbose_name = "Demande d'explication"
        verbose_name_plural = "Demandes d'explication"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["attendance", "kind"], condition=models.Q(attendance__isnull=False),
                                    name="uniq_explanation_per_attendance_kind"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.employee.full_name}"

    @property
    def reference(self):
        return f"EXP-{self.created_at.year if self.created_at else 0}-{self.pk or 0:05d}"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_answered(self):
        return self.status == self.Status.ANSWERED

    @property
    def is_open(self):
        return self.status in (self.Status.PENDING, self.Status.ANSWERED)

    @property
    def is_decided(self):
        return self.status in (self.Status.JUSTIFIED, self.Status.UNJUSTIFIED)
