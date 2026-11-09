from django.db import models

from companies.models import CompanyOwnedModel


class Training(CompanyOwnedModel):
    title = models.CharField("Intitulé", max_length=200)
    provider = models.CharField("Organisme / formateur", max_length=150, blank=True)
    start_date = models.DateField("Début")
    end_date = models.DateField("Fin")
    location = models.CharField("Lieu", max_length=150, blank=True)
    cost = models.DecimalField("Coût (FCFA)", max_digits=12, decimal_places=0, default=0)
    description = models.TextField("Description", blank=True)

    class Meta:
        verbose_name = "Formation"
        verbose_name_plural = "Formations"
        ordering = ["-start_date"]

    def __str__(self):
        return self.title


class TrainingParticipant(CompanyOwnedModel):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Inscrit"
        COMPLETED = "completed", "Formation suivie"
        ABSENT = "absent", "Absent"

    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name="participants")
    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="trainings")
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.REGISTERED)
    note = models.CharField("Observation", max_length=255, blank=True)

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
        constraints = [models.UniqueConstraint(fields=["training", "employee"], name="uniq_training_participant")]
        ordering = ["employee__last_name"]

    def __str__(self):
        return f"{self.employee} — {self.training}"
