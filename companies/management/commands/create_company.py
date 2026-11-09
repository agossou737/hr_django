import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User
from companies.benin import benin_holidays
from companies.models import Company, Holiday
from leaves.services import create_default_types
from payroll.models import PayrollSettings


class Command(BaseCommand):
    help = "Onboarding d'un nouveau client : crée l'entreprise, son administrateur, les types de congés, les jours fériés du Bénin et les paramètres de paie."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Raison sociale")
        parser.add_argument("--admin-email", required=True)
        parser.add_argument("--admin-password", help="Sinon demandé en saisie masquée")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--city", default="Cotonou")

    @transaction.atomic
    def handle(self, *args, **opts):
        email = opts["admin_email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Un compte existe déjà avec l'e-mail {email}.")
        password = opts["admin_password"] or getpass.getpass("Mot de passe de l'administrateur : ")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages))

        from companies.onboarding import onboard_company

        company, _ = onboard_company(opts["name"], email, password, opts["first_name"], opts["last_name"],
                                     city=opts["city"])
        slug = company.slug
        self.stdout.write(self.style.SUCCESS(
            f"Entreprise « {company.name} » créée (identifiant {slug}). Administrateur : {email}."))
