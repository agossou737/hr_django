from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company, Holiday


class SuperAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser("root@plat.bj", "pass12345!")
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.admin_a = User.objects.create_user("adm@a.bj", "pass12345!", company=cls.c1, role="admin")

    def test_superuser_lands_on_console_with_own_nav(self):
        self.client.force_login(self.root)
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, reverse("superadmin:dashboard"))
        r = self.client.get(reverse("superadmin:dashboard"))
        self.assertContains(r, "Console de la plateforme")
        self.assertEqual([s["label"] for s in r.context["nav_sections"]],
                         ["Plateforme", "Entreprises", "Utilisateurs", "Super-administrateurs"])
        self.assertTrue(self.client.post(reverse("accounts:login"), {"username": "ROOT@plat.bj", "password": "pass12345!"}).status_code in (200, 302))

    def test_no_default_django_admin(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_company_users_cannot_access(self):
        for user in (self.hr, self.admin_a):
            self.client.force_login(user)
            for name in ("dashboard", "companies", "company_create", "users", "admins", "admin_create"):
                self.assertEqual(self.client.get(reverse(f"superadmin:{name}")).status_code, 403, name)
            self.assertEqual(self.client.post(reverse("superadmin:company_toggle", args=[self.c1.pk])).status_code, 403)
            self.assertEqual(self.client.post(reverse("superadmin:user_reset", args=[self.hr.pk])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("superadmin:dashboard")).status_code, 302)

    def test_create_company_with_admin(self):
        self.client.force_login(self.root)
        r = self.client.post(reverse("superadmin:company_create"), {
            "name": "Gamma SARL", "city": "Porto-Novo", "admin_email": "boss@gamma.bj", "admin_first_name": "Ama"})
        self.assertEqual(r.status_code, 200)
        c = Company.objects.get(name="Gamma SARL")
        admin = User.objects.get(email="boss@gamma.bj")
        self.assertEqual((admin.company, admin.role, admin.must_change_password), (c, "admin", True))
        self.assertTrue(Holiday.objects.filter(company=c).exists())
        self.assertTrue(c.leaves_leavetype_set.exists())
        pwd = r.context["rows"][0][2]
        self.assertIn(pwd, mail.outbox[0].body)
        self.client.logout()
        self.assertTrue(self.client.login(username="boss@gamma.bj", password=pwd))
        # e-mail déjà pris
        self.client.force_login(self.root)
        r = self.client.post(reverse("superadmin:company_create"), {"name": "X", "admin_email": "HR@a.bj"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Company.objects.filter(name="X").exists())

    def test_suspension_blocks_company_users_only(self):
        self.client.force_login(self.root)
        self.client.post(reverse("superadmin:company_toggle", args=[self.c1.pk]))
        self.c1.refresh_from_db()
        self.assertFalse(self.c1.is_active)
        self.client.force_login(self.hr)
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, reverse("accounts:login"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)  # déconnecté
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(reverse("superadmin:company", args=[self.c1.pk])).status_code, 200)
        self.client.post(reverse("superadmin:company_toggle", args=[self.c1.pk]))
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_user_reset_toggle_and_self_protection(self):
        self.client.force_login(self.root)
        r = self.client.post(reverse("superadmin:user_reset", args=[self.hr.pk]))
        pwd = r.context["rows"][0][2]
        self.hr.refresh_from_db()
        self.assertTrue(self.hr.check_password(pwd))
        self.assertTrue(self.hr.must_change_password)
        self.client.post(reverse("superadmin:user_toggle", args=[self.hr.pk]))
        self.hr.refresh_from_db()
        self.assertFalse(self.hr.is_active)
        self.client.post(reverse("superadmin:user_toggle", args=[self.root.pk]))
        self.client.post(reverse("superadmin:user_reset", args=[self.root.pk]))
        self.root.refresh_from_db()
        self.assertTrue(self.root.is_active)
        self.assertTrue(self.root.check_password("pass12345!"))

    def test_lists_filters_and_new_admins(self):
        self.client.force_login(self.root)
        self.assertEqual(len(self.client.get(reverse("superadmin:companies") + "?q=alp").context["companies"]), 1)
        self.assertEqual(len(self.client.get(reverse("superadmin:companies") + "?status=suspended").context["companies"]), 0)
        self.assertEqual(len(self.client.get(reverse("superadmin:users") + "?role=hr").context["users"]), 1)
        self.assertEqual(self.client.get(reverse("superadmin:company_update", args=[self.c1.pk])).status_code, 200)
        r = self.client.post(reverse("superadmin:company_admin", args=[self.c1.pk]), {"email": "second@a.bj"})
        self.assertEqual(User.objects.get(email="second@a.bj").company, self.c1)
        r = self.client.post(reverse("superadmin:admin_create"), {"email": "root2@plat.bj"})
        n = User.objects.get(email="root2@plat.bj")
        self.assertTrue(n.is_superuser and n.company is None and n.must_change_password)
        self.assertEqual(len(self.client.get(reverse("superadmin:admins")).context["admins"]), 2)

    def test_create_company_command_still_works(self):
        from django.core.management import call_command

        call_command("create_company", name="Delta", admin_email="d@delta.bj", admin_password="Mdp-solide-2026", verbosity=0)
        self.assertTrue(User.objects.get(email="d@delta.bj").check_password("Mdp-solide-2026"))
        self.assertTrue(Holiday.objects.filter(company__name="Delta").exists())
