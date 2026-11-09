import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from companies.models import Company
from employees.models import Contract, Employee
from leaves.models import LeaveRequest, LeaveType

from . import services
from .calculator import PayrollInput, compute_its, compute_payroll
from .models import DEFAULT_BRACKETS, PayrollPeriod, PayrollSettings, Payslip, PayslipItem

D = Decimal


def std_settings(**kw):
    base = dict(cnss_employee_rate=D("3.6"), cnss_employer_rate=D("6.4"), cnss_family_rate=D("9"),
                cnss_accident_rate=D("1"), cnss_ceiling=None, vps_rate=D("4"), its_deducts_cnss=False,
                round_its=True, its_brackets=DEFAULT_BRACKETS)
    base.update(kw)
    return SimpleNamespace(**base)


class FormatTests(SimpleTestCase):
    def test_fcfa_uses_plain_space(self):
        from .pdf import fcfa
        self.assertEqual(fcfa(1234567), "1 234 567")
        self.assertTrue(fcfa(1234567).isascii())


class ITSTests(SimpleTestCase):
    def test_brackets(self):
        b = DEFAULT_BRACKETS
        self.assertEqual(compute_its(0, b), 0)
        self.assertEqual(compute_its(60000, b), 0)
        self.assertEqual(compute_its(100000, b), 4000)
        self.assertEqual(compute_its(150000, b), 9000)
        self.assertEqual(compute_its(300000, b), 33500)
        self.assertEqual(compute_its(600000, b), 9000 + 15000 + 47500 + 30000)

    def test_rounding(self):
        self.assertEqual(compute_its(100999, DEFAULT_BRACKETS), 4000)           # base arrondie à 100 000
        self.assertEqual(compute_its(100999, DEFAULT_BRACKETS, round_amounts=False), D("4100"))

    def test_negative(self):
        self.assertEqual(compute_its(-5, DEFAULT_BRACKETS), 0)


class CalculatorTests(SimpleTestCase):
    def test_reference_300000(self):
        r = compute_payroll(PayrollInput(base_salary=D(300000)), std_settings())
        self.assertEqual((r.gross, r.cnss_employee, r.its, r.net), (300000, 10800, 33500, 255700))
        self.assertEqual((r.cnss_employer, r.vps), (49200, 12000))

    def test_ceiling(self):
        r = compute_payroll(PayrollInput(base_salary=D(1000000)), std_settings(cnss_ceiling=D(500000)))
        self.assertEqual(r.cnss_employee, 18000)
        self.assertEqual(r.contribution_base, 500000)

    def test_its_after_cnss(self):
        r = compute_payroll(PayrollInput(base_salary=D(300000)), std_settings(its_deducts_cnss=True))
        self.assertEqual(r.its_base, 289200)

    def test_exempt_and_deductions(self):
        r = compute_payroll(
            PayrollInput(base_salary=D(200000), subject_earnings=D(50000), exempt_earnings=D(20000), deductions=D(15000)),
            std_settings())
        self.assertEqual(r.gross, 270000)
        self.assertEqual(r.cnss_employee, 9000)                  # 3,6 % de 250 000
        self.assertEqual(r.net, 270000 - 9000 - r.its - 15000)

    def test_unpaid_never_negative(self):
        r = compute_payroll(PayrollInput(base_salary=D(1000), unpaid_deduction=D(5000)), std_settings())
        self.assertEqual(r.gross, 0)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha", ifu="123", cnss_number="C-1")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.usr = User.objects.create_user("e@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.usr2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        mk = lambda c, f, l, **k: Employee.objects.create(company=c, first_name=f, last_name=l, gender="M",
                                                           hire_date=datetime.date(2025, 1, 1), **k)
        cls.e1 = mk(cls.c1, "Jean", "DOSSOU", user=cls.usr)
        cls.e2 = mk(cls.c1, "Awa", "ZINSOU", user=cls.usr2)
        cls.e3 = mk(cls.c1, "Sans", "CONTRAT")
        cls.eb = mk(cls.c2, "Paul", "KPADE")
        for e, sal in ((cls.e1, 300000), (cls.e2, 150000)):
            Contract.objects.create(company=cls.c1, employee=e, contract_type="cdi",
                                    start_date=datetime.date(2025, 1, 1), base_salary=sal)
        Contract.objects.create(company=cls.c2, employee=cls.eb, contract_type="cdi",
                                start_date=datetime.date(2025, 1, 1), base_salary=100000)
        cls.period = PayrollPeriod.objects.create(company=cls.c1, year=2026, month=3)


class ServiceTests(Base):
    def test_generate(self):
        count, skipped = services.generate_period(self.period)
        self.assertEqual(count, 2)
        self.assertEqual(skipped, [self.e3])
        p = Payslip.objects.get(employee=self.e1)
        self.assertEqual((p.gross, p.cnss_employee, p.its, p.net), (300000, 10800, 33500, 255700))

    def test_regenerate_idempotent(self):
        services.generate_period(self.period)
        services.generate_period(self.period)
        self.assertEqual(Payslip.objects.count(), 2)

    def test_items_affect_net(self):
        services.generate_period(self.period)
        p = Payslip.objects.get(employee=self.e2)
        net_before = p.net
        PayslipItem.objects.create(company=self.c1, payslip=p, label="Avance", kind="deduction", amount=10000)
        services.compute_payslip(p)
        self.assertEqual(p.net, net_before - 10000)

    def test_unpaid_leave_deduction(self):
        lt = LeaveType.objects.create(company=self.c1, name="Sans solde", is_paid=False)
        LeaveRequest.objects.create(company=self.c1, employee=self.e2, leave_type=lt,
                                    start_date=datetime.date(2026, 3, 2), end_date=datetime.date(2026, 3, 3),
                                    days=2, status="approved")
        services.generate_period(self.period)
        p = Payslip.objects.get(employee=self.e2)
        # mars 2026 : 22 jours ouvrés ; 2 jours non payés → 150 000 × 2 / 22
        self.assertEqual(p.unpaid_days, 2)
        self.assertEqual(p.unpaid_deduction, D("13636"))

    def test_pending_or_paid_leave_ignored(self):
        lt = LeaveType.objects.create(company=self.c1, name="Sans solde", is_paid=False)
        LeaveRequest.objects.create(company=self.c1, employee=self.e2, leave_type=lt,
                                    start_date=datetime.date(2026, 3, 2), end_date=datetime.date(2026, 3, 3),
                                    days=2, status="pending")
        services.generate_period(self.period)
        self.assertEqual(Payslip.objects.get(employee=self.e2).unpaid_deduction, 0)

    def test_validated_cannot_generate(self):
        services.validate_period(self.period)
        with self.assertRaises(ValueError):
            services.generate_period(self.period)

    def test_totals(self):
        services.generate_period(self.period)
        t = services.period_totals(self.period)
        self.assertEqual(t["gross"], 450000)
        self.assertEqual(t["employer_cost"], t["gross"] + t["cnss_employer"] + t["vps"])


class ViewTests(Base):
    def setUp(self):
        services.generate_period(self.period)
        self.p1 = Payslip.objects.get(employee=self.e1)
        self.p2 = Payslip.objects.get(employee=self.e2)

    def test_hr_pages(self):
        self.client.force_login(self.hr)
        for url in (reverse("payroll:period_list"), reverse("payroll:period_detail", args=[self.period.pk]),
                    reverse("payroll:payslip_detail", args=[self.p1.pk]), reverse("payroll:settings"),
                    reverse("payroll:period_create"), reverse("payroll:item_create", args=[self.p1.pk])):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_pdf(self):
        self.client.force_login(self.hr)
        r = self.client.get(reverse("payroll:payslip_pdf", args=[self.p1.pk]))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_employee_access_rules(self):
        self.client.force_login(self.usr)
        pdf = reverse("payroll:payslip_pdf", args=[self.p1.pk])
        self.assertEqual(self.client.get(pdf).status_code, 404)                    # brouillon : invisible
        services.validate_period(self.period)
        self.assertEqual(self.client.get(pdf).status_code, 200)                    # validé : visible
        self.assertEqual(self.client.get(reverse("payroll:payslip_pdf", args=[self.p2.pk])).status_code, 404)  # celui d'un collègue
        self.assertContains(self.client.get(reverse("payroll:mine")), "Mars 2026")
        self.assertEqual(self.client.get(reverse("payroll:period_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("payroll:payslip_detail", args=[self.p1.pk])).status_code, 403)

    def test_mine_hides_drafts_and_others(self):
        self.client.force_login(self.usr2)
        self.assertNotContains(self.client.get(reverse("payroll:mine")), "Mars 2026")

    def test_company_isolation(self):
        self.client.force_login(self.hr_b)
        for name, args in (("payroll:period_detail", [self.period.pk]), ("payroll:payslip_detail", [self.p1.pk]),
                           ("payroll:payslip_pdf", [self.p1.pk]), ("payroll:period_export", [self.period.pk, "csv"])):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404, name)
        self.assertEqual(self.client.post(reverse("payroll:period_generate", args=[self.period.pk])).status_code, 404)

    def test_add_and_delete_item(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("payroll:item_create", args=[self.p2.pk]),
                             {"kind": "earning", "label": "Prime", "amount": "20000", "subject_to_contributions": "on"})
        self.assertEqual(r.status_code, 302)
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.gross, 170000)
        item = self.p2.items.get()
        self.client.post(reverse("payroll:item_delete", args=[self.p2.pk, item.pk]))
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.gross, 150000)

    def test_items_locked_when_validated(self):
        services.validate_period(self.period)
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("payroll:item_create", args=[self.p1.pk])).status_code, 403)

    def test_invalid_amount(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("payroll:item_create", args=[self.p1.pk]), {"kind": "earning", "label": "x", "amount": "-5"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.p1.items.exists())

    def test_status_and_delete_rules(self):
        self.client.force_login(self.hr)
        self.client.post(reverse("payroll:period_status", args=[self.period.pk, "validate"]))
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, "validated")
        self.client.post(reverse("payroll:period_delete", args=[self.period.pk]))
        self.assertTrue(PayrollPeriod.objects.filter(pk=self.period.pk).exists())
        self.client.post(reverse("payroll:period_status", args=[self.period.pk, "reopen"]))
        self.client.post(reverse("payroll:period_delete", args=[self.period.pk]))
        self.assertFalse(PayrollPeriod.objects.filter(pk=self.period.pk).exists())

    def test_exports(self):
        self.client.force_login(self.hr)
        csv = self.client.get(reverse("payroll:period_export", args=[self.period.pk, "csv"]))
        self.assertIn("DOSSOU", csv.content.decode("utf-8-sig"))
        xlsx = self.client.get(reverse("payroll:period_export", args=[self.period.pk, "xlsx"]))
        self.assertTrue(xlsx.content.startswith(b"PK"))
        self.assertEqual(self.client.get(reverse("payroll:period_export", args=[self.period.pk, "cnss"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("payroll:period_export", args=[self.period.pk, "zip"])).status_code, 404)

    def test_period_form_duplicate(self):
        self.client.force_login(self.hr)
        r = self.client.post(reverse("payroll:period_create"), {"year": 2026, "month": 3})
        self.assertContains(r, "existe déjà")
        r = self.client.post(reverse("payroll:period_create"), {"year": 2026, "month": 4})
        self.assertEqual(r.status_code, 302)

    def test_settings_form(self):
        self.client.force_login(self.hr)
        data = {"cnss_employee_rate": "3.6", "cnss_employer_rate": "6.4", "cnss_family_rate": "9",
                "cnss_accident_rate": "2", "vps_rate": "4", "round_its": "on", "smig": "52000",
                "brackets": "60000;0\n150000;10\n;25"}
        r = self.client.post(reverse("payroll:settings"), data)
        self.assertEqual(r.status_code, 302)
        s = PayrollSettings.for_company(self.c1)
        self.assertEqual(s.its_brackets[-1], [None, 25.0])
        self.assertEqual(s.cnss_accident_rate, D("2"))
        for bad in ("60000;0\n50000;10\n;25", "60000;0\n150000;10", "abc", ";10\n60000;0"):
            data["brackets"] = bad
            self.assertEqual(self.client.post(reverse("payroll:settings"), data).status_code, 200, bad)
        # le paramétrage d'une entreprise n'affecte pas l'autre
        self.assertEqual(PayrollSettings.for_company(self.c2).cnss_accident_rate, D("1"))
