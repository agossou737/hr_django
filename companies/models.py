import datetime

from django.db import models


class Company(models.Model):
    """Entreprise cliente (tenant). Toutes les données RH lui sont rattachées."""

    name = models.CharField("Raison sociale", max_length=200)
    slug = models.SlugField("Identifiant", unique=True)
    ifu = models.CharField("IFU", max_length=20, blank=True)
    rccm = models.CharField("RCCM", max_length=50, blank=True)
    cnss_number = models.CharField("N° employeur CNSS", max_length=30, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    city = models.CharField("Ville", max_length=100, blank=True, default="Cotonou")
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    email = models.EmailField("E-mail", blank=True)
    logo = models.ImageField("Logo", upload_to="companies/logos/", blank=True)
    is_active = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    # Horaires de travail (utilisés pour les retards et les absences)
    work_start_time = models.TimeField("Heure de début", default=datetime.time(8, 0))
    work_end_time = models.TimeField("Heure de fin", default=datetime.time(17, 0))
    late_tolerance_minutes = models.PositiveSmallIntegerField("Tolérance de retard (min)", default=10)
    auto_explanation = models.BooleanField(
        "Demande d'explication automatique en cas de retard", default=True,
        help_text="Chaque pointage en retard génère une demande d'explication adressée à l'employé.",
    )
    explanation_deadline_days = models.PositiveSmallIntegerField(
        "Délai de réponse (jours)", default=2, help_text="Au-delà, l'employé est relancé automatiquement."
    )
    work_days = models.CharField(
        "Jours travaillés",
        max_length=20,
        default="0,1,2,3,4",
        help_text="Numéros des jours séparés par des virgules (0 = lundi … 6 = dimanche).",
    )

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def work_weekdays(self):
        """Ensemble des jours de semaine travaillés (0 = lundi)."""
        days = set()
        for part in (self.work_days or "").split(","):
            part = part.strip()
            if part.isdigit() and 0 <= int(part) <= 6:
                days.add(int(part))
        return days or {0, 1, 2, 3, 4}


class CompanyOwnedModel(models.Model):
    """Base abstraite : tout objet appartient à une entreprise."""

    company = models.ForeignKey(
        Company,
        verbose_name="Entreprise",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True


class Holiday(CompanyOwnedModel):
    """Jour férié ou jour de fermeture de l'entreprise."""

    date = models.DateField("Date")
    name = models.CharField("Libellé", max_length=120)

    class Meta:
        verbose_name = "Jour férié"
        verbose_name_plural = "Jours fériés"
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["company", "date"], name="uniq_holiday_per_company_date")
        ]

    def __str__(self):
        return f"{self.name} ({self.date:%d/%m/%Y})"
