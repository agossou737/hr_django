from datetime import date

from django.core.management.base import BaseCommand

from accounts.models import User
from companies.models import Company
from employees.models import Contract, Department, Employee, Position


class Command(BaseCommand):
    help = "Crée une entreprise de démonstration avec un compte RH et quelques employés."

    def handle(self, *args, **options):
        company, _ = Company.objects.get_or_create(
            slug="demo",
            defaults={"name": "Entreprise Démo SARL", "city": "Cotonou", "email": "contact@demo.bj"},
        )
        if not User.objects.filter(email="rh@demo.bj").exists():
            User.objects.create_user(
                email="rh@demo.bj", password="demo12345", first_name="Responsable", last_name="RH",
                company=company, role=User.Role.HR,
            )
        compta, _ = Department.objects.get_or_create(company=company, name="Comptabilité")
        it, _ = Department.objects.get_or_create(company=company, name="Informatique")
        comptable, _ = Position.objects.get_or_create(
            company=company, title="Comptable", defaults={"department": compta, "base_salary": 250000}
        )
        dev, _ = Position.objects.get_or_create(
            company=company, title="Développeur", defaults={"department": it, "base_salary": 400000}
        )
        if not Employee.objects.filter(company=company).exists():
            for first, last, gender, dept, pos, salary in [
                ("Koffi", "ADJOVI", "M", compta, comptable, 250000),
                ("Aïcha", "SOGLO", "F", it, dev, 400000),
            ]:
                emp = Employee.objects.create(
                    company=company, first_name=first, last_name=last, gender=gender,
                    department=dept, position=pos, hire_date=date(2025, 1, 6),
                )
                Contract.objects.create(
                    company=company, employee=emp, contract_type="cdi",
                    start_date=emp.hire_date, base_salary=salary,
                )
        if not User.objects.filter(email="borne@demo.bj").exists():
            User.objects.create_user(
                email="borne@demo.bj", password="demo12345", first_name="Borne", last_name="Accueil",
                company=company, role=User.Role.KIOSK,
            )
        from companies.benin import benin_holidays
        from companies.models import Holiday
        from leaves.services import create_default_types
        from payroll.models import PayrollSettings

        create_default_types(company)
        PayrollSettings.for_company(company)
        for d, label in benin_holidays(date.today().year):
            Holiday.objects.get_or_create(company=company, date=d, defaults={"name": label})
        self.stdout.write(self.style.SUCCESS(
            "Démo prête : rh@demo.bj (RH) et borne@demo.bj (borne de pointage), mot de passe demo12345"))
