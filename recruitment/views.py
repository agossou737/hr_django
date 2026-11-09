import datetime

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin
from config.files import download
from employees.models import Employee

from .forms import ApplicationForm, JobOfferForm
from .models import Application, JobOffer


class JobListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = JobOffer
    template_name = "recruitment/job_list.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return super().get_queryset().select_related("department").annotate(
            total=Count("applications"),
            active=Count("applications", filter=~Q(applications__stage__in=["hired", "rejected"])),
        )


class JobCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = JobOffer
    form_class = JobOfferForm
    template_name = "form_page.html"
    success_url = reverse_lazy("recruitment:job_list")
    extra_context = {"title": "Nouvelle offre d'emploi", "cancel_url": reverse_lazy("recruitment:job_list")}


class JobUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = JobOffer
    form_class = JobOfferForm
    template_name = "form_page.html"
    success_url = reverse_lazy("recruitment:job_list")
    extra_context = {"title": "Modifier l'offre", "cancel_url": reverse_lazy("recruitment:job_list")}


class JobDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = JobOffer
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("recruitment:job_list")
    extra_context = {"cancel_url": reverse_lazy("recruitment:job_list")}


class ApplicationListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Application
    template_name = "recruitment/application_list.html"
    context_object_name = "applications"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("job")
        job, stage = self.request.GET.get("job"), self.request.GET.get("stage")
        if job and job.isdigit():
            qs = qs.filter(job_id=job)
        if stage in Application.Stage.values:
            qs = qs.filter(stage=stage)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["jobs"] = JobOffer.objects.filter(company=self.request.user.company)
        ctx["stages"] = Application.Stage.choices
        ctx["selected_job"] = self.request.GET.get("job", "")
        ctx["selected_stage"] = self.request.GET.get("stage", "")
        return ctx


class ApplicationCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Application
    form_class = ApplicationForm
    template_name = "form_page.html"
    success_url = reverse_lazy("recruitment:application_list")
    extra_context = {"title": "Nouvelle candidature", "cancel_url": reverse_lazy("recruitment:application_list")}


class ApplicationDetailView(HRRequiredMixin, CompanyQuerysetMixin, DetailView):
    model = Application
    template_name = "recruitment/application_detail.html"
    context_object_name = "application"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stages"] = Application.Stage.choices
        return ctx


class ApplicationUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Application
    form_class = ApplicationForm
    template_name = "form_page.html"
    extra_context = {"title": "Modifier la candidature"}

    def get_success_url(self):
        return reverse("recruitment:application_detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.get_success_url()
        return ctx


class ApplicationDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = Application
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("recruitment:application_list")
    extra_context = {"cancel_url": reverse_lazy("recruitment:application_list")}


class ApplicationStageView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        app = get_object_or_404(Application, pk=pk, company=request.user.company)
        stage = request.POST.get("stage")
        if stage not in Application.Stage.values or stage == Application.Stage.HIRED:
            messages.error(request, "Étape invalide (utilisez « Embaucher » pour recruter).")
        else:
            app.stage = stage
            app.save(update_fields=["stage"])
            messages.success(request, f"Candidature passée à l'étape « {app.get_stage_display()} ».")
        return redirect("recruitment:application_detail", pk=pk)


class ApplicationHireView(HRRequiredMixin, View):
    """Transforme le candidat en fiche employé (matricule automatique) et clôt la candidature."""

    http_method_names = ["post"]

    def post(self, request, pk):
        app = get_object_or_404(Application, pk=pk, company=request.user.company)
        if app.employee_id:
            messages.error(request, "Ce candidat a déjà été embauché.")
            return redirect("employees:detail", pk=app.employee_id)
        try:
            hire_date = datetime.date.fromisoformat(request.POST.get("hire_date", ""))
        except ValueError:
            hire_date = timezone.localdate()
        employee = Employee.objects.create(
            company=request.user.company, first_name=app.first_name, last_name=app.last_name,
            gender=request.POST.get("gender") if request.POST.get("gender") in ("M", "F") else "M",
            email=app.email, phone=app.phone, hire_date=hire_date, department=app.job.department,
        )
        app.employee, app.stage = employee, Application.Stage.HIRED
        app.save(update_fields=["employee", "stage"])
        messages.success(request, f"{employee.full_name} est maintenant employé ({employee.matricule}). Complétez sa fiche et son contrat.")
        return redirect("employees:update", pk=employee.pk)


class ApplicationCVView(HRRequiredMixin, View):
    def get(self, request, pk):
        app = get_object_or_404(Application, pk=pk, company=request.user.company)
        ext = app.cv.name.rsplit(".", 1)[-1] if app.cv else "pdf"
        return download(app.cv, f"CV-{app.last_name}-{app.first_name}.{ext}")
