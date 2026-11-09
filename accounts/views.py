from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.generic import TemplateView

from employees.models import Contract, Department, Employee


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        user = self.request.user
        if user.is_authenticated and user.is_kiosk:
            return reverse("attendance:kiosk")
        return super().get_default_redirect_url()


class UserLogoutView(LogoutView):
    pass


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_template_names(self):
        user = self.request.user
        if user.company_id and not user.can_manage_hr:
            return ["dashboard_self.html"]
        return [self.template_name]

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_kiosk:
            return redirect("attendance:kiosk")
        return super().dispatch(request, *args, **kwargs)

    def _self_context(self, ctx, company, today):
        from leaves import services as leave_services

        user = self.request.user
        employee = Employee.objects.filter(company=company, user=user).first()
        ctx["employee"] = employee
        if employee:
            ctx["balances"] = [b for b in leave_services.balances(employee) if b["allowed"] or b["used"]]
            ctx["my_requests"] = employee.leave_requests.select_related("leave_type")[:5]
            ctx["today_record"] = employee.attendance_records.filter(date=today).first()
        ctx["to_review"] = leave_services.reviewable_requests(user).count() if user.role == "manager" else 0
        return ctx

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.request.user.company
        ctx["company"] = company
        if company is None:
            return ctx

        employees = Employee.objects.filter(company=company)
        today = timezone.localdate()
        if not self.request.user.can_manage_hr:
            return self._self_context(ctx, company, today)
        ctx["total_employees"] = employees.count()
        ctx["active_employees"] = employees.filter(status=Employee.Status.ACTIVE).count()
        from leaves import services as leave_services
        from leaves.models import LeaveRequest

        ctx["on_leave_employees"] = len(leave_services.employee_ids_on_leave(company, today))
        ctx["pending_leaves"] = LeaveRequest.objects.filter(company=company, status="pending").count()
        ctx["departments_count"] = Department.objects.filter(company=company).count()
        ctx["by_department"] = (
            employees.exclude(status=Employee.Status.LEFT)
            .values("department__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        ctx["recent_hires"] = employees.select_related("position").order_by("-hire_date")[:6]

        # Données des graphiques (sérialisées via json_script dans le template)
        staff = employees.exclude(status=Employee.Status.LEFT)
        by_gender = {row["gender"]: row["total"] for row in staff.values("gender").annotate(total=Count("id"))}
        ctx["gender_chart"] = {
            "labels": ["Hommes", "Femmes"],
            "series": [by_gender.get("M", 0), by_gender.get("F", 0)],
        }
        ctx["department_chart"] = {
            "labels": [r["department__name"] or "Sans département" for r in ctx["by_department"]],
            "series": [r["total"] for r in ctx["by_department"]],
        }
        # Embauches des 6 derniers mois (mois courant inclus)
        months = []
        year, month = today.year, today.month
        for _ in range(6):
            months.append((year, month))
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        months.reverse()
        first_month = date(months[0][0], months[0][1], 1)
        hires = {
            (row["m"].year, row["m"].month): row["total"]
            for row in employees.filter(hire_date__gte=first_month)
            .annotate(m=TruncMonth("hire_date"))
            .values("m")
            .annotate(total=Count("id"))
        }
        month_names = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
        ctx["hires_chart"] = {
            "labels": [month_names[m - 1] for _, m in months],
            "series": [hires.get(key, 0) for key in months],
        }
        ctx["expiring_contracts"] = Contract.objects.filter(
            company=company,
            is_current=True,
            end_date__isnull=False,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=60),
        ).select_related("employee").order_by("end_date")
        return ctx


# ------------------------------------------------------- Gestion des utilisateurs
from django.contrib import messages  # noqa: E402
from django.core.exceptions import PermissionDenied  # noqa: E402
from django.shortcuts import get_object_or_404  # noqa: E402
from django.urls import reverse_lazy  # noqa: E402
from django.views.generic import FormView, ListView  # noqa: E402

from .forms import PasswordResetForm, UserCreateForm, UserUpdateForm  # noqa: E402
from .mixins import HRRequiredMixin  # noqa: E402
from .models import User  # noqa: E402


class CompanyUsersMixin(HRRequiredMixin):
    def get_company_users(self):
        return User.objects.filter(company=self.request.user.company)

    def get_target(self, pk):
        target = get_object_or_404(self.get_company_users(), pk=pk)
        if target.role == User.Role.ADMIN and self.request.user.role != User.Role.ADMIN:
            raise PermissionDenied  # un RH ne modifie pas un administrateur
        return target


class UserListView(CompanyUsersMixin, ListView):
    template_name = "accounts/user_list.html"
    context_object_name = "users_list"

    def get_queryset(self):
        return self.get_company_users().select_related("employee").order_by("last_name", "email")


class UserCreateView(CompanyUsersMixin, FormView):
    form_class = UserCreateForm
    template_name = "form_page.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"title": "Nouvel utilisateur", "cancel_url": reverse_lazy("accounts:user_list")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(company=self.request.user.company, acting_user=self.request.user)
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Utilisateur créé.")
        return super().form_valid(form)


class UserUpdateView(CompanyUsersMixin, FormView):
    form_class = UserUpdateForm
    template_name = "form_page.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"title": "Modifier l'utilisateur", "cancel_url": reverse_lazy("accounts:user_list")}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id and request.user.can_manage_hr:
            self.target = self.get_target(kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(company=self.request.user.company, acting_user=self.request.user, instance=self.target)
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Utilisateur mis à jour.")
        return super().form_valid(form)


class UserPasswordView(CompanyUsersMixin, FormView):
    form_class = PasswordResetForm
    template_name = "form_page.html"
    success_url = reverse_lazy("accounts:user_list")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id and request.user.can_manage_hr:
            self.target = self.get_target(kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Nouveau mot de passe — {self.target}", cancel_url=self.success_url)
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.target
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Mot de passe modifié.")
        return super().form_valid(form)
