from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel


class Meeting(CompanyOwnedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planifiée"
        HELD = "held", "Tenue (compte rendu publié)"
        CANCELLED = "cancelled", "Annulée"

    title = models.CharField("Titre", max_length=200)
    date = models.DateField("Date")
    start_time = models.TimeField("Début")
    end_time = models.TimeField("Fin", null=True, blank=True)
    location = models.CharField("Lieu / lien visio", max_length=200, blank=True)
    agenda = models.TextField("Ordre du jour", blank=True)
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Organisateur", on_delete=models.SET_NULL,
                                  null=True, related_name="organized_meetings")
    participants = models.ManyToManyField("employees.Employee", verbose_name="Participants", related_name="meetings",
                                          blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PLANNED)
    minutes = models.TextField("Compte rendu", blank=True)
    minutes_published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réunion"
        verbose_name_plural = "Réunions"
        ordering = ["-date", "-start_time"]

    def __str__(self):
        return f"{self.title} ({self.date:%d/%m/%Y})"

    @property
    def reference(self):
        return f"REU-{self.date.year}-{self.pk or 0:05d}"


class MeetingAction(CompanyOwnedModel):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="actions")
    description = models.CharField("Action / décision", max_length=255)
    owner = models.ForeignKey("employees.Employee", verbose_name="Responsable", on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="meeting_actions")
    due_date = models.DateField("Échéance", null=True, blank=True)
    done = models.BooleanField("Faite", default=False)

    class Meta:
        verbose_name = "Action de réunion"
        verbose_name_plural = "Actions de réunion"
        ordering = ["done", "due_date", "id"]

    def __str__(self):
        return self.description
