import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee

from .models import CRITERIA, Evaluation


class EvaluationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.mgr = User.objects.create_user("m@a.bj", "pass12345!", company=cls.c1, role="manager")
        cls.mgr2 = User.objects.create_user("m2@a.bj", "pass12345!", company=cls.c1, role="manager")
        cls.u1 = User.objects.create_user("e1@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.u2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        mk = lambda c, f, **k: Employee.objects.create(company=c, first_name=f, last_name="X", gender="M",
                                                        hire_date=datetime.date(2025, 1, 1), **k)
        cls.m = mk(cls.c1, "Chef", user=cls.mgr)
        cls.m2 = mk(cls.c1, "Autre", user=cls.mgr2)
        cls.e1 = mk(cls.c1, "A", user=cls.u1, manager=cls.m)
        cls.e2 = mk(cls.c1, "B", user=cls.u2, manager=cls.m2)
        cls.eb = mk(cls.c2, "C")

    def payload(self, employee, **kw):
        data = {"employee": employee.pk, "period": "Année 2026", "date": "2026-06-01",
                "strengths": "Rigueur", "improvements": "", "objectives": ""}
        data.update({f"score_{k}": 4 for k, _ in CRITERIA})
        data.update(kw)
        return data

    def test_manager_scope(self):
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("evaluations:create"), self.payload(self.e2))   # pas son équipe
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evaluation.objects.count(), 0)
        r = self.client.post(reverse("evaluations:create"), self.payload(self.e1))
        self.assertEqual(r.status_code, 302)
        ev = Evaluation.objects.get()
        self.assertEqual((ev.evaluator, ev.average, ev.status), (self.mgr, 4.0, "draft"))

    def test_hr_all_but_not_other_company(self):
        self.client.force_login(self.hr)
        self.assertEqual(self.client.post(reverse("evaluations:create"), self.payload(self.e2)).status_code, 302)
        self.assertEqual(self.client.post(reverse("evaluations:create"), self.payload(self.eb)).status_code, 200)
        self.assertEqual(Evaluation.objects.count(), 1)

    def test_score_validation(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("evaluations:create"), self.payload(self.e1, score_quality=9))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evaluation.objects.count(), 0)

    def test_workflow(self):
        self.client.force_login(self.hr)
        self.client.post(reverse("evaluations:create"), self.payload(self.e1))
        ev = Evaluation.objects.get()
        # brouillon invisible pour l'employé
        self.client.force_login(self.u1)
        self.assertEqual(len(self.client.get(reverse("evaluations:mine")).context["evaluations"]), 0)
        self.assertEqual(self.client.get(reverse("evaluations:my_detail", args=[ev.pk])).status_code, 404)
        # transmission
        self.client.force_login(self.hr)
        self.client.post(reverse("evaluations:submit", args=[ev.pk]))
        ev.refresh_from_db()
        self.assertEqual(ev.status, "submitted")
        self.assertEqual(self.client.get(reverse("evaluations:update", args=[ev.pk])).status_code, 403)  # figée
        # l'employé la voit et l'acquitte ; un collègue non
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(reverse("evaluations:my_detail", args=[ev.pk])).status_code, 404)
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("evaluations:my_detail", args=[ev.pk])).status_code, 200)
        self.client.post(reverse("evaluations:acknowledge", args=[ev.pk]), {"comment": "Merci"})
        ev.refresh_from_db()
        self.assertEqual((ev.status, ev.employee_comment), ("acknowledged", "Merci"))

    def test_access_control(self):
        self.client.force_login(self.hr)
        self.client.post(reverse("evaluations:create"), self.payload(self.e1))
        ev = Evaluation.objects.get()
        for user, code in ((self.mgr, 200), (self.mgr2, 403), (self.u1, 403), (self.hr_b, 404)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("evaluations:detail", args=[ev.pk])).status_code, code, user.email)
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("evaluations:list")).status_code, 403)
        self.assertEqual(self.client.post(reverse("evaluations:submit", args=[ev.pk])).status_code, 403)

    def test_list_scoped(self):
        self.client.force_login(self.hr)
        self.client.post(reverse("evaluations:create"), self.payload(self.e1))
        self.client.post(reverse("evaluations:create"), self.payload(self.e2))
        self.client.force_login(self.mgr)
        self.assertEqual(len(self.client.get(reverse("evaluations:list")).context["evaluations"]), 1)


class ExportTests(TestCase):
    def test_employee_csv(self):
        c = Company.objects.create(name="Alpha", slug="alpha")
        hr = User.objects.create_user("hr@a.bj", "pass12345!", company=c, role="hr")
        Employee.objects.create(company=c, first_name="Jean", last_name="DOSSOU", gender="M", hire_date=datetime.date(2025, 1, 1))
        other = Company.objects.create(name="Beta", slug="beta")
        Employee.objects.create(company=other, first_name="Paul", last_name="SECRET", gender="M", hire_date=datetime.date(2025, 1, 1))
        self.client.force_login(hr)
        body = self.client.get(reverse("employees:list") + "?export=csv").content.decode("utf-8-sig")
        self.assertIn("DOSSOU", body)
        self.assertNotIn("SECRET", body)
        self.assertEqual(self.client.get(reverse("leaves:list") + "?export=csv").status_code, 200)
