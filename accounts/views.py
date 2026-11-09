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

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_kiosk:
            return redirect("attendance:kiosk")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.request.user.company
        ctx["company"] = company
        if company is None:
            return ctx

        employees = Employee.objects.filter(company=company)
        today = timezone.localdate()
        ctx["total_employees"] = employees.count()
        ctx["active_employees"] = employees.filter(status=Employee.Status.ACTIVE).count()
        ctx["on_leave_employees"] = employees.filter(status=Employee.Status.ON_LEAVE).count()
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
