import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from companies.models import CompanyOwnedModel
from config.files import private_storage

EXPIRY_WARNING_DAYS = 60


class EmployeeDocument(CompanyOwnedModel):
    class Kind(models.TextChoices):
        ID = "id", "Pièce d'identité"
        CONTRACT = "contract", "Contrat / avenant"
        DIPLOMA = "diploma", "Diplôme / attestation"
        MEDICAL = "medical", "Visite médicale"
        WORK_PERMIT = "permit", "Permis de travail / séjour"
        OTHER = "other", "Autre"

    employee = models.ForeignKey(
        "employees.Employee", verbose_name="Employé", on_delete=models.CASCADE, related_name="documents"
    )
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.OTHER)
    title = models.CharField("Intitulé", max_length=150)
    file = models.FileField("Fichier", upload_to="documents/", storage=private_storage)
    issue_date = models.DateField("Date d'émission", null=True, blank=True)
    expiry_date = models.DateField("Date d'expiration", null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        verbose_name = "Document RH"
        verbose_name_plural = "Documents RH"
        ordering = ["employee__last_name", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.employee}"

    @property
    def days_left(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    @property
    def expiry_state(self):
        """'expired', 'soon' ou '' (pas d'échéance proche)."""
        left = self.days_left
        if left is None:
            return ""
        if left < 0:
            return "expired"
        return "soon" if left <= EXPIRY_WARNING_DAYS else ""


def expiring_documents(company, days=EXPIRY_WARNING_DAYS):
    limit = timezone.localdate() + datetime.timedelta(days=days)
    return EmployeeDocument.objects.filter(
        company=company, expiry_date__isnull=False, expiry_date__lte=limit
    ).select_related("employee").order_by("expiry_date")
