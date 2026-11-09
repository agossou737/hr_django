import calendar
import datetime
import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin, KioskRequiredMixin
from companies.exports import csv_response
from employees.models import Department, Employee

from . import services
from .forms import AttendanceRecordForm
from .models import AttendanceRecord, FaceTemplate, ScanLog

STATUS_LABELS = {
    "present": "Présent",
    "late": "En retard",
    "absent": "Absent",
    "leave": "En congé",
    "holiday": "Jour férié",
    "off": "Non travaillé",
    "upcoming": "À venir",
}


def _recent_events(company, limit=8):
    """Derniers pointages du jour (arrivée ou départ), du plus récent au plus ancien."""
    today = timezone.localdate()
    records = AttendanceRecord.objects.filter(company=company, date=today).select_related("employee")
    events = []
    for record in records:
        last = record.check_out or record.check_in
        events.append(
            {
                "name": record.employee.full_name,
                "matricule": record.employee.matricule,
                "action": "Départ" if record.check_out else "Arrivée",
                "time": timezone.localtime(last).strftime("%H:%M:%S"),
                "sort": last,
            }
        )
    events.sort(key=lambda e: e["sort"], reverse=True)
    for event in events:
        event.pop("sort")
    return events[:limit]


# ------------------------------------------------------------------- Borne
@method_decorator([ensure_csrf_cookie, never_cache], name="dispatch")
class KioskView(KioskRequiredMixin, TemplateView):
    template_name = "attendance/kiosk.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent"] = _recent_events(self.request.user.company)
        ctx["kiosk_config"] = {"scanUrl": reverse("attendance:api_scan")}
        ctx["enrolled_count"] = (
            FaceTemplate.objects.filter(company=self.request.user.company).values("employee").distinct().count()
        )
        return ctx


def _json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None


class ScanAPIView(KioskRequiredMixin, View):
    """Reçoit l'empreinte calculée par la borne et enregistre le pointage."""

    http_method_names = ["post"]

    def post(self, request):
        company = request.user.company
        payload = _json_body(request)
        if not isinstance(payload, dict):
            return JsonResponse({"status": "error", "message": "Requête invalide."}, status=400)
        try:
            descriptor = services.validate_descriptor(payload.get("descriptor"))
        except services.InvalidDescriptor as exc:
            return JsonResponse({"status": "error", "message": str(exc)}, status=400)

        employee, distance = services.best_match(company, descriptor)
        result = services.register_scan(company, employee, distance, device=request.user)

        body = {
            "status": result.outcome,
            "success": result.success,
            "message": result.message,
            "recent": _recent_events(company),
        }
        if result.employee:
            emp = result.employee
            body["employee"] = {"name": emp.full_name, "matricule": emp.matricule}
        if result.distance is not None:
            body["confidence"] = services.confidence_from_distance(result.distance)
        if result.record:
            local = timezone.localtime(result.record.check_out or result.record.check_in)
            body["date"] = local.strftime("%d/%m/%Y")
            body["time"] = local.strftime("%H:%M:%S")
            body["late_minutes"] = result.record.late_minutes
        return JsonResponse(body)


# --------------------------------------------------------------- Enrôlement
class EnrollView(HRRequiredMixin, TemplateView):
    template_name = "attendance/enroll.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id:
            self.employee = get_object_or_404(Employee, pk=kwargs["employee_pk"], company=request.user.company)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employee"] = self.employee
        ctx["samples_count"] = self.employee.face_templates.count()
        ctx["enroll_config"] = {
            "saveUrl": reverse("attendance:api_enroll", args=[self.employee.pk]),
            "samples": 5,
        }
        return ctx


@method_decorator(ensure_csrf_cookie, name="dispatch")
class EnrollAPIView(HRRequiredMixin, View):
    http_method_names = ["post"]
    MAX_SAMPLES = 10

    def post(self, request, employee_pk):
        employee = get_object_or_404(Employee, pk=employee_pk, company=request.user.company)
        payload = _json_body(request)
        if not isinstance(payload, dict):
            return JsonResponse({"status": "error", "message": "Requête invalide."}, status=400)
        if payload.get("consent") is not True:
            return JsonResponse(
                {"status": "error", "message": "Le consentement de l'employé est obligatoire."}, status=400
            )
        samples = payload.get("descriptors")
        if not isinstance(samples, list) or not (1 <= len(samples) <= self.MAX_SAMPLES):
            return JsonResponse(
                {"status": "error", "message": f"Fournissez entre 1 et {self.MAX_SAMPLES} échantillons."},
                status=400,
            )
        try:
            cleaned = [services.validate_descriptor(sample) for sample in samples]
        except services.InvalidDescriptor as exc:
            return JsonResponse({"status": "error", "message": str(exc)}, status=400)

        now = timezone.now()
        employee.face_templates.all().delete()
        FaceTemplate.objects.bulk_create(
            [FaceTemplate(company=request.user.company, employee=employee, descriptor=d, consent_at=now) for d in cleaned]
        )
        messages.success(request, f"Visage de {employee.full_name} enregistré ({len(cleaned)} échantillons).")
        return JsonResponse({"status": "ok", "redirect": reverse("employees:detail", args=[employee.pk])})


class FaceDeleteView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, employee_pk):
        employee = get_object_or_404(Employee, pk=employee_pk, company=request.user.company)
        deleted, _ = employee.face_templates.all().delete()
        if deleted:
            messages.success(request, f"Données faciales de {employee.full_name} supprimées.")
        return redirect("employees:detail", pk=employee.pk)


# ----------------------------------------------------------------- Présences
def _parse_date(value, default):
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return default


class AttendanceListView(HRRequiredMixin, TemplateView):
    template_name = "attendance/attendance_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.request.user.company
        today = timezone.localdate()
        day = _parse_date(self.request.GET.get("date"), today)
        dept = self.request.GET.get("department", "")
        status_filter = self.request.GET.get("status", "")

        employees = Employee.objects.filter(company=company).exclude(status=Employee.Status.LEFT)
        employees = employees.select_related("department", "position")
        if dept.isdigit():
            employees = employees.filter(department_id=dept)
        records = {
            r.employee_id: r
            for r in AttendanceRecord.objects.filter(company=company, date=day)
        }
        holidays = services.holiday_dates(company, day, day)
        on_leave = services.employees_on_leave(company, day)

        rows, summary = [], {key: 0 for key in STATUS_LABELS}
        for emp in employees:
            record = records.get(emp.pk)
            status = services.day_status(company, emp, day, record, holidays, on_leave, today)
            summary[status] += 1
            if status_filter and status != status_filter:
                continue
            rows.append({"employee": emp, "record": record, "status": status, "label": STATUS_LABELS[status]})

        ctx.update(
            day=day,
            prev_day=day - datetime.timedelta(days=1),
            next_day=day + datetime.timedelta(days=1),
            is_today=day == today,
            rows=rows,
            summary=summary,
            departments=Department.objects.filter(company=company),
            selected_department=dept,
            selected_status=status_filter,
            status_labels=STATUS_LABELS,
        )
        return ctx


class AttendanceCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = AttendanceRecord
    form_class = AttendanceRecordForm
    template_name = "form_page.html"
    success_url = reverse_lazy("attendance:list")
    extra_context = {"title": "Saisir un pointage", "cancel_url": reverse_lazy("attendance:list")}

    def form_valid(self, form):
        messages.success(self.request, "Pointage enregistré.")
        return super().form_valid(form)


class AttendanceUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = AttendanceRecord
    form_class = AttendanceRecordForm
    template_name = "form_page.html"
    success_url = reverse_lazy("attendance:list")
    extra_context = {"title": "Corriger le pointage", "cancel_url": reverse_lazy("attendance:list")}

    def form_valid(self, form):
        messages.success(self.request, "Pointage mis à jour.")
        return super().form_valid(form)


class AttendanceDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = AttendanceRecord
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("attendance:list")
    extra_context = {"cancel_url": reverse_lazy("attendance:list")}

    def form_valid(self, form):
        messages.success(self.request, "Pointage supprimé.")
        return super().form_valid(form)


# ------------------------------------------------------------------- Rapport
MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août",
             "Septembre", "Octobre", "Novembre", "Décembre"]


def monthly_summary(company, year, month, department_id=None):
    """Synthèse mensuelle par employé : présences, retards, heures, absences."""
    first = datetime.date(year, month, 1)
    last = datetime.date(year, month, calendar.monthrange(year, month)[1])
    today = timezone.localdate()
    upto = min(last, today)
    days = services.working_days(company, first, upto) if upto >= first else []

    employees = Employee.objects.filter(company=company).exclude(status=Employee.Status.LEFT)
    employees = employees.select_related("department")
    if department_id:
        employees = employees.filter(department_id=department_id)

    records = AttendanceRecord.objects.filter(company=company, date__range=(first, last))
    by_employee = {}
    for record in records:
        by_employee.setdefault(record.employee_id, []).append(record)

    rows = []
    for emp in employees:
        emp_records = by_employee.get(emp.pk, [])
        present_days = {r.date for r in emp_records}
        expected = [d for d in days if not emp.hire_date or d >= emp.hire_date]
        leave_days = set()
        if expected:
            for d in expected:
                if d not in present_days and emp.pk in services.employees_on_leave(company, d):
                    leave_days.add(d)
        absences = [d for d in expected if d not in present_days and d not in leave_days]
        rows.append(
            {
                "employee": emp,
                "present": len(present_days),
                "late": sum(1 for r in emp_records if r.late_minutes),
                "late_minutes": sum(r.late_minutes for r in emp_records),
                "hours": round(sum(r.worked_hours for r in emp_records), 2),
                "leave": len(leave_days),
                "absences": len(absences),
                "expected": len(expected),
            }
        )
    return rows, len(days)


class MonthlyReportView(HRRequiredMixin, TemplateView):
    template_name = "attendance/monthly_report.html"

    def _period(self):
        today = timezone.localdate()
        try:
            year = int(self.request.GET.get("year", today.year))
            month = int(self.request.GET.get("month", today.month))
            datetime.date(year, month, 1)
        except (TypeError, ValueError):
            year, month = today.year, today.month
        return year, month

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            year, month = self._period()
            dept = request.GET.get("department", "")
            rows, _ = monthly_summary(request.user.company, year, month, dept if dept.isdigit() else None)
            return csv_response(
                f"presences_{year}-{month:02d}.csv",
                ["Matricule", "Nom", "Département", "Jours présent", "Retards", "Minutes de retard",
                 "Heures travaillées", "Jours de congé", "Absences"],
                [
                    [
                        r["employee"].matricule,
                        r["employee"].full_name,
                        r["employee"].department or "",
                        r["present"], r["late"], r["late_minutes"],
                        str(r["hours"]).replace(".", ","), r["leave"], r["absences"],
                    ]
                    for r in rows
                ],
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.request.user.company
        year, month = self._period()
        dept = self.request.GET.get("department", "")
        rows, working = monthly_summary(company, year, month, dept if dept.isdigit() else None)
        today = timezone.localdate()
        ctx.update(
            rows=rows,
            working_days=working,
            year=year,
            month=month,
            month_name=MONTHS_FR[month - 1],
            months=list(enumerate(MONTHS_FR, start=1)),
            years=list(range(today.year - 2, today.year + 1)),
            departments=Department.objects.filter(company=company),
            selected_department=dept,
        )
        return ctx


# ------------------------------------------------------------------- Journal
class ScanLogListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = ScanLog
    template_name = "attendance/scan_logs.html"
    context_object_name = "logs"
    paginate_by = 30

    def get_queryset(self):
        qs = super().get_queryset().select_related("employee", "device")
        outcome = self.request.GET.get("outcome")
        if outcome in ScanLog.Outcome.values:
            qs = qs.filter(outcome=outcome)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["outcomes"] = ScanLog.Outcome.choices
        ctx["selected_outcome"] = self.request.GET.get("outcome", "")
        return ctx
