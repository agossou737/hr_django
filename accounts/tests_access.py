import datetime

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts import access
from accounts.models import User
from companies.models import Company
from employees.models import Employee


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.u = User.objects.create_user("simple@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", email="jean@a.bj")
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU")
        cls.eb = emp(cls.c2, "Paul", "KPADE", email="paul@b.bj")

    def test_create_access_login_and_forced_change(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("employees:access", args=[self.e1.pk]), {"email": "jean@a.bj", "role": "employee"})
        self.assertEqual(r.status_code, 200)
        self.e1.refresh_from_db()
        user = self.e1.user
        self.assertEqual((user.company, user.role, user.must_change_password), (self.c1, "employee", True))
        pwd = r.context["rows"][0][2]
        self.assertIn(pwd, mail.outbox[0].body)
        self.client.logout()
        # connexion avec le mot de passe temporaire, même en changeant la casse de l'e-mail
        self.assertTrue(self.client.login(username="JEAN@a.bj", password=pwd))
        r = self.client.get(reverse("leaves:mine"))
        self.assertRedirects(r, reverse("accounts:password_change"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("accounts:password_change")).status_code, 200)
        r = self.client.post(reverse("accounts:password_change"), {
            "old_password": pwd, "new_password1": "Nouveau-mdp-2026", "new_password2": "Nouveau-mdp-2026"})
        self.assertEqual(r.status_code, 302)
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)
        self.assertEqual(self.client.get(reverse("leaves:mine")).status_code, 200)  # accès normal, session conservée

    def test_weak_or_wrong_old_password_refused(self):
        _, pwd = access.create_access(self.e1, send_email=False)
        self.client.login(username="jean@a.bj", password=pwd)
        self.client.post(reverse("accounts:password_change"), {"old_password": "faux", "new_password1": "Nouveau-mdp-2026",
                                                               "new_password2": "Nouveau-mdp-2026"})
        self.e1.user.refresh_from_db()
        self.assertTrue(self.e1.user.must_change_password)
        self.client.post(reverse("accounts:password_change"), {"old_password": pwd, "new_password1": "12345678",
                                                               "new_password2": "12345678"})
        self.e1.user.refresh_from_db()
        self.assertTrue(self.e1.user.must_change_password)

    def test_errors_duplicates_and_roles(self):
        with self.assertRaises(access.AccessError):
            access.create_access(self.e2)  # pas d'e-mail
        with self.assertRaises(access.AccessError):
            access.create_access(self.e2, "SIMPLE@a.bj")  # déjà pris (casse ignorée)
        with self.assertRaises(access.AccessError):
            access.create_access(self.e2, "x@a.bj", role="admin")
        access.create_access(self.e1, send_email=False)
        with self.assertRaises(access.AccessError):
            access.create_access(self.e1, send_email=False)
        self.assertEqual(len(access.temp_password()), 10)

    def test_permissions_and_isolation(self):
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse("employees:access", args=[self.e1.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("employees:access_bulk")).status_code, 403)
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.get(reverse("employees:access", args=[self.e1.pk])).status_code, 404)

    def test_bulk_creation_skips_missing_email_and_other_company(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("employees:access_bulk"))
        self.assertEqual(len(r.context["rows"]), 1)
        self.assertEqual([e.pk for e, _ in r.context["skipped"]], [self.e2.pk])
        self.eb.refresh_from_db()
        self.assertIsNone(self.eb.user)
        self.assertEqual(self.client.get(reverse("employees:detail", args=[self.e1.pk])).status_code, 200)

    def test_login_is_case_insensitive(self):
        self.assertTrue(self.client.login(username="HR@A.BJ", password="pass12345!"))
