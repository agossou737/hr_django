from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel
from config.files import private_storage


class ExpenseClaim(CompanyOwnedModel):
    class Category(models.TextChoices):
        TRANSPORT = "transport", "Transport / carburant"
        MEAL = "meal", "Repas / réception"
        LODGING = "lodging", "Hébergement"
        SUPPLIES = "supplies", "Fournitures"
        COMMS = "comms", "Communication"
        OTHER = "other", "Autre"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Refusée"
        PAID = "paid", "Remboursée"
        CANCELLED = "cancelled", "Annulée"

    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="expense_claims")
    date = models.DateField("Date de la dépense")
    title = models.CharField("Objet", max_length=150)
    category = models.CharField("Catégorie", max_length=12, choices=Category.choices, default=Category.OTHER)
    amount = models.DecimalField("Montant (FCFA)", max_digits=12, decimal_places=0)
    receipt = models.FileField("Justificatif", upload_to="expenses/", storage=private_storage, blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.CharField("Commentaire", max_length=255, blank=True)
    paid_at = models.DateField("Remboursée le", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Note de frais"
        verbose_name_plural = "Notes de frais"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.reference} — {self.title}"

    @property
    def reference(self):
        return f"NDF-{self.date.year}-{self.pk or 0:05d}"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING
