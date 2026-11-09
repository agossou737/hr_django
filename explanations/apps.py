from django.apps import AppConfig


class ExplanationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "explanations"
    verbose_name = "Demandes d'explication"

    def ready(self):
        from . import signals  # noqa: F401
