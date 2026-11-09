from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, View

from accounts.mixins import CompanyQuerysetMixin, HRRequiredMixin
from config.files import download
from employees.models import Employee
from leaves import services as lsv
from leaves.views import CompanyUserMixin, ReviewerMixin

from . import services
from .forms import ExpenseForm
from .models import ExpenseClaim


def _me(user):
    return Employee.objects.filter(company=user.company, user=user).first()


class MyExpensesView(CompanyUserMixin, TemplateView):
    template_name = "expenses/mine.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = _me(self.request.user)
        ctx.update(employee=emp, claims=emp.expense_claims.all() if emp else [])
        return ctx


class ExpenseCreateView(CompanyUserMixin, CreateView):
    model = ExpenseClaim
    form_class = ExpenseForm
    template_name = "form_page.html"
    success_url = reverse_lazy("expenses:mine")
    extra_context = {"title": "Nouvelle note de frais", "cancel_url": reverse_lazy("expenses:mine")}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id and _me(request.user) is None:
            messages.error(request, "Votre compte n'est lié à aucune fiche employé. Contactez les RH.")
            return redirect("expenses:mine")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(company=self.request.user.company, employee=_me(self.request.user))
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        services.notify_new(self.object)
        messages.success(self.request, "Note de frais envoyée.")
        return response


class CancelView(CompanyUserMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        c = get_object_or_404(ExpenseClaim, pk=pk, company=request.user.company, employee__user=request.user)
        if c.is_pending:
            c.status = ExpenseClaim.Status.CANCELLED
            c.save(update_fields=["status"])
        return redirect("expenses:mine")


class PendingView(ReviewerMixin, TemplateView):
    template_name = "expenses/pending.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["claims"] = lsv.reviewable(self.request.user, ExpenseClaim)
        return ctx


class ReviewView(ReviewerMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk, action):
        c = get_object_or_404(ExpenseClaim, pk=pk, company=request.user.company)
        if action not in ("approve", "reject") or not lsv.can_review(request.user, c):
            raise PermissionDenied
        if c.is_pending:
            services.review(c, request.user, action == "approve", request.POST.get("comment", "").strip())
            messages.success(request, "Décision enregistrée.")
        return redirect("expenses:pending")


class PaidView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        c = get_object_or_404(ExpenseClaim, pk=pk, company=request.user.company)
        if c.status == ExpenseClaim.Status.APPROVED:
            services.mark_paid(c)
            messages.success(request, "Marquée comme remboursée.")
        return redirect("expenses:list")


class ExpenseListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = ExpenseClaim
    template_name = "expenses/list.html"
    context_object_name = "claims"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = [[c.reference, c.employee.matricule, c.employee.full_name, c.date, c.title, c.get_category_display(),
                     c.amount, c.get_status_display()] for c in self.get_queryset()]
            return export_table(request.GET["export"], "notes-de-frais", "Notes de frais",
                                ["Réf.", "Matricule", "Employé", "Date", "Objet", "Catégorie", "Montant (FCFA)", "Statut"],
                                rows, request.user.company)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset().select_related("employee")
        st = self.request.GET.get("status")
        return qs.filter(status=st) if st in ExpenseClaim.Status.values else qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(statuses=ExpenseClaim.Status.choices, selected_status=self.request.GET.get("status", ""))
        return ctx


class ReceiptView(CompanyUserMixin, View):
    def get(self, request, pk):
        c = get_object_or_404(ExpenseClaim.objects.select_related("employee__user"), pk=pk, company=request.user.company)
        if not services.can_view(request.user, c):
            raise PermissionDenied
        ext = c.receipt.name.rsplit(".", 1)[-1] if "." in c.receipt.name else "bin"
        return download(c.receipt, f"{c.reference}.{ext}")


class PdfView(CompanyUserMixin, View):
    def get(self, request, pk):
        c = get_object_or_404(ExpenseClaim.objects.select_related("employee__user", "reviewed_by", "company"), pk=pk,
                              company=request.user.company)
        if not services.can_view(request.user, c):
            raise PermissionDenied
        resp = HttpResponse(services.claim_pdf(c), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{c.reference}.pdf"'
        return resp
