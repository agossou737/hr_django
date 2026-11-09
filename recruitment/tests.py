import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Employee

from .models import Application, JobOffer


class RecruitmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.emp = User.objects.create_user("e@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        cls.job = JobOffer.objects.create(company=cls.c1, title="Comptable")
        cls.job_b = JobOffer.objects.create(company=cls.c2, title="Chauffeur")

    def app(self, **kw):
        data = dict(company=self.c1, job=self.job, first_name="Koffi", last_name="ADJOVI")
        data.update(kw)
        return Application.objects.create(**data)

    def test_access(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("recruitment:job_list")).status_code, 403)
        self.client.force_login(self.hr)
        for n in ("job_list", "job_create", "application_list", "application_create"):
            self.assertEqual(self.client.get(reverse(f"recruitment:{n}")).status_code, 200, n)

    def test_cannot_use_other_company_job(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("recruitment:application_create"),
                             {"job": self.job_b.pk, "first_name": "A", "last_name": "B"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Application.objects.count(), 0)

    def test_stage_change_and_isolation(self):
        a = self.app()
        self.client.force_login(self.hr)
        self.client.post(reverse("recruitment:application_stage", args=[a.pk]), {"stage": "interview"})
        a.refresh_from_db()
        self.assertEqual(a.stage, "interview")
        self.client.post(reverse("recruitment:application_stage", args=[a.pk]), {"stage": "hired"})  # interdit ici
        a.refresh_from_db()
        self.assertEqual(a.stage, "interview")
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.get(reverse("recruitment:application_detail", args=[a.pk])).status_code, 404)

    def test_hire_creates_employee_once(self):
        a = self.app(email="k@x.bj", phone="97000000")
        self.client.force_login(self.hr)
        self.client.post(reverse("recruitment:application_hire", args=[a.pk]), {"hire_date": "2026-05-04", "gender": "F"})
        a.refresh_from_db()
        e = Employee.objects.get(company=self.c1)
        self.assertEqual((a.stage, a.employee, e.hire_date, e.gender, e.matricule), ("hired", e, datetime.date(2026, 5, 4), "F", "EMP0001"))
        self.client.post(reverse("recruitment:application_hire", args=[a.pk]), {})
        self.assertEqual(Employee.objects.count(), 1)

    def test_cv_upload_validation_and_private_download(self):
        import shutil, tempfile
        from django.conf import settings

        tmp = tempfile.mkdtemp()
        try:
            with self.settings(PRIVATE_ROOT=tmp):
                self.client.force_login(self.hr)
                bad = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
                r = self.client.post(reverse("recruitment:application_create"),
                                     {"job": self.job.pk, "first_name": "A", "last_name": "B", "cv": bad})
                self.assertContains(r, "Format non autorisé")
                good = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 test", content_type="application/pdf")
                self.client.post(reverse("recruitment:application_create"),
                                 {"job": self.job.pk, "first_name": "A", "last_name": "B", "cv": good})
                a = Application.objects.get()
                r = self.client.get(reverse("recruitment:application_cv", args=[a.pk]))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 test")
                self.client.force_login(self.hr_b)
                self.assertEqual(self.client.get(reverse("recruitment:application_cv", args=[a.pk])).status_code, 404)
                self.client.force_login(self.emp)
                self.assertEqual(self.client.get(reverse("recruitment:application_cv", args=[a.pk])).status_code, 403)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rating_bounds(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("recruitment:application_create"),
                             {"job": self.job.pk, "first_name": "A", "last_name": "B", "rating": 9})
        self.assertEqual(r.status_code, 200)
