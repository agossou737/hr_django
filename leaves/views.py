import calendar
import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin
from attendance.services import holiday_dates
from attendance.views import MONTHS_FR
from employees.models import Employee

from . import services
from .forms import HRLeaveRequestForm, LeaveRequestForm, LeaveTypeForm
from .models import LeaveRequest, LeaveType


class CompanyUserMixin(LoginRequiredMixin):
    """Utilisateur connecté et rattaché à une entreprise (hors compte borne)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.company_id is None or request.user.is_kiosk):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ReviewerMixin(CompanyUserMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in ("admin", "hr", "manager"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _my_employee(user):
    return Employee.objects.filter(company=user.company, user=user).first()


# --------------------------------------------------------------- Espace employé
class MyLeavesView(CompanyUserMixin, TemplateView):
    template_name = "leaves/mine.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = _my_employee(self.request.user)
        ctx["employee"] = employee
        if employee:
            ctx["requests"] = employee.leave_requests.select_related("leave_type")
            ctx["balances"] = services.balances(employee)
        ctx["year"] = timezone.localdate().year
        return ctx


class LeaveRequestCreateView(CompanyUserMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = "form_page.html"
    success_url = reverse_lazy("leaves:mine")
    extra_context = {"title": "Nouvelle demande de congé", "cancel_url": reverse_lazy("leaves:mine")}

    def get(self, request, *args, **kwargs):
        if _my_employee(request.user) is None:
            messages.error(request, "Votre compte n'est lié à aucune fiche employé. Contactez les RH.")
            return redirect("leaves:mine")
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        kwargs["employee"] = _my_employee(self.request.user)
        return kwargs

    def post(self, request, *args, **kwargs):
        if _my_employee(request.user) is None:
            raise PermissionDenied
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Votre demande a été enregistrée.")
        return super().form_valid(form)


class LeaveCancelView(CompanyUserMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        leave = get_object_or_404(
            LeaveRequest, pk=pk, company=request.user.company, employee__user=request.user
        )
        if leave.status in (LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED) and (
            leave.start_date >= timezone.localdate() or leave.is_pending
        ):
            leave.status = LeaveRequest.Status.CANCELLED
            leave.save(update_fields=["status"])
            messages.success(request, "Demande annulée.")
        else:
            messages.error(request, "Cette demande ne peut plus être annulée.")
        return redirect("leaves:mine")


# ------------------------------------------------------------------ Validation
class PendingLeavesView(ReviewerMixin, TemplateView):
    template_name = "leaves/pending.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["requests"] = services.reviewable_requests(self.request.user)
        return ctx


class LeaveReviewView(ReviewerMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, action):
        leave = get_object_or_404(LeaveRequest, pk=pk, company=request.user.company)
        if action not in ("approve", "reject") or not services.can_review(request.user, leave):
            raise PermissionDenied
        if not leave.is_pending:
            messages.error(request, "Cette demande a déjà été traitée.")
        else:
            services.review(leave, request.user, action == "approve", request.POST.get("comment", "").strip())
            messages.success(
                request, "Demande approuvée." if action == "approve" else "Demande refusée."
            )
        return redirect(request.POST.get("next") or "leaves:pending")


# --------------------------------------------------------------------- RH
class LeaveListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = LeaveRequest
    template_name = "leaves/list.html"
    context_object_name = "requests"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = [
                [r.employee.matricule, r.employee.full_name, r.leave_type.name, r.start_date, r.end_date, r.days,
                 r.get_status_display(), r.created_at.date()]
                for r in self.get_queryset()
            ]
            return export_table(request.GET["export"], "conges", "Demandes de congé",
                                ["Matricule", "Employé", "Type", "Du", "Au", "Jours", "Statut", "Demandé le"],
                                rows, request.user.company)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset().select_related("employee", "leave_type")
        status = self.request.GET.get("status")
        if status in LeaveRequest.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = LeaveRequest.Status.choices
        ctx["selected_status"] = self.request.GET.get("status", "")
        return ctx


class HRLeaveCreateView(HRRequiredMixin, CreateView):
    model = LeaveRequest
    form_class = HRLeaveRequestForm
    template_name = "form_page.html"
    success_url = reverse_lazy("leaves:list")
    extra_context = {"title": "Saisir un congé pour un employé", "cancel_url": reverse_lazy("leaves:list")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.is_pending:
            services.review(self.object, self.request.user, True, "Saisi par les RH")
        messages.success(self.request, "Congé enregistré et approuvé.")
        return response


class LeaveTypeListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = LeaveType
    template_name = "leaves/type_list.html"
    context_object_name = "types"


class LeaveTypeCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = "form_page.html"
    success_url = reverse_lazy("leaves:type_list")
    extra_context = {"title": "Nouveau type de congé", "cancel_url": reverse_lazy("leaves:type_list")}


class LeaveTypeUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = "form_page.html"
    success_url = reverse_lazy("leaves:type_list")
    extra_context = {"title": "Modifier le type de congé", "cancel_url": reverse_lazy("leaves:type_list")}


class LeaveTypeDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = LeaveType
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("leaves:type_list")
    extra_context = {"cancel_url": reverse_lazy("leaves:type_list")}

    def form_valid(self, form):
        if self.object.requests.exists():
            messages.error(self.request, "Ce type est utilisé par des demandes : il ne peut pas être supprimé.")
            return redirect("leaves:type_list")
        messages.success(self.request, "Type supprimé.")
        return super().form_valid(form)


class LeaveTypeDefaultsView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        n = services.create_default_types(request.user.company)
        messages.success(request, f"{n} type(s) de congé ajouté(s)." if n else "Les types par défaut existent déjà.")
        return redirect("leaves:type_list")


# -------------------------------------------------------------------- Calendrier
class LeaveCalendarView(CompanyUserMixin, TemplateView):
    template_name = "leaves/calendar.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        try:
            year, month = int(self.request.GET.get("year", today.year)), int(self.request.GET.get("month", today.month))
            first = datetime.date(year, month, 1)
        except (ValueError, OverflowError):
            year, month = today.year, today.month
            first = datetime.date(year, month, 1)
        last = datetime.date(year, month, calendar.monthrange(year, month)[1])
        company = self.request.user.company
        holidays = holiday_dates(company, first, last)
        leaves = (
            LeaveRequest.objects.filter(
                company=company, status=LeaveRequest.Status.APPROVED, start_date__lte=last, end_date__gte=first
            ).select_related("employee", "leave_type")
        )
        # Un employé simple ne voit que ses propres congés ; manager/RH voient toute l'entreprise.
        if self.request.user.role == "employee":
            leaves = leaves.filter(employee__user=self.request.user)
        weeks = []
        for week in calendar.Calendar(0).monthdatescalendar(year, month):
            row = []
            for day in week:
                row.append(
                    {
                        "date": day,
                        "in_month": day.month == month,
                        "today": day == today,
                        "holiday": day in holidays,
                        "off": day.weekday() not in company.work_weekdays,
                        "leaves": [l for l in leaves if l.start_date <= day <= l.end_date] if day.month == month else [],
                    }
                )
            weeks.append(row)
        prev = first - datetime.timedelta(days=1)
        nxt = last + datetime.timedelta(days=1)
        ctx.update(
            weeks=weeks, year=year, month=month, month_name=MONTHS_FR[month - 1],
            prev=(prev.year, prev.month), next=(nxt.year, nxt.month),
            weekdays=["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
        )
        return ctx
