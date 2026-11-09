"""Logique métier du pointage facial (indépendante des vues)."""
import datetime
import math
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from employees.models import Employee

from .models import AttendanceRecord, FaceTemplate, ScanLog

DESCRIPTOR_SIZE = 128


class InvalidDescriptor(ValueError):
    pass


def validate_descriptor(value):
    """Vérifie qu'une empreinte est bien une liste de 128 nombres finis et raisonnables."""
    if not isinstance(value, (list, tuple)) or len(value) != DESCRIPTOR_SIZE:
        raise InvalidDescriptor("L'empreinte doit contenir exactement 128 valeurs.")
    cleaned = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise InvalidDescriptor("L'empreinte contient une valeur non numérique.")
        number = float(item)
        if not math.isfinite(number) or abs(number) > 10:
            raise InvalidDescriptor("L'empreinte contient une valeur hors limites.")
        cleaned.append(round(number, 6))
    return cleaned


def confidence_from_distance(distance):
    """Convertit une distance euclidienne en pourcentage de confiance indicatif."""
    return max(0.0, min(100.0, round((1 - distance) * 100, 1)))


def best_match(company, descriptor):
    """Retourne (employé, distance) du meilleur candidat de l'entreprise.

    L'employé vaut None si aucune empreinte ne passe sous le seuil de reconnaissance.
    """
    templates = FaceTemplate.objects.filter(company=company).select_related("employee")
    best_employee, best_distance = None, None
    for template in templates:
        try:
            distance = math.dist(descriptor, template.descriptor)
        except (TypeError, ValueError):
            continue
        if best_distance is None or distance < best_distance:
            best_employee, best_distance = template.employee, distance
    if best_distance is None or best_distance > settings.FACE_MATCH_THRESHOLD:
        return None, best_distance
    return best_employee, best_distance


@dataclass
class ScanResult:
    outcome: str
    employee: Employee | None = None
    record: AttendanceRecord | None = None
    distance: float | None = None
    message: str = ""

    @property
    def success(self):
        return self.outcome in (ScanLog.Outcome.CHECK_IN, ScanLog.Outcome.CHECK_OUT)


def register_scan(company, employee, distance, now=None, device=None, source=None):
    """Enregistre un passage devant la borne et met à jour le pointage du jour.

    Règle : le premier passage de la journée est l'arrivée ; tout passage ultérieur,
    espacé d'au moins ATTENDANCE_MIN_INTERVAL_MINUTES du précédent, met à jour le départ.
    """
    source = source or AttendanceRecord.Source.FACE
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    today = local_now.date()
    interval = datetime.timedelta(minutes=settings.ATTENDANCE_MIN_INTERVAL_MINUTES)
    Outcome = ScanLog.Outcome

    def log(outcome):
        ScanLog.objects.create(
            company=company, employee=employee, outcome=outcome, distance=distance, device=device, created_at=now
        )

    if employee is None:
        log(Outcome.UNKNOWN)
        return ScanResult(Outcome.UNKNOWN, distance=distance, message="Visage non reconnu." if source == AttendanceRecord.Source.FACE else "Empreinte non reconnue.")

    if employee.status != Employee.Status.ACTIVE:
        log(Outcome.INACTIVE)
        return ScanResult(
            Outcome.INACTIVE,
            employee=employee,
            distance=distance,
            message="Cet employé n'est pas actif : pointage refusé.",
        )

    confidence = confidence_from_distance(distance) if distance is not None else None
    with transaction.atomic():
        record = (
            AttendanceRecord.objects.select_for_update()
            .filter(company=company, employee=employee, date=today)
            .first()
        )
        if record is None:
            record = AttendanceRecord.objects.create(
                company=company,
                employee=employee,
                date=today,
                check_in=now,
                source_in=source,
                confidence=confidence,
            )
            log(Outcome.CHECK_IN)
            return ScanResult(Outcome.CHECK_IN, employee, record, distance, "Arrivée enregistrée.")

        last_event = record.check_out or record.check_in
        if now - last_event < interval:
            log(Outcome.DUPLICATE)
            return ScanResult(Outcome.DUPLICATE, employee, record, distance, "Vous avez déjà pointé à l'instant.")

        record.check_out = now
        record.source_out = source
        record.save(update_fields=["check_out", "source_out", "late_minutes"])
        log(Outcome.CHECK_OUT)
        return ScanResult(Outcome.CHECK_OUT, employee, record, distance, "Départ enregistré.")


# ---------------------------------------------------------------- Jours ouvrés
def holiday_dates(company, start, end):
    from companies.models import Holiday

    return set(Holiday.objects.filter(company=company, date__range=(start, end)).values_list("date", flat=True))


def employees_on_leave(company, day):
    """Identifiants des employés en congé approuvé à la date donnée (module Congés)."""
    try:
        from leaves.services import employee_ids_on_leave
    except ImportError:  # module Congés non installé
        return set()
    return employee_ids_on_leave(company, day)


def working_days(company, start, end):
    """Jours travaillés de l'entreprise entre deux dates incluses (hors jours fériés)."""
    holidays = holiday_dates(company, start, end)
    weekdays = company.work_weekdays
    days, current = [], start
    while current <= end:
        if current.weekday() in weekdays and current not in holidays:
            days.append(current)
        current += datetime.timedelta(days=1)
    return days


def day_status(company, employee, day, record, holidays, on_leave_ids, today):
    """Statut d'un employé pour une journée : present, late, absent, leave, holiday, off, upcoming."""
    if record:
        return "late" if record.late_minutes else "present"
    if day in holidays:
        return "holiday"
    if day.weekday() not in company.work_weekdays:
        return "off"
    if employee.pk in on_leave_ids:
        return "leave"
    if day > today:
        return "upcoming"
    if employee.hire_date and day < employee.hire_date:
        return "off"
    return "absent"
