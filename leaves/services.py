"""Règles métier des congés : décompte, soldes, droits d'approbation, chevauchements."""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from attendance.services import working_days

from .models import LeaveRequest, LeaveType, PermissionRequest

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


def delegated_employee_ids(user, day=None):
    """Managers absents (congé approuvé aujourd'hui) dont `user` est le remplaçant ayant accepté l'intérim."""
    day = day or timezone.localdate()
    if not user.is_authenticated or user.company_id is None:
        return set()
    return set(
        LeaveRequest.objects.filter(
            company_id=user.company_id, status=LeaveRequest.Status.APPROVED, start_date__lte=day, end_date__gte=day,
            replacement__user=user, replacement_status=LeaveRequest.ReplacementStatus.ACCEPTED,
        ).values_list("employee_id", flat=True)
    )


def is_reviewer(user):
    return user.is_authenticated and user.company_id is not None and (
        user.role in ("admin", "hr", "manager") or bool(delegated_employee_ids(user))
    )


def _supervisor_ids(user):
    ids = set(delegated_employee_ids(user))
    me = getattr(user, "employee", None)
    if me is not None and user.role == user.Role.MANAGER:
        ids.add(me.pk)
    return ids


def _is_supervised_by(target, ids):
    return target.manager_id in ids or (target.department_id is not None and target.department.head_id in ids)


def can_review(user, req):
    """HR/admin traitent tout ; un manager (ou son remplaçant délégué) l'équipe. Jamais sa propre demande.
    Un congé avec remplaçant non confirmé ne peut pas être approuvé (sauf par les RH)."""
    if not user.is_authenticated or user.company_id != req.company_id:
        return False
    target = req.employee
    if target.user_id == user.pk:
        return False
    if user.can_manage_hr:
        return True
    return _is_supervised_by(target, _supervisor_ids(user))


def replacement_blocks(req):
    return isinstance(req, LeaveRequest) and req.replacement_status == LeaveRequest.ReplacementStatus.PENDING


def _reviewable(user, model):
    qs = model.objects.filter(company=user.company, status="pending").exclude(employee__user=user).select_related("employee")
    if user.can_manage_hr:
        return qs
    ids = _supervisor_ids(user)
    if not ids:
        return qs.none()
    return qs.filter(Q(employee__manager__in=ids) | Q(employee__department__head__in=ids))


def reviewable_requests(user):
    """Demandes de congé en attente que l'utilisateur peut traiter."""
    return _reviewable(user, LeaveRequest).select_related("leave_type", "replacement")


def reviewable_permissions(user):
    return _reviewable(user, PermissionRequest)


def reviewers_of(req):
    """Utilisateurs à prévenir : RH + supérieur direct (ou responsable du département) + délégué éventuel."""
    from accounts.models import User

    target = req.employee
    users = set(User.objects.filter(company_id=req.company_id, is_active=True, role__in=["admin", "hr"]))
    heads = {target.manager_id, target.department.head_id if target.department_id else None} - {None}
    for emp in target.__class__.objects.filter(pk__in=heads).select_related("user"):
        if emp.user_id and emp.user.is_active:
            users.add(emp.user)
        for lr in LeaveRequest.objects.filter(
            employee=emp, status=LeaveRequest.Status.APPROVED, start_date__lte=timezone.localdate(),
            end_date__gte=timezone.localdate(), replacement_status=LeaveRequest.ReplacementStatus.ACCEPTED,
            replacement__user__isnull=False,
        ).select_related("replacement__user"):
            users.add(lr.replacement.user)
    users.discard(target.user)
    return list(users)


def review(req, user, approve, comment=""):
    from django.urls import reverse

    from notifications.services import notify

    req.status = "approved" if approve else "rejected"
    req.reviewed_by = user
    req.reviewed_at = timezone.now()
    req.review_comment = comment[:255]
    req.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment"])
    if req.employee.user_id:
        is_leave = isinstance(req, LeaveRequest)
        notify([req.employee.user], f"Votre demande de {'congé' if is_leave else 'permission'} a été "
               f"{'approuvée' if approve else 'refusée'}", comment,
               reverse("leaves:mine" if is_leave else "leaves:permission_mine"))
    if approve and isinstance(req, LeaveRequest) and req.replacement_status == LeaveRequest.ReplacementStatus.ACCEPTED \
            and req.replacement and req.replacement.user_id:
        notify([req.replacement.user], "Intérim confirmé",
               f"Vous assurez l'intérim de {req.employee.full_name} du {req.start_date:%d/%m/%Y} au {req.end_date:%d/%m/%Y}.",
               reverse("leaves:mine"))
    return req


def respond_replacement(req, accept, comment=""):
    from django.urls import reverse

    from notifications.services import notify

    req.replacement_status = (LeaveRequest.ReplacementStatus.ACCEPTED if accept
                              else LeaveRequest.ReplacementStatus.DECLINED)
    req.replacement_responded_at = timezone.now()
    req.replacement_comment = comment[:255]
    req.save(update_fields=["replacement_status", "replacement_responded_at", "replacement_comment"])
    targets = reviewers_of(req) if accept else []
    if req.employee.user_id:
        targets.append(req.employee.user)
    notify(targets, f"{req.replacement.full_name} a {'accepté' if accept else 'refusé'} l'intérim de "
           f"{req.employee.full_name}", comment, reverse("leaves:pending"))
    return req


def notify_new_request(req):
    from django.urls import reverse

    from notifications.services import notify

    is_leave = isinstance(req, LeaveRequest)
    if is_leave and req.replacement_id and req.replacement.user_id:
        notify([req.replacement.user], f"{req.employee.full_name} vous désigne comme remplaçant",
               f"Du {req.start_date:%d/%m/%Y} au {req.end_date:%d/%m/%Y}. Merci de confirmer.",
               reverse("leaves:replacements"))
    if not (is_leave and req.replacement_status == LeaveRequest.ReplacementStatus.PENDING):
        notify(reviewers_of(req), f"Nouvelle demande de {'congé' if is_leave else 'permission'} : {req.employee.full_name}",
               "", reverse("leaves:pending" if is_leave else "leaves:permission_pending"))
