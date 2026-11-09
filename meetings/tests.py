import datetime

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee
from notifications.models import Notification

from .models import Meeting, MeetingAction


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class MeetingTests(TestCase):
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
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", user=cls.u1)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU", user=cls.u2)
        cls.eb = emp(cls.c2, "Paul", "KPADE")

    def create(self, user=None, **kw):
        self.client.force_login(user or self.mgr)
        data = {"title": "Point hebdo", "date": "2026-03-05", "start_time": "09:00", "end_time": "10:00",
                "location": "Salle A", "agenda": "1. Bilan", "participants": [self.e1.pk]}
        data.update(kw)
        return self.client.post(reverse("meetings:create"), data)

    def test_create_notifies_participants_only(self):
        r = self.create()
        self.assertEqual(r.status_code, 302)
        m = Meeting.objects.get()
        self.assertEqual(m.organizer, self.mgr)
        self.assertEqual(Notification.objects.filter(title__startswith="Convocation").count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.u1).exists())
        self.assertFalse(Notification.objects.filter(user=self.u2).exists())

    def test_employee_cannot_organize_and_visibility(self):
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("meetings:create")).status_code, 403)
        self.create()
        m = Meeting.objects.get()
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("meetings:detail", args=[m.pk])).status_code, 200)
        self.assertEqual(len(self.client.get(reverse("meetings:mine")).context["meetings"]), 1)
        self.client.force_login(self.u2)  # non invité
        self.assertEqual(self.client.get(reverse("meetings:detail", args=[m.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("meetings:pdf", args=[m.pk, "convocation"])).status_code, 403)
        self.assertEqual(len(self.client.get(reverse("meetings:mine")).context["meetings"]), 0)
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.get(reverse("meetings:detail", args=[m.pk])).status_code, 404)
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("meetings:detail", args=[m.pk])).status_code, 200)

    def test_minutes_publish_actions_and_pdf(self):
        self.create()
        m = Meeting.objects.get()
        self.client.force_login(self.u1)  # un participant ne rédige pas
        self.assertEqual(self.client.post(reverse("meetings:minutes", args=[m.pk]), {"minutes": "x"}).status_code, 403)
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("meetings:pdf", args=[m.pk, "compte-rendu"])).status_code, 403)  # pas encore
        self.client.post(reverse("meetings:minutes", args=[m.pk]), {"minutes": "Décisions prises : budget validé."})
        m.refresh_from_db()
        self.assertEqual(m.status, "held")
        self.assertTrue(Notification.objects.filter(user=self.u1, title__startswith="Compte rendu").exists())
        self.client.post(reverse("meetings:action_add", args=[m.pk]),
                         {"description": "Envoyer le budget", "owner": self.e1.pk, "due_date": "2026-03-12"})
        act = MeetingAction.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.u1, title__startswith="Action issue").exists())
        self.client.force_login(self.u1)  # le responsable coche son action
        self.client.post(reverse("meetings:action_toggle", args=[act.pk]))
        act.refresh_from_db()
        self.assertTrue(act.done)
        r = self.client.get(reverse("meetings:pdf", args=[m.pk, "compte-rendu"]))
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.client.force_login(self.u2)
        self.assertEqual(self.client.post(reverse("meetings:action_toggle", args=[act.pk])).status_code, 403)

    def test_foreign_participant_not_selectable_and_cancel(self):
        r = self.create(participants=[self.eb.pk])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Meeting.objects.count(), 0)
        self.create()
        m = Meeting.objects.get()
        self.client.post(reverse("meetings:cancel", args=[m.pk]))
        m.refresh_from_db()
        self.assertEqual(m.status, "cancelled")
        self.assertTrue(Notification.objects.filter(user=self.u1, title__startswith="Réunion annulée").exists())
        self.assertEqual(self.client.get(reverse("meetings:update", args=[m.pk])).status_code, 403)

    def test_hr_list_export(self):
        self.create()
        self.client.force_login(self.hr)
        self.assertEqual(len(self.client.get(reverse("meetings:list")).context["meetings"]), 1)
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("meetings:list") + f"?export={fmt}").status_code, 200)
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("meetings:list")).status_code, 403)
