import calendar
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from attendance.services import working_days
from employees.models import Contract, Employee
from leaves.models import LeaveRequest

from .calculator import PayrollInput, compute_payroll, money
from .models import PayrollSettings, Payslip, PayslipItem


def month_bounds(year, month):
    return datetime.date(year, month, 1), datetime.date(year, month, calendar.monthrange(year, month)[1])


def current_contract(employee, start, end):
    """Contrat applicable sur le mois : le plus récent couvrant au moins un jour du mois."""
    qs = Contract.objects.filter(employee=employee, start_date__lte=end).order_by("-start_date")
    for contract in qs:
        if contract.end_date is None or contract.end_date >= start:
            return contract
    return None


def unpaid_leave_days(company, employee, start, end):
    """Jours ouvrés de congés approuvés non rémunérés compris dans le mois."""
    leaves = LeaveRequest.objects.filter(
        employee=employee, status=LeaveRequest.Status.APPROVED, leave_type__is_paid=False,
        start_date__lte=end, end_date__gte=start,
    )
    days = set()
    for leave in leaves:
        lo, hi = max(leave.start_date, start), min(leave.end_date, end)
        days.update(working_days(company, lo, hi))
    return Decimal(len(days))


def _items_totals(payslip):
    totals = {"subject": Decimal(0), "exempt": Decimal(0), "deductions": Decimal(0)}
    for item in payslip.items.all():
        if item.kind == PayslipItem.Kind.DEDUCTION:
            totals["deductions"] += item.amount
        elif item.subject_to_contributions:
            totals["subject"] += item.amount
        else:
            totals["exempt"] += item.amount
    return totals


def compute_payslip(payslip, settings=None):
    """Recalcule et enregistre un bulletin (brouillon uniquement)."""
    period, employee, company = payslip.period, payslip.employee, payslip.company
    settings = settings or PayrollSettings.for_company(company)
    start, end = month_bounds(period.year, period.month)
    contract = current_contract(employee, start, end)
    base = contract.base_salary if contract else payslip.base_salary

    unpaid = unpaid_leave_days(company, employee, start, end)
    month_days = len(working_days(company, start, end)) or 1
    unpaid_deduction = money(Decimal(base) * unpaid / month_days) if unpaid else Decimal(0)

    totals = _items_totals(payslip)
    result = compute_payroll(
        PayrollInput(
            base_salary=base, unpaid_deduction=unpaid_deduction, subject_earnings=totals["subject"],
            exempt_earnings=totals["exempt"], deductions=totals["deductions"],
        ),
        settings,
    )
    payslip.base_salary, payslip.unpaid_days, payslip.unpaid_deduction = base, unpaid, unpaid_deduction
    payslip.extra_earnings = result.extra_earnings
    payslip.gross, payslip.contribution_base = result.gross, result.contribution_base
    payslip.cnss_employee, payslip.its_base, payslip.its = result.cnss_employee, result.its_base, result.its
    payslip.other_deductions, payslip.net = totals["deductions"], result.net
    payslip.cnss_employer, payslip.vps = result.cnss_employer, result.vps
    payslip.save()
    return payslip


@transaction.atomic
def generate_period(period):
    """Crée (ou recalcule) les bulletins des employés ayant un contrat sur le mois.

    Retourne (nombre de bulletins, liste des employés ignorés faute de contrat).
    """
    if not period.is_draft:
        raise ValueError("La période est validée.")
    start, end = month_bounds(period.year, period.month)
    settings = PayrollSettings.for_company(period.company)
    count, skipped = 0, []
    employees = Employee.objects.filter(company=period.company).exclude(status=Employee.Status.LEFT)
    for employee in employees.filter(hire_date__lte=end):
        if employee.exit_date and employee.exit_date < start:
            continue
        contract = current_contract(employee, start, end)
        if contract is None:
            skipped.append(employee)
            continue
        payslip, _ = Payslip.objects.get_or_create(
            company=period.company, period=period, employee=employee,
            defaults={"base_salary": contract.base_salary},
        )
        compute_payslip(payslip, settings)
        count += 1
    return count, skipped


def validate_period(period):
    period.status = period.Status.VALIDATED
    period.validated_at = timezone.now()
    period.save(update_fields=["status", "validated_at"])


def reopen_period(period):
    period.status = period.Status.DRAFT
    period.validated_at = None
    period.save(update_fields=["status", "validated_at"])


def period_totals(period):
    agg = period.payslips.aggregate(
        gross=Sum("gross"), cnss_employee=Sum("cnss_employee"), its=Sum("its"), net=Sum("net"),
        cnss_employer=Sum("cnss_employer"), vps=Sum("vps"),
    )
    totals = {k: (v or Decimal(0)) for k, v in agg.items()}
    totals["employer_cost"] = totals["gross"] + totals["cnss_employer"] + totals["vps"]
    totals["cnss_total"] = totals["cnss_employee"] + totals["cnss_employer"]
    return totals
