import datetime
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from companies.models import Company
from employees.models import Employee

from .models import EmployeeDocument, expiring_documents


class DocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.u1 = User.objects.create_user("e1@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.u2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        mk = lambda c, f, **k: Employee.objects.create(company=c, first_name=f, last_name="X", gender="M",
                                                        hire_date=datetime.date(2025, 1, 1), **k)
        cls.e1, cls.e2, cls.eb = mk(cls.c1, "A", user=cls.u1), mk(cls.c1, "B", user=cls.u2), mk(cls.c2, "C")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._ctx = self.settings(PRIVATE_ROOT=self.tmp)
        self._ctx.enable()

    def tearDown(self):
        self._ctx.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def doc(self, employee=None, expiry=None, company=None):
        return EmployeeDocument.objects.create(
            company=company or self.c1, employee=employee or self.e1, title="Passeport", kind="id",
            file=SimpleUploadedFile("p.pdf", b"%PDF data"), expiry_date=expiry)

    def test_expiry_logic(self):
        today = timezone.localdate()
        ok = self.doc(expiry=today + datetime.timedelta(days=400))
        soon = self.doc(expiry=today + datetime.timedelta(days=10))
        gone = self.doc(expiry=today - datetime.timedelta(days=3))
        self.assertEqual((ok.expiry_state, soon.expiry_state, gone.expiry_state), ("", "soon", "expired"))
        self.assertEqual(set(expiring_documents(self.c1)), {soon, gone})
        self.assertEqual(expiring_documents(self.c2).count(), 0)

    def test_upload_rules(self):
        self.client.force_login(self.hr)
        url = reverse("documents:create")
        base = {"employee": self.e1.pk, "kind": "id", "title": "CNI"}
        r = self.client.post(url, {**base, "file": SimpleUploadedFile("a.exe", b"x")})
        self.assertContains(r, "Format non autorisé")
        r = self.client.post(url, {**base, "file": SimpleUploadedFile("a.pdf", b"x" * (6 * 1024 * 1024))})
        self.assertContains(r, "trop volumineux")
        r = self.client.post(url, {**base, "employee": self.eb.pk, "file": SimpleUploadedFile("a.pdf", b"x")})
        self.assertEqual(r.status_code, 200)  # employé d'une autre entreprise refusé
        r = self.client.post(url, {**base, "file": SimpleUploadedFile("a.pdf", b"x"),
                                   "issue_date": "2026-05-01", "expiry_date": "2026-01-01"})
        self.assertContains(r, "précède")
        r = self.client.post(url, {**base, "file": SimpleUploadedFile("a.pdf", b"x")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(EmployeeDocument.objects.get().uploaded_by, self.hr)

    def test_download_permissions(self):
        d = self.doc()
        url = reverse("documents:download", args=[d.pk])
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(url).status_code, 200)       # son propre document
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(url).status_code, 403)       # document d'un collègue
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.get(url).status_code, 404)       # autre entreprise
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_lists_and_isolation(self):
        self.doc()
        self.doc(employee=self.eb, company=self.c2)
        self.client.force_login(self.hr)
        r = self.client.get(reverse("documents:list"))
        self.assertEqual(len(r.context["documents"]), 1)
        self.assertEqual(self.client.get(reverse("documents:expiring")).status_code, 200)
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("documents:list")).status_code, 403)
        self.assertEqual(len(self.client.get(reverse("documents:mine")).context["documents"]), 1)

    def test_delete_removes_file(self):
        d = self.doc()
        path = d.file.path
        import os
        self.assertTrue(os.path.exists(path))
        self.client.force_login(self.hr)
        self.client.post(reverse("documents:delete", args=[d.pk]))
        self.assertFalse(os.path.exists(path))
        self.client.force_login(self.hr_b)
        d2 = self.doc()
        self.assertEqual(self.client.post(reverse("documents:delete", args=[d2.pk])).status_code, 404)

    def test_no_public_url(self):
        d = self.doc()
        with self.assertRaises(ValueError):
            d.file.url
