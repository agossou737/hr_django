from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView, View

from . import services
from .forms import EvaluationForm
from .models import Evaluation


class ManagerMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        u = request.user
        if u.is_authenticated and (u.company_id is None or u.role not in ("admin", "hr", "manager")):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class EvaluationListView(ManagerMixin, ListView):
    template_name = "evaluations/list.html"
    context_object_name = "evaluations"
    paginate_by = 25

    def get_queryset(self):
        employees = services.evaluable_employees(self.request.user)
        return Evaluation.objects.filter(company=self.request.user.company, employee__in=employees).select_related("employee")


class EvaluationCreateView(ManagerMixin, CreateView):
    model = Evaluation
    form_class = EvaluationForm
    template_name = "form_page.html"
    success_url = reverse_lazy("evaluations:list")
    extra_context = {"title": "Nouvelle évaluation", "cancel_url": reverse_lazy("evaluations:list")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Évaluation enregistrée en brouillon.")
        return super().form_valid(form)


class EvaluationOwnedMixin(ManagerMixin):
    def get_evaluation(self, pk):
        ev = get_object_or_404(Evaluation, pk=pk, company=self.request.user.company)
        if not services.can_manage(self.request.user, ev):
            raise PermissionDenied
        return ev


class EvaluationUpdateView(EvaluationOwnedMixin, UpdateView):
    form_class = EvaluationForm
    template_name = "form_page.html"
    extra_context = {"title": "Modifier l'évaluation"}

    def get_object(self, queryset=None):
        ev = self.get_evaluation(self.kwargs["pk"])
        if ev.status != Evaluation.Status.DRAFT:
            raise PermissionDenied  # une évaluation transmise n'est plus modifiable
        return ev

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("evaluations:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = self.get_success_url()
        return ctx


class EvaluationDetailView(EvaluationOwnedMixin, TemplateView):
    template_name = "evaluations/detail.html"

    def get_context_data(self, pk, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["evaluation"] = self.get_evaluation(pk)
        return ctx


class EvaluationSubmitView(EvaluationOwnedMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        ev = self.get_evaluation(pk)
        if ev.status == Evaluation.Status.DRAFT:
            ev.status = Evaluation.Status.SUBMITTED
            ev.save(update_fields=["status"])
            messages.success(request, "Évaluation transmise à l'employé.")
        return redirect("evaluations:detail", pk=pk)


# ------------------------------------------------------------ Espace employé
class SelfMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        u = request.user
        if u.is_authenticated and (u.company_id is None or u.is_kiosk):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class MyEvaluationsView(SelfMixin, ListView):
    template_name = "evaluations/mine.html"
    context_object_name = "evaluations"

    def get_queryset(self):
        return Evaluation.objects.filter(
            company=self.request.user.company, employee__user=self.request.user
        ).exclude(status=Evaluation.Status.DRAFT)


class MyEvaluationDetailView(SelfMixin, TemplateView):
    template_name = "evaluations/my_detail.html"

    def get_context_data(self, pk, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["evaluation"] = get_object_or_404(
            Evaluation.objects.exclude(status=Evaluation.Status.DRAFT),
            pk=pk, company=self.request.user.company, employee__user=self.request.user,
        )
        return ctx


class AcknowledgeView(SelfMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        ev = get_object_or_404(
            Evaluation.objects.exclude(status=Evaluation.Status.DRAFT),
            pk=pk, company=request.user.company, employee__user=request.user,
        )
        if ev.status == Evaluation.Status.SUBMITTED:
            ev.employee_comment = request.POST.get("comment", "").strip()[:2000]
            ev.status = Evaluation.Status.ACKNOWLEDGED
            ev.save(update_fields=["employee_comment", "status"])
            messages.success(request, "Merci, votre prise en compte est enregistrée.")
        return redirect("evaluations:my_detail", pk=pk)
