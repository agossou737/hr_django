from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin
from leaves.views import CompanyUserMixin

from . import services
from .forms import EnrollForm, TrainingForm
from .models import Training, TrainingParticipant


class TrainingListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Training
    template_name = "training/list.html"
    context_object_name = "trainings"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = []
            for t in self.get_queryset():
                for p in t.participants.select_related("employee"):
                    rows.append([t.title, t.provider, t.start_date, t.end_date, t.cost, p.employee.matricule,
                                 p.employee.full_name, p.get_status_display()])
            return export_table(request.GET["export"], "formations", "Formations et participants",
                                ["Formation", "Organisme", "Début", "Fin", "Coût", "Matricule", "Employé", "Statut"], rows,
                                request.user.company)
        return super().get(request, *args, **kwargs)


class TrainingCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Training
    form_class = TrainingForm
    template_name = "form_page.html"
    success_url = reverse_lazy("training:list")
    extra_context = {"title": "Nouvelle formation", "cancel_url": reverse_lazy("training:list")}


class TrainingUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Training
    form_class = TrainingForm
    template_name = "form_page.html"
    success_url = reverse_lazy("training:list")
    extra_context = {"title": "Modifier la formation", "cancel_url": reverse_lazy("training:list")}


class TrainingDetailView(HRRequiredMixin, CompanyQuerysetMixin, DetailView):
    model = Training
    template_name = "training/detail.html"
    context_object_name = "training"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["participants"] = self.object.participants.select_related("employee")
        ctx["statuses"] = TrainingParticipant.Status.choices
        ctx["form"] = EnrollForm(company=self.request.user.company)
        return ctx


class EnrollView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        t = get_object_or_404(Training, pk=pk, company=request.user.company)
        form = EnrollForm(request.POST, company=request.user.company)
        if form.is_valid():
            n = len(services.enroll(t, form.cleaned_data["employees"]))
            messages.success(request, f"{n} employé(s) inscrit(s).")
        else:
            messages.error(request, "Sélection invalide.")
        return redirect("training:detail", pk=pk)


class ParticipantUpdateView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = get_object_or_404(TrainingParticipant, pk=pk, company=request.user.company)
        action = request.POST.get("action")
        if action == "remove":
            p.delete()
        elif request.POST.get("status") in TrainingParticipant.Status.values:
            p.status = request.POST["status"]
            p.note = request.POST.get("note", "")[:255]
            p.save(update_fields=["status", "note"])
        return redirect("training:detail", pk=p.training_id)


class MyTrainingsView(CompanyUserMixin, TemplateView):
    template_name = "training/mine.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = TrainingParticipant.objects.filter(
            company=self.request.user.company, employee__user=self.request.user).select_related("training")
        return ctx


class CertificateView(CompanyUserMixin, View):
    def get(self, request, pk):
        p = get_object_or_404(TrainingParticipant.objects.select_related("training__company", "employee__user"), pk=pk,
                              company=request.user.company)
        if not (request.user.can_manage_hr or p.employee.user_id == request.user.pk) or p.status != "completed":
            raise PermissionDenied
        resp = HttpResponse(services.certificate_pdf(p), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="attestation-{p.pk}.pdf"'
        return resp
