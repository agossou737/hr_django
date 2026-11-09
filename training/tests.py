import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee
from notifications.models import Notification

from .models import Training, TrainingParticipant


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class TrainingTests(TestCase):
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

    def make(self):
        self.client.force_login(self.hr)
        self.client.post(reverse("training:create"), {"title": "Sécurité incendie", "start_date": "2026-04-01",
                                                      "end_date": "2026-04-02", "cost": "50000"})
        return Training.objects.get()

    def test_create_validation_enroll_and_certificate(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("training:create"), {"title": "X", "start_date": "2026-04-05", "end_date": "2026-04-01", "cost": 0})
        self.assertEqual(r.status_code, 200)
        t = self.make()
        self.client.post(reverse("training:enroll", args=[t.pk]), {"employees": [self.e1.pk, self.e2.pk, self.eb.pk]})
        self.assertEqual(t.participants.count(), 0)  # un employé d'une autre entreprise invalide toute la sélection
        self.client.post(reverse("training:enroll", args=[t.pk]), {"employees": [self.e1.pk]})
        self.client.post(reverse("training:enroll", args=[t.pk]), {"employees": [self.e1.pk]})  # idempotent
        self.assertEqual(t.participants.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.u1, title__startswith="Formation").exists())
        p = t.participants.get()
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("training:certificate", args=[p.pk])).status_code, 403)  # pas suivie
        self.client.force_login(self.hr)
        self.client.post(reverse("training:participant", args=[p.pk]), {"status": "completed", "note": "Réussi"})
        for user, code in ((self.u1, 200), (self.hr, 200), (self.u2, 403), (self.hr_b, 404)):
            self.client.force_login(user)
            r = self.client.get(reverse("training:certificate", args=[p.pk]))
            self.assertEqual(r.status_code, code, user)
        self.client.force_login(self.u1)
        self.assertEqual(len(self.client.get(reverse("training:mine")).context["items"]), 1)
        self.assertEqual(self.client.get(reverse("training:list")).status_code, 403)

    def test_remove_and_export(self):
        t = self.make()
        self.client.post(reverse("training:enroll", args=[t.pk]), {"employees": [self.e1.pk]})
        p = TrainingParticipant.objects.get()
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("training:list") + f"?export={fmt}").status_code, 200)
        self.client.post(reverse("training:participant", args=[p.pk]), {"action": "remove"})
        self.assertEqual(TrainingParticipant.objects.count(), 0)
