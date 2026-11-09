from django.core.management.base import BaseCommand

from explanations.services import send_reminders


class Command(BaseCommand):
    help = "Relance les employés qui n'ont pas répondu à une demande d'explication (à lancer chaque jour via cron)."

    def handle(self, *args, **options):
        self.stdout.write(f"{send_reminders()} relance(s) envoyée(s).")
