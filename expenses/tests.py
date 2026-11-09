import datetime
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee
from notifications.models import Notification

from .models import ExpenseClaim


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


@override_settings(PRIVATE_ROOT=tempfile.mkdtemp())
class ExpenseTests(TestCase):
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

    def submit(self, **kw):
        self.client.force_login(self.u1)
        data = {"date": "2026-01-10", "title": "Taxi client", "category": "transport", "amount": "5000"}
        data.update(kw)
        return self.client.post(reverse("expenses:create"), data)

    def test_full_cycle(self):
        self.assertEqual(self.submit().status_code, 302)
        c = ExpenseClaim.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.mgr, title__startswith="Note de frais").exists())
        self.client.force_login(self.mgr)
        self.assertEqual(len(self.client.get(reverse("expenses:pending")).context["claims"]), 1)
        self.client.post(reverse("expenses:review", args=[c.pk, "approve"]), {"comment": "OK"})
        c.refresh_from_db()
        self.assertEqual(c.status, "approved")
        self.client.force_login(self.hr)
        self.client.post(reverse("expenses:paid", args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.status, "paid")
        self.assertTrue(Notification.objects.filter(user=self.u1, title="Note de frais remboursée").exists())
        self.assertTrue(self.client.get(reverse("expenses:pdf", args=[c.pk])).content.startswith(b"%PDF"))

    def test_validation(self):
        self.assertEqual(self.submit(amount="0").status_code, 200)
        self.assertEqual(self.submit(date="2999-01-01").status_code, 200)
        self.assertEqual(self.submit(receipt=SimpleUploadedFile("x.exe", b"MZ")).status_code, 200)
        self.assertEqual(ExpenseClaim.objects.count(), 0)

    def test_access_control_and_receipt(self):
        self.submit(receipt=SimpleUploadedFile("recu.pdf", b"%PDF-1.4 test"))
        c = ExpenseClaim.objects.get()
        self.assertTrue(c.receipt)
        for user, code in ((self.u1, 200), (self.mgr, 200), (self.hr, 200), (self.u2, 403), (self.hr_b, 404)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("expenses:receipt", args=[c.pk])).status_code, code, user)
            self.assertEqual(self.client.get(reverse("expenses:pdf", args=[c.pk])).status_code, code, user)
        self.client.force_login(self.u1)  # pas d'auto-approbation
        self.assertEqual(self.client.post(reverse("expenses:review", args=[c.pk, "approve"])).status_code, 403)
        self.client.force_login(self.u2)  # un collègue non plus
        self.assertEqual(self.client.post(reverse("expenses:review", args=[c.pk, "approve"])).status_code, 403)

    def test_cannot_pay_unapproved_and_exports(self):
        self.submit()
        c = ExpenseClaim.objects.get()
        self.client.force_login(self.hr)
        self.client.post(reverse("expenses:paid", args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.status, "pending")
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("expenses:list") + f"?export={fmt}").status_code, 200)
