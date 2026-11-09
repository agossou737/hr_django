from django.db.models import Q

from employees.models import Employee


def evaluable_employees(user):
    """Employés que l'utilisateur peut évaluer : toute l'entreprise (RH) ou son équipe (manager)."""
    qs = Employee.objects.filter(company=user.company).exclude(status=Employee.Status.LEFT)
    if user.can_manage_hr:
        return qs
    me = Employee.objects.filter(company=user.company, user=user).first()
    if user.role != user.Role.MANAGER or me is None:
        return qs.none()
    return qs.filter(Q(manager=me) | Q(department__head=me)).exclude(pk=me.pk)


def can_manage(user, evaluation):
    return evaluable_employees(user).filter(pk=evaluation.employee_id).exists()
