from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel


class Sanction(CompanyOwnedModel):
    class Kind(models.TextChoices):
        VERBAL = "verbal", "Avertissement verbal"
        WRITTEN = "written", "Avertissement écrit"
        BLAME = "blame", "Blâme"
        SUSPENSION = "suspension", "Mise à pied"
        OTHER = "other", "Autre mesure"

    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="sanctions")
    kind = models.CharField("Nature", max_length=12, choices=Kind.choices)
    date = models.DateField("Date")
    reason = models.CharField("Motif", max_length=200)
    details = models.TextField("Détails des faits", blank=True)
    suspension_days = models.PositiveSmallIntegerField("Jours de mise à pied", default=0)
    explanation = models.ForeignKey("explanations.Explanation", verbose_name="Demande d'explication liée",
                                    on_delete=models.SET_NULL, null=True, blank=True, related_name="sanctions")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    acknowledged_at = models.DateTimeField("Prise de connaissance", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sanction"
        verbose_name_plural = "Sanctions"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.employee}"

    @property
    def reference(self):
        return f"DISC-{self.date.year}-{self.pk or 0:05d}"
