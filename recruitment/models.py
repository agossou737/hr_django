from django.db import models

from companies.models import CompanyOwnedModel
from config.files import private_storage


class JobOffer(CompanyOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Ouverte"
        CLOSED = "closed", "Clôturée"

    title = models.CharField("Intitulé du poste", max_length=150)
    department = models.ForeignKey(
        "employees.Department", verbose_name="Département", on_delete=models.SET_NULL, null=True, blank=True
    )
    contract_type = models.CharField("Type de contrat", max_length=20, choices=[
        ("cdi", "CDI"), ("cdd", "CDD"), ("internship", "Stage"), ("consultant", "Prestation")], default="cdi")
    location = models.CharField("Lieu", max_length=120, blank=True, default="Cotonou")
    description = models.TextField("Description et profil recherché", blank=True)
    openings = models.PositiveSmallIntegerField("Postes à pourvoir", default=1)
    closing_date = models.DateField("Date limite", null=True, blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Application(CompanyOwnedModel):
    class Stage(models.TextChoices):
        NEW = "new", "Nouvelle"
        SCREENING = "screening", "Présélection"
        INTERVIEW = "interview", "Entretien"
        OFFER = "offer", "Offre envoyée"
        HIRED = "hired", "Embauché"
        REJECTED = "rejected", "Refusée"

    job = models.ForeignKey(JobOffer, verbose_name="Offre", on_delete=models.CASCADE, related_name="applications")
    first_name = models.CharField("Prénoms", max_length=120)
    last_name = models.CharField("Nom", max_length=120)
    email = models.EmailField("E-mail", blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    cv = models.FileField("CV", upload_to="recruitment/cv/", storage=private_storage, blank=True)
    notes = models.TextField("Notes de l'équipe RH", blank=True)
    rating = models.PositiveSmallIntegerField("Note (1 à 5)", null=True, blank=True)
    stage = models.CharField("Étape", max_length=12, choices=Stage.choices, default=Stage.NEW)
    employee = models.OneToOneField(
        "employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="application"
    )
    applied_at = models.DateTimeField("Reçue le", auto_now_add=True)

    class Meta:
        verbose_name = "Candidature"
        verbose_name_plural = "Candidatures"
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.job}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
