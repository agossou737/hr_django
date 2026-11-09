from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView, View

from accounts.mixins import HRRequiredMixin
from leaves.views import CompanyUserMixin

from . import services
from .forms import AnswerForm, DecisionForm, ExplanationRequestForm
from .models import Explanation


class MyExplanationsView(CompanyUserMixin, ListView):
    template_name = "explanations/mine.html"
    context_object_name = "explanations"

    def get_queryset(self):
        return Explanation.objects.filter(company=self.request.user.company, employee__user=self.request.user)


class ExplanationListView(HRRequiredMixin, ListView):
    template_name = "explanations/list.html"
    context_object_name = "explanations"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = [[x.reference, x.employee.matricule, x.employee.full_name, x.get_kind_display(), x.date,
                     x.late_minutes, x.get_status_display(), x.deadline] for x in self.get_queryset()]
            return export_table(request.GET["export"], "explications", "Demandes d'explication",
                                ["Réf.", "Matricule", "Employé", "Nature", "Date", "Retard (min)", "Statut", "Échéance"],
                                rows, request.user.company)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Explanation.objects.filter(company=self.request.user.company).select_related("employee")
        status = self.request.GET.get("status")
        if status in Explanation.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = Explanation.Status.choices
        ctx["selected_status"] = self.request.GET.get("status", "")
        return ctx


class _ExplanationMixin(CompanyUserMixin):
    def get_explanation(self, pk):
        exp = get_object_or_404(Explanation.objects.select_related("employee__user", "company"), pk=pk,
                                company=self.request.user.company)
        if not services.can_view(self.request.user, exp):
            raise PermissionDenied
        return exp


class ExplanationDetailView(_ExplanationMixin, TemplateView):
    template_name = "explanations/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        exp = self.get_explanation(self.kwargs["pk"])
        is_owner = exp.employee.user_id == self.request.user.pk
        ctx.update(exp=exp, is_owner=is_owner, can_answer=is_owner and exp.is_pending,
                   can_decide=self.request.user.can_manage_hr and exp.is_answered and not is_owner,
                   answer_form=AnswerForm(), decision_form=DecisionForm())
        return ctx


class AnswerView(_ExplanationMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        exp = self.get_explanation(pk)
        if exp.employee.user_id != request.user.pk:
            raise PermissionDenied
        form = AnswerForm(request.POST)
        if not exp.is_pending:
            messages.error(request, "Cette demande n'attend plus de réponse.")
        elif form.is_valid():
            services.answer(exp, form.cleaned_data["answer"])
            messages.success(request, "Votre réponse a été transmise aux RH.")
        else:
            messages.error(request, "Votre réponse est trop courte.")
        return redirect("explanations:detail", pk=pk)


class DecideView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, action):
        exp = get_object_or_404(Explanation, pk=pk, company=request.user.company)
        if action not in ("accept", "reject") or exp.employee.user_id == request.user.pk:
            raise PermissionDenied
        if not exp.is_answered:
            messages.error(request, "Aucune réponse à traiter.")
        else:
            services.decide(exp, request.user, action == "accept", request.POST.get("comment", "").strip())
            messages.success(request, "Décision enregistrée.")
        return redirect("explanations:detail", pk=pk)


class CancelView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        exp = get_object_or_404(Explanation, pk=pk, company=request.user.company)
        if exp.is_open:
            exp.status = Explanation.Status.CANCELLED
            exp.save(update_fields=["status"])
            messages.success(request, "Demande annulée.")
        return redirect("explanations:list")


class PdfView(_ExplanationMixin, View):
    def get(self, request, pk, which):
        exp = self.get_explanation(pk)
        if which == "demande":
            data = services.request_pdf(exp)
        elif which == "reponse" and exp.answered_at:
            data = services.response_pdf(exp)
        else:
            raise PermissionDenied
        resp = HttpResponse(data, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{exp.reference}-{which}.pdf"'
        return resp


class ExplanationCreateView(HRRequiredMixin, CreateView):
    model = Explanation
    form_class = ExplanationRequestForm
    template_name = "form_page.html"
    extra_context = {"title": "Demander une explication", "cancel_url": reverse_lazy("explanations:list")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        d = form.cleaned_data
        self.object = services.create_manual(self.request.user.company, d["employee"], self.request.user, d["kind"],
                                             d["date"], d["subject"], d["message"])
        messages.success(self.request, "Demande envoyée à l'employé.")
        return redirect("explanations:detail", pk=self.object.pk)
