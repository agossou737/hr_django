"""Calcul de la paie (Bénin) — fonctions pures, testables sans base de données."""
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

ZERO = Decimal(0)


def money(value):
    """Arrondi au franc le plus proche (FCFA sans décimales)."""
    return Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def pct(amount, rate):
    return money(Decimal(amount) * Decimal(rate) / 100)


def compute_its(taxable, brackets, round_amounts=True):
    """ITS mensuel progressif par tranches. `brackets` = [[plafond|None, taux %], …] croissants."""
    taxable = Decimal(taxable)
    if round_amounts:
        taxable = (taxable / 1000).to_integral_value(rounding=ROUND_FLOOR) * 1000
    if taxable <= 0:
        return ZERO
    tax, lower = ZERO, ZERO
    for ceiling, rate in brackets:
        upper = Decimal(ceiling) if ceiling is not None else None
        if upper is None or taxable <= upper:
            tax += (taxable - lower) * Decimal(rate) / 100
            break
        tax += (upper - lower) * Decimal(rate) / 100
        lower = upper
    if round_amounts:
        return (tax / 10).to_integral_value(rounding=ROUND_HALF_UP) * 10
    return money(tax)


@dataclass
class PayrollInput:
    base_salary: Decimal
    unpaid_deduction: Decimal = ZERO
    subject_earnings: Decimal = ZERO       # primes soumises à CNSS/ITS
    exempt_earnings: Decimal = ZERO        # indemnités non soumises
    deductions: Decimal = ZERO             # avances et retenues diverses


@dataclass
class PayrollResult:
    gross: Decimal
    contribution_base: Decimal
    cnss_employee: Decimal
    its_base: Decimal
    its: Decimal
    net: Decimal
    cnss_employer: Decimal
    vps: Decimal
    extra_earnings: Decimal


def compute_payroll(data, settings):
    """Calcule un bulletin à partir des entrées et des paramètres (`PayrollSettings` ou équivalent)."""
    base = money(data.base_salary)
    subject = max(base - money(data.unpaid_deduction) + money(data.subject_earnings), ZERO)
    exempt = money(data.exempt_earnings)
    gross = subject + exempt

    cnss_base = subject
    if settings.cnss_ceiling:
        cnss_base = min(subject, Decimal(settings.cnss_ceiling))
    cnss_employee = pct(cnss_base, settings.cnss_employee_rate)
    employer_rate = Decimal(settings.cnss_employer_rate) + Decimal(settings.cnss_family_rate) + Decimal(
        settings.cnss_accident_rate
    )
    cnss_employer = pct(cnss_base, employer_rate)

    its_base = subject - (cnss_employee if settings.its_deducts_cnss else ZERO)
    its = money(compute_its(its_base, settings.its_brackets, settings.round_its))
    vps = pct(subject, settings.vps_rate)

    deductions = money(data.deductions)
    net = gross - cnss_employee - its - deductions
    return PayrollResult(
        gross=gross, contribution_base=cnss_base, cnss_employee=cnss_employee, its_base=its_base,
        its=its, net=net, cnss_employer=cnss_employer, vps=vps,
        extra_earnings=money(data.subject_earnings) + exempt,
    )
