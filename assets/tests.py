import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee
from notifications.models import Notification

from . import services
from .models import Asset, AssetAssignment

D = datetime.date(2026, 3, 2)


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class AssetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.u1 = User.objects.create_user("e1@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.u2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", user=cls.u1)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU", user=cls.u2)
        cls.eb = emp(cls.c2, "Paul", "KPADE")
        cls.laptop = Asset.objects.create(company=cls.c1, name="Laptop Dell", tag="PC-001", value=450000)

    def test_assign_return_cycle(self):
        a = services.assign(self.laptop, self.e1, self.hr, D)
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.status, "assigned")
        self.assertTrue(Notification.objects.filter(user=self.u1, title__contains="Matériel remis").exists())
        with self.assertRaises(services.AssetError):
            services.assign(self.laptop, self.e2, self.hr, D)
        services.give_back(a, D, "good")
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.status, "available")
        with self.assertRaises(services.AssetError):
            services.give_back(a, D, "good")
        b = services.assign(self.laptop, self.e2, self.hr, D)
        services.give_back(b, D, "poor")
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.status, "maintenance")

    def test_cross_company_assignment_refused(self):
        with self.assertRaises(services.AssetError):
            services.assign(self.laptop, self.eb, self.hr, D)

    def test_views_flow_and_pdf_access(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("assets:assign", args=[self.laptop.pk]),
                             {"employee": self.e1.pk, "assigned_at": "2026-03-02"})
        self.assertEqual(r.status_code, 302)
        a = AssetAssignment.objects.get()
        self.assertTrue(self.client.get(reverse("assets:pdf", args=[a.pk])).content.startswith(b"%PDF"))
        r = self.client.post(reverse("assets:return", args=[a.pk]), {"returned_at": "2026-03-10", "condition": "good"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(self.client.get(reverse("assets:pdf", args=[a.pk])).content.startswith(b"%PDF"))
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("assets:pdf", args=[a.pk])).status_code, 200)
        self.assertEqual(len(self.client.get(reverse("assets:mine")).context["assignments"]), 1)
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(reverse("assets:pdf", args=[a.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("assets:list")).status_code, 403)
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.get(reverse("assets:detail", args=[self.laptop.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("assets:pdf", args=[a.pk])).status_code, 404)

    def test_tag_unique_delete_and_retire(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("assets:create"), {"name": "Autre", "tag": "PC-001", "category": "computer",
                                                        "value": 10, "condition": "good"})
        self.assertEqual(r.status_code, 200)
        a = services.assign(self.laptop, self.e1, self.hr, D)
        self.client.post(reverse("assets:retire", args=[self.laptop.pk]))
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.status, "assigned")
        self.client.post(reverse("assets:delete", args=[self.laptop.pk]))
        self.assertTrue(Asset.objects.filter(pk=self.laptop.pk).exists())
        services.give_back(a, D, "good")
        self.client.post(reverse("assets:retire", args=[self.laptop.pk]))
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.status, "retired")
        fresh = Asset.objects.create(company=self.c1, name="Stylo")
        self.client.post(reverse("assets:delete", args=[fresh.pk]))
        self.assertFalse(Asset.objects.filter(pk=fresh.pk).exists())

    def test_list_filters_and_export(self):
        self.client.force_login(self.hr)
        self.assertEqual(len(self.client.get(reverse("assets:list") + "?q=dell").context["assets"]), 1)
        self.assertEqual(len(self.client.get(reverse("assets:list") + "?status=retired").context["assets"]), 0)
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("assets:list") + f"?export={fmt}").status_code, 200)
