import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from companies.benin import benin_holidays, easter
from companies.models import Company, Holiday
from employees.models import Department, Employee

from . import services
from .models import LeaveRequest, LeaveType

MON = datetime.date(2026, 3, 2)  # lundi


def emp(company, first, last, **kw):
    return Employee.objects.create(
        company=company, first_name=first, last_name=last, gender="M", hire_date=datetime.date(2024, 1, 1), **kw
    )


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.mgr = User.objects.create_user("m@a.bj", "pass12345!", company=cls.c1, role="manager")
        cls.mgr2 = User.objects.create_user("m2@a.bj", "pass12345!", company=cls.c1, role="manager")
        cls.usr = User.objects.create_user("e@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.usr2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        cls.e_mgr = emp(cls.c1, "Marc", "CHEF", user=cls.mgr)
        cls.e_mgr2 = emp(cls.c1, "Autre", "CHEF", user=cls.mgr2)
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", user=cls.usr, manager=cls.e_mgr)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU", user=cls.usr2, manager=cls.e_mgr2)
        cls.eb = emp(cls.c2, "Paul", "KPADE")
        cls.annual = LeaveType.objects.create(company=cls.c1, name="Congé annuel", annual_days=10)
        cls.sick = LeaveType.objects.create(company=cls.c1, name="Maladie")
        cls.annual_b = LeaveType.objects.create(company=cls.c2, name="Congé annuel", annual_days=10)

    def make(self, employee=None, start=MON, end=None, ltype=None, status="pending"):
        end = end or start
        return LeaveRequest.objects.create(
            company=self.c1, employee=employee or self.e1, leave_type=ltype or self.annual,
            start_date=start, end_date=end,
            days=services.count_leave_days(self.c1, start, end), status=status,
        )


class ServiceTests(Base):
    def test_working_days_skip_weekend_and_holiday(self):
        Holiday.objects.create(company=self.c1, date=datetime.date(2026, 3, 4), name="Férié")
        # lun 2 → lun 9 : 6 jours ouvrés hors week-end (2,3,4,5,6,9) moins le férié du 4
        self.assertEqual(services.count_leave_days(self.c1, MON, datetime.date(2026, 3, 9)), Decimal(5))

    def test_balance_and_overlap(self):
        self.make(start=MON, end=datetime.date(2026, 3, 4), status="approved")  # 3 jours
        self.assertEqual(services.balance(self.e1, self.annual, 2026), Decimal(7))
        self.assertIsNone(services.balance(self.e1, self.sick, 2026))
        self.assertTrue(services.has_overlap(self.e1, datetime.date(2026, 3, 4), datetime.date(2026, 3, 6)))
        self.assertFalse(services.has_overlap(self.e1, datetime.date(2026, 3, 5), datetime.date(2026, 3, 6)))

    def test_cancelled_and_rejected_not_counted(self):
        self.make(status="rejected")
        self.make(start=datetime.date(2026, 3, 3), status="cancelled")
        self.assertEqual(services.balance(self.e1, self.annual, 2026), Decimal(10))

    def test_on_leave_hook(self):
        self.make(status="approved")
        self.make(employee=self.e2, status="pending")
        self.assertEqual(services.employee_ids_on_leave(self.c1, MON), {self.e1.pk})
        self.assertEqual(services.employee_ids_on_leave(self.c2, MON), set())


class PermissionTests(Base):
    def test_can_review(self):
        r = self.make()
        self.assertTrue(services.can_review(self.hr, r))
        self.assertTrue(services.can_review(self.mgr, r))      # son manager
        self.assertFalse(services.can_review(self.mgr2, r))    # autre équipe
        self.assertFalse(services.can_review(self.usr, r))     # simple employé
        self.assertFalse(services.can_review(self.hr_b, r))    # autre entreprise

    def test_cannot_review_own(self):
        r = self.make(employee=self.e_mgr)
        self.assertFalse(services.can_review(self.mgr, r))

    def test_department_head_can_review(self):
        dept = Department.objects.create(company=self.c1, name="IT", head=self.e_mgr2)
        self.e1.department = dept
        self.e1.save()
        self.assertTrue(services.can_review(self.mgr2, self.make()))

    def test_reviewable_scope(self):
        self.make()
        self.make(employee=self.e2, start=datetime.date(2026, 3, 3))
        self.assertEqual(services.reviewable_requests(self.mgr).count(), 1)
        self.assertEqual(services.reviewable_requests(self.hr).count(), 2)
        self.assertEqual(services.reviewable_requests(self.usr).count(), 0)


class WorkflowViewTests(Base):
    def post_request(self, user, **extra):
        self.client.force_login(user)
        data = {"leave_type": self.annual.pk, "start_date": "2026-03-02", "end_date": "2026-03-04", "reason": "x"}
        data.update(extra)
        return self.client.post(reverse("leaves:create"), data)

    def test_employee_creates_request(self):
        r = self.post_request(self.usr)
        self.assertEqual(r.status_code, 302)
        req = LeaveRequest.objects.get()
        self.assertEqual((req.employee, req.status, req.days), (self.e1, "pending", Decimal(3)))

    def test_balance_exceeded(self):
        r = self.post_request(self.usr, end_date="2026-03-20")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Solde insuffisant")
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_end_before_start_and_overlap(self):
        r = self.post_request(self.usr, start_date="2026-03-05", end_date="2026-03-02")
        self.assertContains(r, "précède")
        self.post_request(self.usr)
        r = self.post_request(self.usr, start_date="2026-03-03", end_date="2026-03-03")
        self.assertContains(r, "existe déjà")

    def test_weekend_only_rejected(self):
        r = self.post_request(self.usr, start_date="2026-03-07", end_date="2026-03-08")
        self.assertContains(r, "aucun jour ouvré")

    def test_other_company_leave_type_rejected(self):
        r = self.post_request(self.usr, leave_type=self.annual_b.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_approve_by_manager(self):
        req = self.make()
        self.client.force_login(self.mgr)
        self.client.post(reverse("leaves:review", args=[req.pk, "approve"]), {"comment": "OK"})
        req.refresh_from_db()
        self.assertEqual((req.status, req.reviewed_by, req.review_comment), ("approved", self.mgr, "OK"))

    def test_reject(self):
        req = self.make()
        self.client.force_login(self.hr)
        self.client.post(reverse("leaves:review", args=[req.pk, "reject"]))
        req.refresh_from_db()
        self.assertEqual(req.status, "rejected")

    def test_forbidden_reviewers(self):
        req = self.make()
        for user in (self.usr, self.mgr2, self.hr_b):
            self.client.force_login(user)
            r = self.client.post(reverse("leaves:review", args=[req.pk, "approve"]))
            self.assertIn(r.status_code, (403, 404))
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")

    def test_cannot_approve_twice(self):
        req = self.make(status="approved")
        self.client.force_login(self.hr)
        self.client.post(reverse("leaves:review", args=[req.pk, "reject"]))
        req.refresh_from_db()
        self.assertEqual(req.status, "approved")

    def test_cancel_only_own(self):
        req = self.make()
        self.client.force_login(self.usr2)
        self.assertEqual(self.client.post(reverse("leaves:cancel", args=[req.pk])).status_code, 404)
        self.client.force_login(self.usr)
        self.client.post(reverse("leaves:cancel", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, "cancelled")

    def test_hr_entry_auto_approved(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("leaves:hr_create"), {
            "employee_field": self.e2.pk, "leave_type": self.sick.pk,
            "start_date": "2026-03-02", "end_date": "2026-03-03", "reason": ""})
        self.assertEqual(r.status_code, 302)
        req = LeaveRequest.objects.get()
        self.assertEqual((req.employee, req.status), (self.e2, "approved"))

    def test_hr_cannot_pick_other_company_employee(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("leaves:hr_create"), {
            "employee_field": self.eb.pk, "leave_type": self.sick.pk,
            "start_date": "2026-03-02", "end_date": "2026-03-03"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_pages_by_role(self):
        self.make()
        expectations = {
            self.usr: {"leaves:mine": 200, "leaves:calendar": 200, "leaves:pending": 403, "leaves:list": 403, "leaves:type_list": 403},
            self.mgr: {"leaves:mine": 200, "leaves:pending": 200, "leaves:list": 403},
            self.hr: {"leaves:mine": 200, "leaves:pending": 200, "leaves:list": 200, "leaves:type_list": 200, "leaves:calendar": 200},
        }
        for user, pages in expectations.items():
            self.client.force_login(user)
            for name, code in pages.items():
                self.assertEqual(self.client.get(reverse(name)).status_code, code, f"{user.role} {name}")

    def test_calendar_employee_sees_only_own(self):
        self.make(status="approved")
        self.make(employee=self.e2, start=MON, status="approved")
        self.client.force_login(self.usr)
        r = self.client.get(reverse("leaves:calendar") + "?year=2026&month=3")
        self.assertContains(r, "Jean D.")
        self.assertNotContains(r, "Awa Z.")
        self.client.force_login(self.hr)
        r = self.client.get(reverse("leaves:calendar") + "?year=2026&month=3")
        self.assertContains(r, "Awa Z.")

    def test_default_types_and_company_isolation(self):
        self.client.force_login(self.hr_b)
        self.client.post(reverse("leaves:type_defaults"))
        self.assertGreater(LeaveType.objects.filter(company=self.c2).count(), 1)
        self.assertEqual(LeaveType.objects.filter(company=self.c1).count(), 2)
        t = LeaveType.objects.filter(company=self.c1).first()
        self.assertEqual(self.client.post(reverse("leaves:type_delete", args=[t.pk])).status_code, 404)

    def test_type_in_use_not_deletable(self):
        self.make()
        self.client.force_login(self.hr)
        self.client.post(reverse("leaves:type_delete", args=[self.annual.pk]))
        self.assertTrue(LeaveType.objects.filter(pk=self.annual.pk).exists())

    def test_attendance_uses_leave(self):
        from attendance.services import employees_on_leave
        self.make(status="approved")
        self.assertIn(self.e1.pk, employees_on_leave(self.c1, MON))


class BeninHolidayTests(TestCase):
    def test_easter(self):
        self.assertEqual(easter(2026), datetime.date(2026, 4, 5))
        self.assertEqual(easter(2025), datetime.date(2025, 4, 20))

    def test_list(self):
        days = dict((d, n) for d, n in benin_holidays(2026))
        self.assertEqual(len(days), 9)
        self.assertEqual(days[datetime.date(2026, 4, 6)], "Lundi de Pâques")
        self.assertEqual(days[datetime.date(2026, 5, 14)], "Ascension")
        self.assertEqual(days[datetime.date(2026, 5, 25)], "Lundi de Pentecôte")
        self.assertEqual(days[datetime.date(2026, 8, 1)], "Fête de l'Indépendance")


class SettingsAndUsersTests(Base):
    def test_generate_holidays_idempotent(self):
        self.client.force_login(self.hr)
        for _ in range(2):
            self.client.post(reverse("companies:holiday_generate"), {"year": "2026"})
        self.assertEqual(Holiday.objects.filter(company=self.c1).count(), 9)
        self.assertEqual(Holiday.objects.filter(company=self.c2).count(), 0)
        self.client.post(reverse("companies:holiday_generate"), {"year": "abc"})

    def test_company_settings_update(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("companies:settings"), {
            "name": "Alpha SARL", "city": "Cotonou", "work_start_time": "07:30", "work_end_time": "16:30",
            "late_tolerance_minutes": 5, "days": ["0", "1", "2", "3", "4", "5"]})
        self.assertEqual(r.status_code, 302)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.work_weekdays, {0, 1, 2, 3, 4, 5})
        self.assertEqual(self.c1.late_tolerance_minutes, 5)

    def test_settings_forbidden_for_employee(self):
        self.client.force_login(self.usr)
        self.assertEqual(self.client.get(reverse("companies:settings")).status_code, 403)

    def test_create_user_and_link(self):
        free = emp(self.c1, "Libre", "NOM")
        self.client.force_login(self.hr)
        r = self.client.post(reverse("accounts:user_create"), {
            "email": "NEW@a.bj", "first_name": "N", "last_name": "W", "role": "employee",
            "employee": free.pk, "password1": "Sup3r-secret!", "password2": "Sup3r-secret!"})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(email="new@a.bj")
        self.assertEqual(u.company, self.c1)
        free.refresh_from_db()
        self.assertEqual(free.user, u)

    def test_hr_cannot_create_admin(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("accounts:user_create"), {
            "email": "x@a.bj", "role": "admin", "password1": "Sup3r-secret!", "password2": "Sup3r-secret!"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="x@a.bj").exists())

    def test_user_isolation_and_admin_protection(self):
        admin = User.objects.create_user("adm@a.bj", "pass12345!", company=self.c1, role="admin")
        other = User.objects.create_user("o@b.bj", "pass12345!", company=self.c2, role="employee")
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("accounts:user_update", args=[other.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("accounts:user_update", args=[admin.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:user_password", args=[admin.pk])).status_code, 403)
        r = self.client.get(reverse("accounts:user_list"))
        self.assertNotContains(r, "o@b.bj")

    def test_password_reset_and_self_lockout(self):
        self.client.force_login(self.hr)
        self.client.post(reverse("accounts:user_password", args=[self.usr.pk]),
                         {"password1": "N0uveau-mdp!", "password2": "N0uveau-mdp!"})
        self.usr.refresh_from_db()
        self.assertTrue(self.usr.check_password("N0uveau-mdp!"))
        self.client.post(reverse("accounts:user_update", args=[self.hr.pk]),
                         {"first_name": "a", "last_name": "b", "role": "employee", "is_active": ""})
        self.hr.refresh_from_db()
        self.assertEqual(self.hr.role, "hr")
        self.assertTrue(self.hr.is_active)

    def test_dashboards(self):
        for user in (self.hr, self.mgr, self.usr):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.client.force_login(self.usr)
        self.assertTemplateUsed(self.client.get(reverse("dashboard")), "dashboard_self.html")
