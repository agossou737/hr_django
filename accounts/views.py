from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.utils import timezone
from django.views.generic import TemplateView

from employees.models import Contract, Department, Employee


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    pass


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

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
        ctx["recent_hires"] = employees.order_by("-hire_date")[:5]
        ctx["expiring_contracts"] = Contract.objects.filter(
            company=company,
            is_current=True,
            end_date__isnull=False,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=60),
        ).select_related("employee").order_by("end_date")
        return ctx
