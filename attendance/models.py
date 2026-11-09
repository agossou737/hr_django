import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from companies.models import CompanyOwnedModel
from employees.models import Employee


class FaceTemplate(CompanyOwnedModel):
    """Empreinte faciale (vecteur de 128 valeurs) d'un employé.

    Aucune photo n'est conservée par ce module : seul le vecteur numérique est stocké,
    avec la date du consentement de la personne.
    """

    employee = models.ForeignKey(
        Employee, verbose_name="Employé", on_delete=models.CASCADE, related_name="face_templates"
    )
    descriptor = models.JSONField("Empreinte")
    consent_at = models.DateTimeField("Consentement donné le")
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        verbose_name = "Empreinte faciale"
        verbose_name_plural = "Empreintes faciales"

    def __str__(self):
        return f"Empreinte de {self.employee.full_name}"


class AttendanceRecord(CompanyOwnedModel):
    """Pointage journalier : première arrivée et dernière sortie."""

    class Source(models.TextChoices):
        FACE = "face", "Reconnaissance faciale"
        FINGERPRINT = "fingerprint", "Empreinte digitale"
        MANUAL = "manual", "Saisie manuelle"

    employee = models.ForeignKey(
        Employee, verbose_name="Employé", on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField("Date")
    check_in = models.DateTimeField("Arrivée")
    check_out = models.DateTimeField("Départ", null=True, blank=True)
    source_in = models.CharField("Source arrivée", max_length=12, choices=Source.choices, default=Source.FACE)
    source_out = models.CharField(
        "Source départ", max_length=12, choices=Source.choices, default=Source.FACE, blank=True
    )
    confidence = models.FloatField("Confiance (%)", null=True, blank=True)
    late_minutes = models.PositiveIntegerField("Retard (min)", default=0)
    note = models.CharField("Observation", max_length=255, blank=True)

    class Meta:
        verbose_name = "Pointage"
        verbose_name_plural = "Pointages"
        ordering = ["-date", "check_in"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="uniq_attendance_per_employee_day")
        ]

    def __str__(self):
        return f"{self.employee.full_name} — {self.date:%d/%m/%Y}"

    def compute_late_minutes(self):
        """Minutes de retard par rapport à l'heure de début, au-delà de la tolérance."""
        company = self.company
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.datetime.combine(self.date, company.work_start_time), tz)
        late = (self.check_in - start).total_seconds() / 60
        return int(late) if late > company.late_tolerance_minutes else 0

    def save(self, *args, **kwargs):
        if self.check_in:
            self.late_minutes = self.compute_late_minutes()
        super().save(*args, **kwargs)

    @property
    def worked_duration(self):
        if self.check_out and self.check_out > self.check_in:
            return self.check_out - self.check_in
        return None

    @property
    def worked_hours(self):
        duration = self.worked_duration
        return round(duration.total_seconds() / 3600, 2) if duration else 0.0


class ScanLog(CompanyOwnedModel):
    """Journal de toutes les tentatives de pointage, réussies ou non."""

    class Outcome(models.TextChoices):
        CHECK_IN = "in", "Arrivée enregistrée"
        CHECK_OUT = "out", "Départ enregistré"
        DUPLICATE = "duplicate", "Déjà pointé"
        UNKNOWN = "unknown", "Non reconnu"
        INACTIVE = "inactive", "Employé non actif"

    employee = models.ForeignKey(
        Employee, verbose_name="Employé", on_delete=models.SET_NULL, null=True, blank=True, related_name="scan_logs"
    )
    outcome = models.CharField("Résultat", max_length=12, choices=Outcome.choices)
    distance = models.FloatField("Distance", null=True, blank=True)
    device = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Borne / utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField("Date et heure", default=timezone.now)

    class Meta:
        verbose_name = "Tentative de pointage"
        verbose_name_plural = "Journal des pointages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_outcome_display()} — {self.created_at:%d/%m/%Y %H:%M}"
