from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounts.models import User
from companies.models import Company, Holiday
from leaves.models import LeaveType
from payroll.models import PayrollSettings


class CreateCompanyCommandTests(TestCase):
    def run_cmd(self, **kw):
        args = dict(name="Mon Client SARL", admin_email="Admin@Client.bj", admin_password="Sup3r-secret!")
        args.update(kw)
        call_command("create_company", stdout=StringIO(), **args)

    def test_onboarding(self):
        self.run_cmd()
        company = Company.objects.get(name="Mon Client SARL")
        admin = User.objects.get(email="admin@client.bj")
        self.assertEqual((admin.company, admin.role), (company, "admin"))
        self.assertGreater(LeaveType.objects.filter(company=company).count(), 3)
        self.assertEqual(Holiday.objects.filter(company=company).count(), 9)
        self.assertTrue(PayrollSettings.objects.filter(company=company).exists())

    def test_unique_slug_and_email(self):
        self.run_cmd()
        self.run_cmd(admin_email="autre@client.bj")
        self.assertEqual(set(Company.objects.values_list("slug", flat=True)), {"mon-client-sarl", "mon-client-sarl-2"})
        with self.assertRaises(CommandError):
            self.run_cmd(admin_email="autre@client.bj")

    def test_weak_password_rejected_and_nothing_created(self):
        with self.assertRaises(CommandError):
            self.run_cmd(admin_password="123")
        self.assertEqual(Company.objects.count(), 0)
