import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee
from explanations.models import Explanation
from notifications.models import Notification

from .models import Sanction


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class DisciplineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.mgr = User.objects.create_user("m@a.bj", "pass12345!", company=cls.c1, role="manager")
        cls.u1 = User.objects.create_user("e1@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.u2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        cls.e_mgr = emp(cls.c1, "Marc", "CHEF", user=cls.mgr)
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", user=cls.u1, manager=cls.e_mgr)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU", user=cls.u2)

    def create(self, **kw):
        self.client.force_login(self.hr)
        data = {"employee": self.e1.pk, "kind": "written", "date": "2026-03-02", "reason": "Retards répétés",
                "details": "3 retards en 2 semaines", "suspension_days": 0}
        data.update(kw)
        return self.client.post(reverse("discipline:create"), data)

    def test_issue_notify_acknowledge_pdf(self):
        self.assertEqual(self.create().status_code, 302)
        s = Sanction.objects.get()
        self.assertEqual(s.issued_by, self.hr)
        self.assertTrue(Notification.objects.filter(user=self.u1, title__startswith="Mesure disciplinaire").exists())
        self.client.force_login(self.u1)
        self.assertEqual(len(self.client.get(reverse("discipline:mine")).context["sanctions"]), 1)
        self.client.post(reverse("discipline:acknowledge", args=[s.pk]))
        s.refresh_from_db()
        self.assertIsNotNone(s.acknowledged_at)
        self.assertTrue(self.client.get(reverse("discipline:pdf", args=[s.pk])).content.startswith(b"%PDF"))

    def test_confidentiality(self):
        self.create()
        s = Sanction.objects.get()
        for user, code in ((self.mgr, 403), (self.u2, 403), (self.hr_b, 404), (self.hr, 200), (self.u1, 200)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("discipline:pdf", args=[s.pk])).status_code, code, user)
        for user in (self.mgr, self.u1, self.u2):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("discipline:list")).status_code, 403)
            self.assertEqual(self.client.get(reverse("discipline:create")).status_code, 403)
        self.client.force_login(self.u2)
        self.client.post(reverse("discipline:acknowledge", args=[s.pk]))  # pas la sienne
        s.refresh_from_db()
        self.assertIsNone(s.acknowledged_at)
        self.assertEqual(len(self.client.get(reverse("discipline:mine")).context["sanctions"]), 0)

    def test_validation_and_link(self):
        self.assertEqual(self.create(kind="suspension", suspension_days=0).status_code, 200)
        self.assertEqual(Sanction.objects.count(), 0)
        other = Explanation.objects.create(company=self.c1, employee=self.e2, date="2026-03-01", subject="x",
                                           deadline="2026-03-03")
        self.assertEqual(self.create(explanation=other.pk).status_code, 200)  # explication d'un autre employé
        mine = Explanation.objects.create(company=self.c1, employee=self.e1, date="2026-03-01", subject="y",
                                          deadline="2026-03-03")
        self.assertEqual(self.create(explanation=mine.pk, kind="suspension", suspension_days=2).status_code, 302)
        s = Sanction.objects.get()
        self.assertEqual(s.explanation, mine)
        self.client.force_login(self.hr)
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("discipline:list") + f"?export={fmt}").status_code, 200)
        self.client.post(reverse("discipline:delete", args=[s.pk]))
        self.assertEqual(Sanction.objects.count(), 0)
