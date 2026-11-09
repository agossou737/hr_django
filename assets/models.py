from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel


class Asset(CompanyOwnedModel):
    class Category(models.TextChoices):
        COMPUTER = "computer", "Ordinateur"
        PHONE = "phone", "Téléphone / tablette"
        VEHICLE = "vehicle", "Véhicule / moto"
        FURNITURE = "furniture", "Mobilier"
        TOOL = "tool", "Outillage / équipement"
        CLOTHING = "clothing", "Tenue / EPI"
        KEYS = "keys", "Clés / badge"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        ASSIGNED = "assigned", "Affecté"
        MAINTENANCE = "maintenance", "En maintenance"
        RETIRED = "retired", "Réformé"

    class Condition(models.TextChoices):
        NEW = "new", "Neuf"
        GOOD = "good", "Bon état"
        FAIR = "fair", "État moyen"
        POOR = "poor", "Mauvais état"

    name = models.CharField("Désignation", max_length=150)
    tag = models.CharField("Code inventaire", max_length=40, blank=True)
    category = models.CharField("Catégorie", max_length=12, choices=Category.choices, default=Category.OTHER)
    serial_number = models.CharField("N° de série", max_length=80, blank=True)
    purchase_date = models.DateField("Date d'achat", null=True, blank=True)
    value = models.DecimalField("Valeur (FCFA)", max_digits=12, decimal_places=0, default=0)
    condition = models.CharField("État", max_length=8, choices=Condition.choices, default=Condition.GOOD)
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.TextField("Remarques", blank=True)

    class Meta:
        verbose_name = "Matériel"
        verbose_name_plural = "Matériels"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "tag"], condition=~models.Q(tag=""),
                                               name="uniq_asset_tag_per_company")]

    def __str__(self):
        return f"{self.name} ({self.tag})" if self.tag else self.name

    @property
    def current_assignment(self):
        return self.assignments.filter(returned_at__isnull=True).select_related("employee").first()


class AssetAssignment(CompanyOwnedModel):
    asset = models.ForeignKey(Asset, verbose_name="Matériel", on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="asset_assignments")
    assigned_at = models.DateField("Remis le")
    condition_out = models.CharField("État à la remise", max_length=8, choices=Asset.Condition.choices,
                                     default=Asset.Condition.GOOD)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    returned_at = models.DateField("Restitué le", null=True, blank=True)
    condition_in = models.CharField("État à la restitution", max_length=8, choices=Asset.Condition.choices, blank=True)
    notes = models.CharField("Observations", max_length=255, blank=True)

    class Meta:
        verbose_name = "Affectation de matériel"
        verbose_name_plural = "Affectations de matériel"
        ordering = ["-assigned_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["asset"], condition=models.Q(returned_at__isnull=True),
                                               name="one_open_assignment_per_asset")]

    def __str__(self):
        return f"{self.asset} → {self.employee}"

    @property
    def is_open(self):
        return self.returned_at is None

    @property
    def reference(self):
        return f"MAT-{self.assigned_at.year}-{self.pk or 0:05d}"
