from django.conf import settings
from django.db import models

from companies.models import CompanyOwnedModel


class Notification(CompanyOwnedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField("Titre", max_length=150)
    message = models.TextField("Message", blank=True)
    url = models.CharField("Lien", max_length=255, blank=True)
    is_read = models.BooleanField("Lue", default=False)
    created_at = models.DateTimeField("Date", auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user} — {self.title}"
