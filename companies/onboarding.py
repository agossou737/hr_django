"""Création d'une entreprise cliente prête à l'emploi (utilisée par la console superadmin et la commande create_company)."""
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User
from companies.benin import benin_holidays
from companies.models import Company, Holiday


def unique_slug(name):
    base = slugify(name) or "entreprise"
    slug, n = base, 2
    while Company.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def seed_company(company):
    from leaves.services import create_default_types
    from payroll.models import PayrollSettings

    create_default_types(company)
    PayrollSettings.for_company(company)
    for date, label in benin_holidays(timezone.localdate().year):
        Holiday.objects.get_or_create(company=company, date=date, defaults={"name": label})


def onboard_company(name, admin_email, password, first_name="", last_name="", must_change=False, **extra):
    company = Company.objects.create(name=name, slug=unique_slug(name), **extra)
    admin = User.objects.create_user(email=admin_email, password=password, company=company, role=User.Role.ADMIN,
                                     first_name=first_name, last_name=last_name, must_change_password=must_change)
    seed_company(company)
    return company, admin
