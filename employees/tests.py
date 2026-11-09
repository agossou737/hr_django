from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company

from .models import Contract, Department, Employee


def make_employee(company, **kw):
    data = dict(first_name="Jean", last_name="DOSSOU", gender="M", hire_date=date(2025, 1, 1))
    data.update(kw)
    return Employee.objects.create(company=company, **data)


class BaseCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr1 = User.objects.create_user("hr1@a.bj", "pass12345!", company=cls.c1, role=User.Role.HR)
        cls.emp_user = User.objects.create_user("e@a.bj", "pass12345!", company=cls.c1, role=User.Role.EMPLOYEE)
        cls.hr2 = User.objects.create_user("hr2@b.bj", "pass12345!", company=cls.c2, role=User.Role.HR)


class MatriculeTests(BaseCase):
    def test_auto_matricule_per_company(self):
        a1, a2 = make_employee(self.c1), make_employee(self.c1)
        b1 = make_employee(self.c2)
        self.assertEqual((a1.matricule, a2.matricule), ("EMP0001", "EMP0002"))
        self.assertEqual(b1.matricule, "EMP0001")


class AccessTests(BaseCase):
    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("employees:list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/compte/connexion/", r["Location"])

    def test_simple_employee_forbidden(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(reverse("employees:list")).status_code, 403)

    def test_hr_can_list(self):
        make_employee(self.c1)
        self.client.force_login(self.hr1)
        r = self.client.get(reverse("employees:list"))
        self.assertContains(r, "DOSSOU")

    def test_login_with_email(self):
        r = self.client.post(reverse("accounts:login"), {"username": "hr1@a.bj", "password": "pass12345!"})
        self.assertRedirects(r, reverse("dashboard"))


class IsolationTests(BaseCase):
    def test_cannot_see_other_company_employee(self):
        other = make_employee(self.c2, last_name="SECRET")
        self.client.force_login(self.hr1)
        self.assertEqual(self.client.get(reverse("employees:detail", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("employees:update", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("employees:delete", args=[other.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("employees:list")), "SECRET")

    def test_cannot_add_contract_to_other_company_employee(self):
        other = make_employee(self.c2)
        self.client.force_login(self.hr1)
        r = self.client.get(reverse("employees:contract_create", args=[other.pk]))
        self.assertEqual(r.status_code, 404)

    def test_form_rejects_other_company_department(self):
        foreign = Department.objects.create(company=self.c2, name="Externe")
        self.client.force_login(self.hr1)
        r = self.client.post(reverse("employees:create"), {
            "first_name": "A", "last_name": "B", "gender": "M", "nationality": "Béninoise",
            "dependents": 0, "hire_date": "2025-01-01", "status": "active", "department": foreign.pk,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Employee.objects.filter(company=self.c1).exists())


class CrudTests(BaseCase):
    def test_create_employee_attached_to_company(self):
        self.client.force_login(self.hr1)
        r = self.client.post(reverse("employees:create"), {
            "first_name": "Awa", "last_name": "TOGNI", "gender": "F", "nationality": "Béninoise",
            "dependents": 1, "hire_date": "2025-03-01", "status": "active",
        })
        emp = Employee.objects.get(last_name="TOGNI")
        self.assertRedirects(r, reverse("employees:detail", args=[emp.pk]))
        self.assertEqual(emp.company, self.c1)
        self.assertEqual(emp.matricule, "EMP0001")

    def test_cdd_requires_end_date(self):
        emp = make_employee(self.c1)
        self.client.force_login(self.hr1)
        r = self.client.post(reverse("employees:contract_create", args=[emp.pk]), {
            "contract_type": "cdd", "start_date": "2025-01-01", "base_salary": 100000,
            "weekly_hours": 40, "trial_period_months": 0, "is_current": "on",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Contract.objects.count(), 0)

    def test_new_current_contract_closes_previous(self):
        emp = make_employee(self.c1)
        self.client.force_login(self.hr1)
        base = {"contract_type": "cdi", "start_date": "2025-01-01", "base_salary": 100000,
                "weekly_hours": 40, "trial_period_months": 0, "is_current": "on"}
        self.client.post(reverse("employees:contract_create", args=[emp.pk]), base)
        self.client.post(reverse("employees:contract_create", args=[emp.pk]), {**base, "start_date": "2026-01-01"})
        self.assertEqual(emp.contracts.filter(is_current=True).count(), 1)
        self.assertEqual(emp.contracts.count(), 2)

    def test_dashboard_counts(self):
        make_employee(self.c1)
        self.client.force_login(self.hr1)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["total_employees"], 1)
