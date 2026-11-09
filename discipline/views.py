from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, View

from accounts.mixins import CompanyQuerysetMixin, HRRequiredMixin
from leaves.views import CompanyUserMixin

from . import services
from .forms import SanctionForm
from .models import Sanction


class SanctionListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Sanction
    template_name = "discipline/list.html"
    context_object_name = "sanctions"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = [[s.reference, s.employee.matricule, s.employee.full_name, s.get_kind_display(), s.date, s.reason,
                     "Oui" if s.acknowledged_at else "Non"] for s in self.get_queryset()]
            return export_table(request.GET["export"], "sanctions", "Mesures disciplinaires",
                                ["Réf.", "Matricule", "Employé", "Nature", "Date", "Motif", "Pris connaissance"], rows,
                                request.user.company)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().select_related("employee")


class SanctionCreateView(HRRequiredMixin, CreateView):
    model = Sanction
    form_class = SanctionForm
    template_name = "form_page.html"
    success_url = reverse_lazy("discipline:list")
    extra_context = {"title": "Notifier une mesure disciplinaire", "cancel_url": reverse_lazy("discipline:list")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        form.instance.issued_by = self.request.user
        response = super().form_valid(form)
        services.notify_employee(self.object)
        messages.success(self.request, "Mesure enregistrée et notifiée à l'employé.")
        return response


class SanctionDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = Sanction
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("discipline:list")
    extra_context = {"cancel_url": reverse_lazy("discipline:list")}


class MySanctionsView(CompanyUserMixin, TemplateView):
    template_name = "discipline/mine.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sanctions"] = Sanction.objects.filter(company=self.request.user.company, employee__user=self.request.user)
        return ctx


class AcknowledgeView(CompanyUserMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        s = get_object_or_404(Sanction, pk=pk, company=request.user.company, employee__user=request.user)
        if not s.acknowledged_at:
            services.acknowledge(s)
            messages.success(request, "Prise de connaissance enregistrée.")
        return redirect("discipline:mine")


class SanctionPdfView(CompanyUserMixin, View):
    def get(self, request, pk):
        s = get_object_or_404(Sanction.objects.select_related("employee__user", "issued_by", "company", "explanation"),
                              pk=pk, company=request.user.company)
        if not (request.user.can_manage_hr or s.employee.user_id == request.user.pk):
            raise PermissionDenied
        resp = HttpResponse(services.sanction_pdf(s), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{s.reference}.pdf"'
        return resp
