"""Règles métier des congés : décompte, soldes, droits d'approbation, chevauchements."""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from attendance.services import working_days

from .models import LeaveRequest, LeaveType

BLOCKING = (LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED)

# Valeurs proposées à la création d'une entreprise (modifiables). À confirmer auprès de
# l'Inspection du travail : la loi n° 98-004 fixe 2 jours ouvrables par mois de service.
DEFAULT_TYPES = [
    ("Congé annuel", 24, True),
    ("Congé maternité", 98, True),
    ("Congé de paternité", 3, True),
    ("Congé maladie", 0, True),
    ("Événement familial", 0, True),
    ("Congé sans solde", 0, False),
]


def create_default_types(company):
    created = 0
    for name, days, paid in DEFAULT_TYPES:
        _, was_created = LeaveType.objects.get_or_create(
            company=company, name=name, defaults={"annual_days": days, "is_paid": paid}
        )
        created += was_created
    return created


def count_leave_days(company, start, end):
    """Nombre de jours ouvrés (hors week-ends non travaillés et jours fériés) de la période."""
    return Decimal(len(working_days(company, start, end)))


def employee_ids_on_leave(company, day):
    """Employés ayant un congé approuvé couvrant ce jour (utilisé par le module Pointage)."""
    return set(
        LeaveRequest.objects.filter(
            company=company, status=LeaveRequest.Status.APPROVED, start_date__lte=day, end_date__gte=day
        ).values_list("employee_id", flat=True)
    )


def used_days(employee, leave_type, year, include_pending=True):
    statuses = BLOCKING if include_pending else (LeaveRequest.Status.APPROVED,)
    total = LeaveRequest.objects.filter(
        employee=employee, leave_type=leave_type, status__in=statuses,
        start_date__year=year,
    ).aggregate(t=Sum("days"))["t"]
    return total or Decimal(0)


def balance(employee, leave_type, year=None):
    """Jours restants de l'année pour un type plafonné ; None si le type n'est pas plafonné."""
    if not leave_type.is_capped:
        return None
    year = year or timezone.localdate().year
    return leave_type.annual_days - used_days(employee, leave_type, year)


def balances(employee, year=None):
    year = year or timezone.localdate().year
    rows = []
    for leave_type in LeaveType.objects.filter(company=employee.company):
        used = used_days(employee, leave_type, year)
        rows.append(
            {
                "type": leave_type,
                "allowed": leave_type.annual_days if leave_type.is_capped else None,
                "used": used,
                "remaining": (leave_type.annual_days - used) if leave_type.is_capped else None,
            }
        )
    return rows


def has_overlap(employee, start, end, exclude_pk=None):
    qs = LeaveRequest.objects.filter(
        employee=employee, status__in=BLOCKING, start_date__lte=end, end_date__gte=start
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def can_review(user, leave_request):
    """HR/admin traitent toutes les demandes ; un manager celles de son équipe. Jamais la sienne."""
    if not user.is_authenticated or user.company_id != leave_request.company_id:
        return False
    target = leave_request.employee
    if target.user_id == user.pk:
        return False
    if user.can_manage_hr:
        return True
    if user.role != user.Role.MANAGER:
        return False
    me = getattr(user, "employee", None)
    if me is None:
        return False
    return target.manager_id == me.pk or (
        target.department_id is not None and target.department.head_id == me.pk
    )


def reviewable_requests(user):
    """Demandes en attente que l'utilisateur peut traiter."""
    qs = LeaveRequest.objects.filter(
        company=user.company, status=LeaveRequest.Status.PENDING
    ).exclude(employee__user=user).select_related("employee", "leave_type")
    if user.can_manage_hr:
        return qs
    me = getattr(user, "employee", None)
    if user.role != user.Role.MANAGER or me is None:
        return qs.none()
    return qs.filter(Q(employee__manager=me) | Q(employee__department__head=me))


def review(leave_request, user, approve, comment=""):
    leave_request.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    leave_request.reviewed_by = user
    leave_request.reviewed_at = timezone.now()
    leave_request.review_comment = comment[:255]
    leave_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment"])
    return leave_request
