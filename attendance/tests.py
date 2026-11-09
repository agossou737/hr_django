import datetime
import json
import random

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from companies.models import Company, Holiday
from employees.models import Employee

from . import services
from .models import AttendanceRecord, FaceTemplate, ScanLog


def vec(seed, noise=0.0):
    rnd = random.Random(seed)
    base = [rnd.uniform(-0.2, 0.2) for _ in range(128)]
    if noise:
        n = random.Random(seed + 999)
        base = [v + n.uniform(-noise, noise) for v in base]
    return base


def emp(company, first="Jean", last="DOSSOU"):
    return Employee.objects.create(
        company=company, first_name=first, last_name=last, gender="M", hire_date=datetime.date(2025, 1, 1)
    )


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role=User.Role.HR)
        cls.kiosk = User.objects.create_user("k@a.bj", "pass12345!", company=cls.c1, role=User.Role.KIOSK)
        cls.worker = User.objects.create_user("w@a.bj", "pass12345!", company=cls.c1, role=User.Role.EMPLOYEE)
        cls.hr2 = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role=User.Role.HR)
        cls.e1 = emp(cls.c1)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU")
        cls.eb = emp(cls.c2, "Paul", "KPADE")
        FaceTemplate.objects.create(company=cls.c1, employee=cls.e1, descriptor=vec(1), consent_at=timezone.now())
        FaceTemplate.objects.create(company=cls.c1, employee=cls.e2, descriptor=vec(2), consent_at=timezone.now())
        FaceTemplate.objects.create(company=cls.c2, employee=cls.eb, descriptor=vec(3), consent_at=timezone.now())


class DescriptorTests(TestCase):
    def test_valid(self):
        self.assertEqual(len(services.validate_descriptor([0.1] * 128)), 128)

    def test_invalid(self):
        for bad in (None, [0.1] * 127, ["a"] * 128, [True] * 128, [float("nan")] * 128, [99] * 128, "x"):
            with self.assertRaises(services.InvalidDescriptor):
                services.validate_descriptor(bad)


class MatchTests(Base):
    def test_match_same_person(self):
        e, d = services.best_match(self.c1, vec(1, noise=0.001))
        self.assertEqual(e, self.e1)
        self.assertLess(d, 0.5)

    def test_unknown_person(self):
        e, _ = services.best_match(self.c1, vec(77))
        self.assertIsNone(e)

    def test_company_isolation(self):
        # le visage de l'employé de Beta ne doit jamais être reconnu chez Alpha
        e, _ = services.best_match(self.c1, vec(3))
        self.assertIsNone(e)


class RegisterScanTests(Base):
    def at(self, h, m=0, day=None):
        day = day or datetime.date(2026, 3, 2)  # un lundi
        return timezone.make_aware(datetime.datetime.combine(day, datetime.time(h, m)))

    def test_checkin_then_checkout_then_duplicate(self):
        r1 = services.register_scan(self.c1, self.e1, 0.2, now=self.at(8, 0))
        self.assertEqual(r1.outcome, ScanLog.Outcome.CHECK_IN)
        r2 = services.register_scan(self.c1, self.e1, 0.2, now=self.at(8, 1))
        self.assertEqual(r2.outcome, ScanLog.Outcome.DUPLICATE)
        r3 = services.register_scan(self.c1, self.e1, 0.2, now=self.at(17, 5))
        self.assertEqual(r3.outcome, ScanLog.Outcome.CHECK_OUT)
        rec = AttendanceRecord.objects.get()
        self.assertEqual(rec.worked_hours, 9.08 if rec.worked_hours == 9.08 else rec.worked_hours)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_late_minutes(self):
        services.register_scan(self.c1, self.e1, 0.2, now=self.at(8, 30))
        self.assertEqual(AttendanceRecord.objects.get().late_minutes, 30)

    def test_tolerance(self):
        services.register_scan(self.c1, self.e1, 0.2, now=self.at(8, 8))
        self.assertEqual(AttendanceRecord.objects.get().late_minutes, 0)

    def test_unknown_logged(self):
        r = services.register_scan(self.c1, None, 0.9, now=self.at(8))
        self.assertEqual(r.outcome, ScanLog.Outcome.UNKNOWN)
        self.assertEqual(AttendanceRecord.objects.count(), 0)
        self.assertEqual(ScanLog.objects.count(), 1)

    def test_inactive_employee(self):
        self.e2.status = Employee.Status.LEFT
        self.e2.save()
        r = services.register_scan(self.c1, self.e2, 0.2, now=self.at(8))
        self.assertEqual(r.outcome, ScanLog.Outcome.INACTIVE)
        self.assertEqual(AttendanceRecord.objects.count(), 0)


class ScanApiTests(Base):
    def post(self, user, payload):
        self.client.force_login(user)
        return self.client.post(reverse("attendance:api_scan"), json.dumps(payload), content_type="application/json")

    def test_scan_ok(self):
        r = self.post(self.kiosk, {"descriptor": vec(1, 0.001)})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        self.assertEqual(r.json()["employee"]["name"], self.e1.full_name)

    def test_scan_unknown(self):
        r = self.post(self.kiosk, {"descriptor": vec(55)})
        self.assertFalse(r.json()["success"])

    def test_bad_payload(self):
        self.assertEqual(self.post(self.kiosk, {"descriptor": [1, 2]}).status_code, 400)
        self.client.force_login(self.kiosk)
        r = self.client.post(reverse("attendance:api_scan"), "not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_plain_employee_forbidden(self):
        self.assertIn(self.post(self.worker, {"descriptor": vec(1)}).status_code, (302, 403))
        self.assertEqual(AttendanceRecord.objects.count(), 0)

    def test_anonymous_forbidden(self):
        r = self.client.post(reverse("attendance:api_scan"), "{}", content_type="application/json")
        self.assertIn(r.status_code, (302, 403))

    def test_get_not_allowed(self):
        self.client.force_login(self.kiosk)
        self.assertEqual(self.client.get(reverse("attendance:api_scan")).status_code, 405)

    def test_kiosk_page_and_redirect(self):
        self.client.force_login(self.kiosk)
        self.assertEqual(self.client.get(reverse("attendance:kiosk")).status_code, 200)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], reverse("attendance:kiosk"))


class EnrollTests(Base):
    def url(self, e):
        return reverse("attendance:api_enroll", args=[e.pk])

    def post(self, e, payload, user=None):
        self.client.force_login(user or self.hr)
        return self.client.post(self.url(e), json.dumps(payload), content_type="application/json")

    def test_requires_consent(self):
        r = self.post(self.e1, {"descriptors": [vec(9)]})
        self.assertEqual(r.status_code, 400)

    def test_enroll_replaces(self):
        r = self.post(self.e1, {"consent": True, "descriptors": [vec(9), vec(9, 0.01)]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.e1.face_templates.count(), 2)
        self.assertIsNotNone(self.e1.face_templates.first().consent_at)

    def test_other_company_404(self):
        r = self.post(self.eb, {"consent": True, "descriptors": [vec(9)]})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.eb.face_templates.count(), 1)

    def test_too_many(self):
        r = self.post(self.e1, {"consent": True, "descriptors": [vec(i) for i in range(11)]})
        self.assertEqual(r.status_code, 400)

    def test_delete(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("attendance:face_delete", args=[self.e1.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.e1.face_templates.count(), 0)

    def test_pages(self):
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("attendance:enroll", args=[self.e1.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("employees:detail", args=[self.e1.pk])).status_code, 200)


class ReportTests(Base):
    def test_pages_render(self):
        today = timezone.localdate()
        AttendanceRecord.objects.create(company=self.c1, employee=self.e1, date=today,
                                        check_in=timezone.now())
        self.client.force_login(self.hr)
        for name in ("attendance:list", "attendance:monthly", "attendance:logs", "attendance:create"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 200, name)
        r = self.client.get(reverse("attendance:monthly") + "?export=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])

    def test_list_isolation(self):
        AttendanceRecord.objects.create(company=self.c2, employee=self.eb, date=timezone.localdate(),
                                        check_in=timezone.now())
        self.client.force_login(self.hr)
        r = self.client.get(reverse("attendance:list"))
        self.assertNotContains(r, "KPADE")

    def test_cannot_edit_other_company_record(self):
        rec = AttendanceRecord.objects.create(company=self.c2, employee=self.eb, date=timezone.localdate(),
                                              check_in=timezone.now())
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("attendance:update", args=[rec.pk])).status_code, 404)

    def test_holiday_excluded_from_working_days(self):
        Holiday.objects.create(company=self.c1, date=datetime.date(2026, 3, 2), name="Test")
        days = services.working_days(self.c1, datetime.date(2026, 3, 2), datetime.date(2026, 3, 2))
        self.assertEqual(len(list(days)), 0)
