import io

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin
from companies.exports import csv_response

from . import services
from .forms import PayrollSettingsForm, PayslipItemForm, PeriodForm
from .models import PayrollPeriod, PayrollSettings, Payslip, PayslipItem
from .pdf import build_payslip_pdf

JOURNAL_HEADER = [
    "Matricule", "Nom", "Prénoms", "N° CNSS", "Salaire de base", "Retenue absences", "Primes", "Brut",
    "CNSS salarié", "ITS", "Autres retenues", "Net à payer", "CNSS employeur", "VPS", "Coût employeur",
]


def _journal_rows(period):
    for p in period.payslips.select_related("employee"):
        e = p.employee
        yield [e.matricule, e.last_name, e.first_name, e.cnss_number, p.base_salary, p.unpaid_deduction,
               p.extra_earnings, p.gross, p.cnss_employee, p.its, p.other_deductions, p.net,
               p.cnss_employer, p.vps, p.employer_cost]


# ------------------------------------------------------------------- Périodes
class PeriodListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = PayrollPeriod
    template_name = "payroll/period_list.html"
    context_object_name = "periods"


class PeriodCreateView(HRRequiredMixin, CreateView):
    model = PayrollPeriod
    form_class = PeriodForm
    template_name = "form_page.html"
    extra_context = {"title": "Nouvelle période de paie", "cancel_url": reverse_lazy("payroll:period_list")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def get_success_url(self):
        return reverse("payroll:period_detail", args=[self.object.pk])


class PeriodMixin(HRRequiredMixin):
    def get_period(self, pk):
        return get_object_or_404(PayrollPeriod, pk=pk, company=self.request.user.company)


class PeriodDetailView(PeriodMixin, TemplateView):
    template_name = "payroll/period_detail.html"

    def get_context_data(self, pk, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = self.get_period(pk)
        ctx.update(period=period, payslips=period.payslips.select_related("employee"), totals=services.period_totals(period))
        return ctx


class PeriodGenerateView(PeriodMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        period = self.get_period(pk)
        if not period.is_draft:
            messages.error(request, "Cette période est validée : rouvrez-la pour recalculer.")
        else:
            count, skipped = services.generate_period(period)
            messages.success(request, f"{count} bulletin(s) calculé(s).")
            if skipped:
                names = ", ".join(e.full_name for e in skipped[:5])
                messages.warning(request, f"Sans contrat sur la période, ignoré(s) : {names}{'…' if len(skipped) > 5 else ''}.")
        return redirect("payroll:period_detail", pk=pk)


class PeriodStatusView(PeriodMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, action):
        period = self.get_period(pk)
        if action == "validate":
            if not period.payslips.exists():
                messages.error(request, "Calculez d'abord les bulletins.")
            else:
                services.validate_period(period)
                messages.success(request, "Période validée : les bulletins sont visibles par les employés.")
        elif action == "reopen":
            services.reopen_period(period)
            messages.success(request, "Période rouverte en brouillon.")
        else:
            raise Http404
        return redirect("payroll:period_detail", pk=pk)


class PeriodDeleteView(PeriodMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        period = self.get_period(pk)
        if not period.is_draft:
            messages.error(request, "Une période validée ne peut pas être supprimée.")
            return redirect("payroll:period_detail", pk=pk)
        period.delete()
        messages.success(request, "Période supprimée.")
        return redirect("payroll:period_list")


class PeriodExportView(PeriodMixin, View):
    def get(self, request, pk, fmt):
        period = self.get_period(pk)
        name = f"journal-paie-{period.year}-{period.month:02d}"
        if fmt == "csv":
            return csv_response(f"{name}.csv", JOURNAL_HEADER, _journal_rows(period))
        if fmt == "xlsx":
            from openpyxl import Workbook
            from openpyxl.styles import Font

            wb = Workbook()
            ws = wb.active
            ws.title = "Journal de paie"
            ws.append(JOURNAL_HEADER)
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for row in _journal_rows(period):
                ws.append([float(v) if hasattr(v, "quantize") else v for v in row])
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = 16
            buf = io.BytesIO()
            wb.save(buf)
            response = HttpResponse(
                buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
            return response
        if fmt == "cnss":
            header = ["N° CNSS", "Matricule", "Nom", "Prénoms", "Base cotisable", "CNSS salarié", "CNSS employeur"]
            rows = [[p.employee.cnss_number, p.employee.matricule, p.employee.last_name, p.employee.first_name,
                     p.contribution_base, p.cnss_employee, p.cnss_employer] for p in period.payslips.select_related("employee")]
            return csv_response(f"cnss-{period.year}-{period.month:02d}.csv", header, rows)
        raise Http404


# ------------------------------------------------------------------- Bulletins
class PayslipDetailView(HRRequiredMixin, TemplateView):
    template_name = "payroll/payslip_detail.html"

    def get_context_data(self, pk, **kwargs):
        ctx = super().get_context_data(**kwargs)
        payslip = get_object_or_404(
            Payslip.objects.select_related("employee", "period"), pk=pk, company=self.request.user.company
        )
        ctx.update(payslip=payslip, items=payslip.items.all(), period=payslip.period,
                   settings=PayrollSettings.for_company(self.request.user.company))
        return ctx


class ItemMixin(HRRequiredMixin):
    def get_payslip(self, pk):
        payslip = get_object_or_404(Payslip, pk=pk, company=self.request.user.company)
        if not payslip.period.is_draft:
            raise PermissionDenied
        return payslip


class ItemCreateView(ItemMixin, FormView):
    form_class = PayslipItemForm
    template_name = "form_page.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id and request.user.can_manage_hr:
            self.payslip = self.get_payslip(kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Ajouter un élément — {self.payslip.employee.full_name}",
                   cancel_url=reverse("payroll:payslip_detail", args=[self.payslip.pk]))
        return ctx

    def form_valid(self, form):
        item = form.save(commit=False)
        item.company, item.payslip = self.request.user.company, self.payslip
        item.save()
        services.compute_payslip(self.payslip)
        messages.success(self.request, "Élément ajouté, bulletin recalculé.")
        return redirect("payroll:payslip_detail", pk=self.payslip.pk)


class ItemDeleteView(ItemMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, item_pk):
        payslip = self.get_payslip(pk)
        get_object_or_404(PayslipItem, pk=item_pk, payslip=payslip).delete()
        services.compute_payslip(payslip)
        messages.success(request, "Élément supprimé, bulletin recalculé.")
        return redirect("payroll:payslip_detail", pk=pk)


class PayslipPDFView(LoginRequiredMixin, View):
    """PDF : la RH voit tout ; un employé uniquement ses propres bulletins validés."""

    def get(self, request, pk):
        user = request.user
        if user.company_id is None or user.is_kiosk:
            raise PermissionDenied
        payslip = get_object_or_404(
            Payslip.objects.select_related("employee", "period", "company"), pk=pk, company=user.company
        )
        if not user.can_manage_hr:
            if payslip.employee.user_id != user.pk or payslip.period.is_draft:
                raise Http404
        content = build_payslip_pdf(payslip)
        response = HttpResponse(content, content_type="application/pdf")
        filename = f"bulletin-{payslip.period.year}-{payslip.period.month:02d}-{payslip.employee.matricule}.pdf"
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


class MyPayslipsView(LoginRequiredMixin, TemplateView):
    template_name = "payroll/mine.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.company_id is None or user.is_kiosk:
            raise PermissionDenied
        ctx["payslips"] = (
            Payslip.objects.filter(company=user.company, employee__user=user, period__status=PayrollPeriod.Status.VALIDATED)
            .select_related("period").order_by("-period__year", "-period__month")
        )
        return ctx


class PayrollSettingsView(HRRequiredMixin, UpdateView):
    form_class = PayrollSettingsForm
    template_name = "form_page.html"
    success_url = reverse_lazy("payroll:settings")
    extra_context = {"title": "Paramètres de paie (Bénin)", "cancel_url": reverse_lazy("payroll:period_list")}

    def get_object(self, queryset=None):
        return PayrollSettings.for_company(self.request.user.company)

    def form_valid(self, form):
        messages.success(self.request, "Paramètres de paie enregistrés. Recalculez les périodes en brouillon pour les appliquer.")
        return super().form_valid(form)
