from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin
from leaves.views import CompanyUserMixin

from . import services
from .forms import AssetForm, AssignForm, ReturnForm
from .models import Asset, AssetAssignment


class AssetListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Asset
    template_name = "assets/list.html"
    context_object_name = "assets"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = []
            for a in self.get_queryset():
                cur = a.current_assignment
                rows.append([a.tag, a.name, a.get_category_display(), a.serial_number, a.value,
                             a.get_condition_display(), a.get_status_display(), cur.employee.full_name if cur else ""])
            return export_table(request.GET["export"], "materiel", "Inventaire du matériel",
                                ["Code", "Désignation", "Catégorie", "N° série", "Valeur", "État", "Statut", "Détenteur"],
                                rows, request.user.company)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        g = self.request.GET
        if g.get("status") in Asset.Status.values:
            qs = qs.filter(status=g["status"])
        if g.get("category") in Asset.Category.values:
            qs = qs.filter(category=g["category"])
        if g.get("q"):
            from django.db.models import Q

            qs = qs.filter(Q(name__icontains=g["q"]) | Q(tag__icontains=g["q"]) | Q(serial_number__icontains=g["q"]))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(statuses=Asset.Status.choices, categories=Asset.Category.choices,
                   f_status=self.request.GET.get("status", ""), f_category=self.request.GET.get("category", ""),
                   q=self.request.GET.get("q", ""))
        return ctx


class AssetCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Asset
    form_class = AssetForm
    template_name = "form_page.html"
    success_url = reverse_lazy("assets:list")
    extra_context = {"title": "Nouveau matériel", "cancel_url": reverse_lazy("assets:list")}


class AssetUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Asset
    form_class = AssetForm
    template_name = "form_page.html"
    success_url = reverse_lazy("assets:list")
    extra_context = {"title": "Modifier le matériel", "cancel_url": reverse_lazy("assets:list")}


class AssetDetailView(HRRequiredMixin, CompanyQuerysetMixin, DetailView):
    model = Asset
    template_name = "assets/detail.html"
    context_object_name = "asset"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["history"] = self.object.assignments.select_related("employee")
        ctx["current"] = self.object.current_assignment
        return ctx


class AssetDeleteView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        asset = get_object_or_404(Asset, pk=pk, company=request.user.company)
        if asset.assignments.exists():
            messages.error(request, "Ce matériel a un historique d'affectation : réformez-le plutôt que de le supprimer.")
            return redirect("assets:detail", pk=pk)
        asset.delete()
        messages.success(request, "Matériel supprimé.")
        return redirect("assets:list")


class AssetRetireView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        asset = get_object_or_404(Asset, pk=pk, company=request.user.company)
        if asset.status == Asset.Status.ASSIGNED:
            messages.error(request, "Faites d'abord restituer ce matériel.")
        else:
            asset.status = Asset.Status.RETIRED if asset.status != Asset.Status.RETIRED else Asset.Status.AVAILABLE
            asset.save(update_fields=["status"])
        return redirect("assets:detail", pk=pk)


class AssignView(HRRequiredMixin, FormView):
    form_class = AssignForm
    template_name = "form_page.html"

    def dispatch(self, request, *args, **kwargs):
        self.asset = get_object_or_404(Asset, pk=kwargs["pk"], company=request.user.company) \
            if request.user.is_authenticated and request.user.company_id else None
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Affecter : {self.asset.name}", cancel_url=reverse_lazy("assets:detail", args=[self.asset.pk]))
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            services.assign(self.asset, d["employee"], self.request.user, d["assigned_at"], notes=d["notes"])
        except services.AssetError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Matériel affecté.")
        return redirect("assets:detail", pk=self.asset.pk)


class ReturnView(HRRequiredMixin, FormView):
    form_class = ReturnForm
    template_name = "form_page.html"

    def dispatch(self, request, *args, **kwargs):
        self.assignment = get_object_or_404(AssetAssignment.objects.select_related("asset", "employee"), pk=kwargs["pk"],
                                            company=request.user.company) \
            if request.user.is_authenticated and request.user.company_id else None
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Restitution : {self.assignment.asset.name}",
                   cancel_url=reverse_lazy("assets:detail", args=[self.assignment.asset_id]))
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            services.give_back(self.assignment, d["returned_at"], d["condition"], d["notes"])
        except services.AssetError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, "Restitution enregistrée.")
        return redirect("assets:detail", pk=self.assignment.asset_id)


class MyAssetsView(CompanyUserMixin, TemplateView):
    template_name = "assets/mine.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["assignments"] = AssetAssignment.objects.filter(
            company=self.request.user.company, employee__user=self.request.user).select_related("asset")
        return ctx


class DischargePdfView(CompanyUserMixin, View):
    def get(self, request, pk):
        a = get_object_or_404(AssetAssignment.objects.select_related("asset", "employee__user", "assigned_by", "company"),
                              pk=pk, company=request.user.company)
        if not (request.user.can_manage_hr or a.employee.user_id == request.user.pk):
            raise PermissionDenied
        resp = HttpResponse(services.discharge_pdf(a), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{a.reference}.pdf"'
        return resp
