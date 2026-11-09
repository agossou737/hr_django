import datetime

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceRecord
from companies.models import Company
from employees.models import Employee
from leaves import services as lsv
from leaves.models import LeaveRequest, LeaveType, PermissionRequest
from notifications.models import Notification

from . import services
from .models import Explanation

D = datetime.date(2026, 3, 2)  # lundi


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class Base(TestCase):
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
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", user=cls.u1, manager=cls.e_mgr)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU", user=cls.u2, manager=cls.e_mgr)

    def late_record(self, employee=None, hour=9, minute=0, day=D):
        tz = timezone.get_current_timezone()
        ci = timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, minute)), tz)
        return AttendanceRecord.objects.create(company=self.c1, employee=employee or self.e1, date=day, check_in=ci)


class ExplanationFlowTests(Base):
    def test_lateness_creates_one_explanation_and_notifies(self):
        rec = self.late_record()
        self.assertGreater(rec.late_minutes, 0)
        exp = Explanation.objects.get()
        self.assertTrue(exp.automatic)
        self.assertEqual(exp.employee, self.e1)
        self.assertEqual(Notification.objects.filter(user=self.u1).count(), 1)
        rec.check_out = rec.check_in + datetime.timedelta(hours=8)
        rec.save()  # un second enregistrement ne doit pas dupliquer
        self.assertEqual(Explanation.objects.count(), 1)

    def test_on_time_or_disabled_creates_nothing(self):
        self.late_record(hour=7, minute=55)
        self.assertEqual(Explanation.objects.count(), 0)
        self.c1.auto_explanation = False
        self.c1.save()
        c = Company.objects.get(pk=self.c1.pk)
        tz = timezone.get_current_timezone()
        AttendanceRecord.objects.create(company=c, employee=self.e2, date=D, check_in=timezone.make_aware(
            datetime.datetime.combine(D, datetime.time(10, 0)), tz))
        self.assertEqual(Explanation.objects.count(), 0)

    def test_full_circuit_employee_answers_hr_decides(self):
        self.late_record()
        exp = Explanation.objects.get()
        self.client.force_login(self.u1)
        r = self.client.get(reverse("explanations:pdf", args=[exp.pk, "demande"]))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertEqual(self.client.get(reverse("explanations:pdf", args=[exp.pk, "reponse"])).status_code, 403)
        self.client.post(reverse("explanations:answer", args=[exp.pk]), {"answer": "Embouteillage sur le pont."})
        exp.refresh_from_db()
        self.assertEqual(exp.status, "answered")
        self.assertTrue(Notification.objects.filter(user=self.hr, title__startswith="Réponse de").exists())
        self.assertTrue(self.client.get(reverse("explanations:pdf", args=[exp.pk, "reponse"])).content.startswith(b"%PDF"))
        # l'employé ne peut pas décider
        self.assertEqual(self.client.post(reverse("explanations:decide", args=[exp.pk, "accept"])).status_code, 403)
        self.client.force_login(self.hr)
        self.client.post(reverse("explanations:decide", args=[exp.pk, "accept"]), {"comment": "OK"})
        exp.refresh_from_db()
        self.assertEqual(exp.status, "justified")
        self.assertTrue(Notification.objects.filter(user=self.u1, title__contains="acceptée").exists())
        self.assertTrue(self.client.get(reverse("explanations:pdf", args=[exp.pk, "reponse"])).content.startswith(b"%PDF"))

    def test_access_isolation(self):
        self.late_record()
        exp = Explanation.objects.get()
        for user, code in ((self.u2, 403), (self.mgr, 403), (self.hr_b, 404)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("explanations:detail", args=[exp.pk])).status_code, code)
            self.assertEqual(self.client.get(reverse("explanations:pdf", args=[exp.pk, "demande"])).status_code, code)
        self.client.force_login(self.u2)
        self.client.post(reverse("explanations:answer", args=[exp.pk]), {"answer": "Je réponds à la place"})
        exp.refresh_from_db()
        self.assertEqual(exp.status, "pending")
        self.assertEqual(self.client.get(reverse("explanations:list")).status_code, 403)

    def test_reminders_after_deadline_max_three(self):
        self.late_record()
        exp = Explanation.objects.get()
        self.assertEqual(services.send_reminders(today=exp.deadline), 0)  # pas encore en retard
        day = exp.deadline
        sent = 0
        for i in range(1, 6):
            sent += services.send_reminders(today=day + datetime.timedelta(days=i))
        self.assertEqual(sent, 3)
        exp.refresh_from_db()
        self.assertEqual(exp.reminders_sent, 3)
        self.assertTrue(Notification.objects.filter(user=self.hr, title__startswith="Sans réponse").exists())

    def test_manual_request_and_email(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("explanations:create"), {
            "employee": self.e2.pk, "kind": "absence", "date": "2026-03-03", "subject": "Absence non justifiée",
            "message": "Merci de justifier."})
        self.assertEqual(r.status_code, 302)
        exp = Explanation.objects.get()
        self.assertFalse(exp.automatic)
        self.assertEqual(exp.requested_by, self.hr)
        self.assertEqual(len(mail.outbox), 1)  # e-mail envoyé à l'employé
        self.assertEqual(mail.outbox[0].to, ["e2@a.bj"])

    def test_export_list(self):
        self.late_record()
        self.client.force_login(self.hr)
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("explanations:list") + f"?export={fmt}").status_code, 200)


class NotificationTests(Base):
    def test_open_marks_read_and_isolation(self):
        from notifications.services import notify

        n = notify([self.u1], "Salut", "msg", "/conges/", email=False)[0]
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(reverse("notifications:open", args=[n.pk])).status_code, 404)
        self.client.force_login(self.u1)
        r = self.client.get(reverse("notifications:open", args=[n.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/conges/")
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_bell_shows_unread_count(self):
        from notifications.services import notify

        notify([self.u1], "A", email=False)
        notify([self.u1], "B", email=False)
        self.client.force_login(self.u1)
        r = self.client.get(reverse("notifications:list"))
        self.assertEqual(r.context["unread_notifications"], 2)
        self.client.post(reverse("notifications:read_all"))
        self.assertEqual(self.client.get(reverse("notifications:list")).context["unread_notifications"], 0)

    def test_unsafe_redirect_ignored(self):
        from notifications.services import notify

        n = notify([self.u1], "X", "", "https://evil.example/", email=False)[0]
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("notifications:open", args=[n.pk]))["Location"], reverse("notifications:list"))


class InterimTests(Base):
    def setUp(self):
        self.lt = LeaveType.objects.create(company=self.c1, name="Annuel", annual_days=30)

    def request_leave(self, replacement=None, employee=None):
        self.client.force_login((employee or self.e_mgr).user)
        return self.client.post(reverse("leaves:create"), {
            "leave_type": self.lt.pk, "start_date": "2026-03-02", "end_date": "2026-03-06", "reason": "Repos",
            "replacement": replacement.pk if replacement else ""})

    def test_replacement_must_accept_before_manager_approval(self):
        self.request_leave(self.e1, self.e_mgr)
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.replacement_status, "pending")
        self.assertTrue(Notification.objects.filter(user=self.u1, title__contains="remplaçant").exists())
        # le circuit n'est pas bloqué pour les RH, mais un manager ne peut pas approuver avant l'acceptation
        self.assertTrue(lsv.replacement_blocks(leave))
        self.client.force_login(self.u2)
        self.assertEqual(self.client.post(reverse("leaves:replacement_respond", args=[leave.pk, "accept"])).status_code, 404)
        self.client.force_login(self.u1)
        self.client.post(reverse("leaves:replacement_respond", args=[leave.pk, "accept"]), {"comment": "Ok"})
        leave.refresh_from_db()
        self.assertEqual(leave.replacement_status, "accepted")

    def test_decline_notifies_employee(self):
        self.request_leave(self.e1, self.e_mgr)
        leave = LeaveRequest.objects.get()
        self.client.force_login(self.u1)
        self.client.post(reverse("leaves:replacement_respond", args=[leave.pk, "decline"]))
        leave.refresh_from_db()
        self.assertEqual(leave.replacement_status, "declined")
        self.assertTrue(Notification.objects.filter(user=self.mgr, title__contains="refusé").exists())

    def test_manager_approval_blocked_while_replacement_pending(self):
        boss = User.objects.create_user("boss@a.bj", "pass12345!", company=self.c1, role="manager")
        e_boss = emp(self.c1, "Big", "BOSS", user=boss)
        self.e_mgr.manager = e_boss
        self.e_mgr.save()
        self.request_leave(self.e1, self.e_mgr)
        leave = LeaveRequest.objects.get()
        self.client.force_login(boss)
        self.client.post(reverse("leaves:review", args=[leave.pk, "approve"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")
        self.client.force_login(self.u1)
        self.client.post(reverse("leaves:replacement_respond", args=[leave.pk, "accept"]))
        self.client.force_login(boss)
        self.client.post(reverse("leaves:review", args=[leave.pk, "approve"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")

    def test_delegation_to_replacement_during_leave(self):
        """Le remplaçant accepté traite les demandes de l'équipe du manager pendant son congé."""
        self.request_leave(self.e1, self.e_mgr)
        leave = LeaveRequest.objects.get()
        self.client.force_login(self.u1)
        self.client.post(reverse("leaves:replacement_respond", args=[leave.pk, "accept"]))
        self.client.force_login(self.hr)
        self.client.post(reverse("leaves:review", args=[leave.pk, "approve"]))
        # demande de l'autre employé, dans l'équipe du manager absent
        other = LeaveRequest.objects.create(company=self.c1, employee=self.e2, leave_type=self.lt,
                                            start_date=datetime.date(2026, 4, 6), end_date=datetime.date(2026, 4, 6), days=1)
        day = datetime.date(2026, 3, 3)
        self.assertEqual(lsv.delegated_employee_ids(self.u1, day), {self.e_mgr.pk})
        self.assertEqual(lsv.delegated_employee_ids(self.u1, datetime.date(2026, 3, 20)), set())
        # simule « aujourd'hui » pendant le congé
        from unittest import mock

        with mock.patch("leaves.services.timezone.localdate", return_value=day):
            self.assertTrue(lsv.is_reviewer(self.u1))
            self.assertTrue(lsv.can_review(self.u1, other))
            self.assertIn(other, lsv.reviewable_requests(self.u1))
            self.client.force_login(self.u1)
            self.assertEqual(self.client.get(reverse("leaves:pending")).status_code, 200)
        # hors période : plus de droits
        self.assertFalse(lsv.is_reviewer(self.u1))
        self.assertEqual(self.client.get(reverse("leaves:pending")).status_code, 403)

    def test_replacement_validation_and_pdf(self):
        self.request_leave(None, self.e1)
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.replacement_status, "none")
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("leaves:pdf", args=[leave.pk])).status_code, 403)  # pas encore approuvé
        self.client.force_login(self.mgr)
        self.client.post(reverse("leaves:review", args=[leave.pk, "approve"]))
        self.client.force_login(self.u1)
        r = self.client.get(reverse("leaves:pdf", args=[leave.pk]))
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(reverse("leaves:pdf", args=[leave.pk])).status_code, 403)

    def test_cannot_pick_replacement_on_leave_or_self(self):
        LeaveRequest.objects.create(company=self.c1, employee=self.e1, leave_type=self.lt, status="approved",
                                    start_date=D, end_date=D, days=1)
        self.request_leave(self.e1, self.e_mgr)
        self.assertEqual(LeaveRequest.objects.filter(employee=self.e_mgr).count(), 0)
        self.request_leave(self.e_mgr, self.e_mgr)
        self.assertEqual(LeaveRequest.objects.filter(employee=self.e_mgr).count(), 0)


class PermissionTests(Base):
    def post_perm(self, user, **kw):
        self.client.force_login(user)
        data = {"date": "2026-03-04", "start_time": "10:00", "end_time": "12:00", "reason": "Rendez-vous médical"}
        data.update(kw)
        return self.client.post(reverse("leaves:permission_create"), data)

    def test_request_review_pdf(self):
        self.assertEqual(self.post_perm(self.u1).status_code, 302)
        p = PermissionRequest.objects.get()
        self.assertEqual(p.hours, 2)
        self.assertTrue(Notification.objects.filter(user=self.mgr, title__contains="permission").exists())
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("leaves:permission_pending")).status_code, 200)
        self.client.post(reverse("leaves:permission_review", args=[p.pk, "approve"]), {"comment": "OK"})
        p.refresh_from_db()
        self.assertEqual(p.status, "approved")
        self.client.force_login(self.u1)
        self.assertTrue(self.client.get(reverse("leaves:permission_pdf", args=[p.pk])).content.startswith(b"%PDF"))
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(reverse("leaves:permission_pdf", args=[p.pk])).status_code, 403)

    def test_validation_and_permissions(self):
        self.assertEqual(self.post_perm(self.u1, end_time="09:00").status_code, 200)
        self.post_perm(self.u1)
        self.assertEqual(self.post_perm(self.u1, start_time="11:00", end_time="13:00").status_code, 200)  # chevauche
        self.assertEqual(PermissionRequest.objects.count(), 1)
        p = PermissionRequest.objects.get()
        self.client.force_login(self.u2)  # un collègue ne traite rien
        self.assertEqual(self.client.post(reverse("leaves:permission_review", args=[p.pk, "approve"])).status_code, 403)
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.post(reverse("leaves:permission_review", args=[p.pk, "approve"])).status_code, 404)
        self.client.force_login(self.u1)  # pas d'auto-approbation
        self.assertEqual(self.client.post(reverse("leaves:permission_review", args=[p.pk, "approve"])).status_code, 403)

    def test_hr_list_and_export(self):
        self.post_perm(self.u1)
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("leaves:permission_list")).status_code, 200)
        for fmt in ("csv", "xlsx", "pdf"):
            self.assertEqual(self.client.get(reverse("leaves:permission_list") + f"?export={fmt}").status_code, 200)
