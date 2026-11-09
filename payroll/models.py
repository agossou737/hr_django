from decimal import Decimal

from django.db import models

from companies.models import Company, CompanyOwnedModel

DEFAULT_BRACKETS = [[60000, 0], [150000, 10], [250000, 15], [500000, 19], [None, 30]]


class PayrollSettings(models.Model):
    """Paramètres de paie d'une entreprise. Tous les taux sont modifiables : la loi évolue."""

    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name="payroll_settings")
    cnss_employee_rate = models.DecimalField("CNSS salarié — vieillesse (%)", max_digits=5, decimal_places=2, default=Decimal("3.6"))
    cnss_employer_rate = models.DecimalField("CNSS employeur — vieillesse (%)", max_digits=5, decimal_places=2, default=Decimal("6.4"))
    cnss_family_rate = models.DecimalField("CNSS employeur — prestations familiales (%)", max_digits=5, decimal_places=2, default=Decimal("9"))
    cnss_accident_rate = models.DecimalField(
        "CNSS employeur — risques professionnels (%)", max_digits=5, decimal_places=2, default=Decimal("1"),
        help_text="Entre 1 % et 4 % selon l'activité ; le taux est notifié par la CNSS.",
    )
    cnss_ceiling = models.DecimalField(
        "Plafond mensuel CNSS (FCFA)", max_digits=12, decimal_places=0, null=True, blank=True,
        help_text="Laisser vide s'il n'y a pas de plafond.",
    )
    vps_rate = models.DecimalField("VPS employeur (%)", max_digits=5, decimal_places=2, default=Decimal("4"))
    its_deducts_cnss = models.BooleanField(
        "Déduire la CNSS salarié de la base ITS", default=False,
        help_text="À confirmer avec votre expert-comptable (par défaut : base = brut imposable).",
    )
    round_its = models.BooleanField(
        "Arrondir la base ITS au millier inférieur et l'impôt à la dizaine", default=True
    )
    smig = models.DecimalField("SMIG mensuel (FCFA)", max_digits=10, decimal_places=0, default=Decimal("52000"))
    its_brackets = models.JSONField(
        "Barème ITS mensuel", default=list,
        help_text="Liste [plafond de tranche, taux %] ; plafond vide pour la dernière tranche.",
    )

    class Meta:
        verbose_name = "Paramètres de paie"
        verbose_name_plural = "Paramètres de paie"

    def __str__(self):
        return f"Paramètres de paie — {self.company}"

    def save(self, *args, **kwargs):
        if not self.its_brackets:
            self.its_brackets = [list(b) for b in DEFAULT_BRACKETS]
        super().save(*args, **kwargs)

    @classmethod
    def for_company(cls, company):
        obj, _ = cls.objects.get_or_create(company=company)
        return obj


class PayrollPeriod(CompanyOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        VALIDATED = "validated", "Validée"

    year = models.PositiveSmallIntegerField("Année")
    month = models.PositiveSmallIntegerField("Mois")
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    validated_at = models.DateTimeField("Validée le", null=True, blank=True)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        verbose_name = "Période de paie"
        verbose_name_plural = "Périodes de paie"
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(fields=["company", "year", "month"], name="uniq_period_per_company_month")
        ]

    MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août",
              "Septembre", "Octobre", "Novembre", "Décembre"]

    def __str__(self):
        return self.label

    @property
    def label(self):
        return f"{self.MONTHS[self.month - 1]} {self.year}"

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT


class Payslip(CompanyOwnedModel):
    """Bulletin de paie : toutes les valeurs sont figées au calcul."""

    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="payslips")

    base_salary = models.DecimalField("Salaire de base", max_digits=12, decimal_places=0)
    unpaid_days = models.DecimalField("Jours non rémunérés", max_digits=5, decimal_places=1, default=0)
    unpaid_deduction = models.DecimalField("Retenue absences non payées", max_digits=12, decimal_places=0, default=0)
    extra_earnings = models.DecimalField("Primes et indemnités", max_digits=12, decimal_places=0, default=0)
    gross = models.DecimalField("Brut total", max_digits=12, decimal_places=0, default=0)
    contribution_base = models.DecimalField("Base cotisable", max_digits=12, decimal_places=0, default=0)
    cnss_employee = models.DecimalField("CNSS salarié", max_digits=12, decimal_places=0, default=0)
    its_base = models.DecimalField("Base ITS", max_digits=12, decimal_places=0, default=0)
    its = models.DecimalField("ITS", max_digits=12, decimal_places=0, default=0)
    other_deductions = models.DecimalField("Autres retenues", max_digits=12, decimal_places=0, default=0)
    net = models.DecimalField("Net à payer", max_digits=12, decimal_places=0, default=0)
    cnss_employer = models.DecimalField("CNSS employeur", max_digits=12, decimal_places=0, default=0)
    vps = models.DecimalField("VPS", max_digits=12, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Bulletin de paie"
        verbose_name_plural = "Bulletins de paie"
        ordering = ["employee__last_name", "employee__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["period", "employee"], name="uniq_payslip_per_period_employee")
        ]

    def __str__(self):
        return f"{self.employee} — {self.period}"

    @property
    def employer_cost(self):
        return self.gross + self.cnss_employer + self.vps


class PayslipItem(CompanyOwnedModel):
    """Prime, indemnité ou retenue ponctuelle saisie sur un bulletin en brouillon."""

    class Kind(models.TextChoices):
        EARNING = "earning", "Gain (prime, indemnité)"
        DEDUCTION = "deduction", "Retenue (avance, acompte)"

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField("Nature", max_length=10, choices=Kind.choices, default=Kind.EARNING)
    label = models.CharField("Libellé", max_length=120)
    amount = models.DecimalField("Montant (FCFA)", max_digits=12, decimal_places=0)
    subject_to_contributions = models.BooleanField(
        "Soumis à CNSS et ITS", default=True,
        help_text="Décochez pour une indemnité non imposable (selon la réglementation applicable).",
    )

    class Meta:
        verbose_name = "Élément de paie"
        verbose_name_plural = "Éléments de paie"
        ordering = ["kind", "id"]

    def __str__(self):
        return f"{self.label} ({self.amount})"
