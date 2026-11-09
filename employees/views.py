from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin

from .forms import ContractForm, DepartmentForm, EmployeeForm, PositionForm
from .models import Contract, Department, Employee, Position


# --------------------------------------------------------------------- Employés
class EmployeeListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Employee
    template_name = "employees/employee_list.html"
    context_object_name = "employees"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related("department", "position")
        q = self.request.GET.get("q", "").strip()
        dept = self.request.GET.get("department")
        status = self.request.GET.get("status")
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(matricule__icontains=q)
                | Q(email__icontains=q)
            )
        if dept and dept.isdigit():
            qs = qs.filter(department_id=dept)
        if status in Employee.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departments"] = Department.objects.filter(company=self.request.user.company)
        ctx["statuses"] = Employee.Status.choices
        ctx["q"] = self.request.GET.get("q", "")
        ctx["selected_department"] = self.request.GET.get("department", "")
        ctx["selected_status"] = self.request.GET.get("status", "")
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        return ctx


class EmployeeDetailView(HRRequiredMixin, CompanyQuerysetMixin, DetailView):
    model = Employee
    template_name = "employees/employee_detail.html"
    context_object_name = "employee"

    def get_queryset(self):
        return super().get_queryset().select_related("department", "position", "manager")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["face_samples"] = self.object.face_templates.count()
        return ctx


class EmployeeCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/employee_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Employé créé avec succès.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employees:detail", args=[self.object.pk])


class EmployeeUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = "employees/employee_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Fiche employé mise à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("employees:detail", args=[self.object.pk])


class EmployeeDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = Employee
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("employees:list")

    def form_valid(self, form):
        messages.success(self.request, "Employé supprimé.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse("employees:detail", args=[self.object.pk])
        return ctx


# ------------------------------------------------------------------ Départements
class DepartmentListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Department
    template_name = "employees/department_list.html"
    context_object_name = "departments"

    def get_queryset(self):
        return super().get_queryset().select_related("head")


class DepartmentCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "form_page.html"
    success_url = reverse_lazy("employees:department_list")
    extra_context = {"title": "Nouveau département", "cancel_url": reverse_lazy("employees:department_list")}

    def form_valid(self, form):
        messages.success(self.request, "Département créé.")
        return super().form_valid(form)


class DepartmentUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "form_page.html"
    success_url = reverse_lazy("employees:department_list")
    extra_context = {"title": "Modifier le département", "cancel_url": reverse_lazy("employees:department_list")}

    def form_valid(self, form):
        messages.success(self.request, "Département mis à jour.")
        return super().form_valid(form)


class DepartmentDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = Department
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("employees:department_list")
    extra_context = {"cancel_url": reverse_lazy("employees:department_list")}

    def form_valid(self, form):
        messages.success(self.request, "Département supprimé.")
        return super().form_valid(form)


# ------------------------------------------------------------------------ Postes
class PositionListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Position
    template_name = "employees/position_list.html"
    context_object_name = "positions"

    def get_queryset(self):
        return super().get_queryset().select_related("department")


class PositionCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Position
    form_class = PositionForm
    template_name = "form_page.html"
    success_url = reverse_lazy("employees:position_list")
    extra_context = {"title": "Nouveau poste", "cancel_url": reverse_lazy("employees:position_list")}

    def form_valid(self, form):
        messages.success(self.request, "Poste créé.")
        return super().form_valid(form)


class PositionUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Position
    form_class = PositionForm
    template_name = "form_page.html"
    success_url = reverse_lazy("employees:position_list")
    extra_context = {"title": "Modifier le poste", "cancel_url": reverse_lazy("employees:position_list")}

    def form_valid(self, form):
        messages.success(self.request, "Poste mis à jour.")
        return super().form_valid(form)


class PositionDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = Position
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("employees:position_list")
    extra_context = {"cancel_url": reverse_lazy("employees:position_list")}

    def form_valid(self, form):
        messages.success(self.request, "Poste supprimé.")
        return super().form_valid(form)


# --------------------------------------------------------------------- Contrats
class EmployeeScopedMixin:
    """Charge l'employé de l'URL en vérifiant qu'il appartient à l'entreprise."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id:
            self.employee = get_object_or_404(
                Employee, pk=kwargs["employee_pk"], company=request.user.company
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["employee"] = self.employee
        ctx["cancel_url"] = reverse("employees:detail", args=[self.employee.pk])
        return ctx

    def get_success_url(self):
        return reverse("employees:detail", args=[self.employee.pk])


class ContractCreateView(HRRequiredMixin, EmployeeScopedMixin, CompanyFormMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = "form_page.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Nouveau contrat — {self.employee.full_name}"
        return ctx

    def form_valid(self, form):
        form.instance.employee = self.employee
        if form.cleaned_data.get("is_current"):
            self.employee.contracts.update(is_current=False)
        messages.success(self.request, "Contrat enregistré.")
        return super().form_valid(form)


class ContractUpdateView(
    HRRequiredMixin, EmployeeScopedMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView
):
    model = Contract
    form_class = ContractForm
    template_name = "form_page.html"

    def get_queryset(self):
        return super().get_queryset().filter(employee=self.employee)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = f"Modifier le contrat — {self.employee.full_name}"
        return ctx

    def form_valid(self, form):
        if form.cleaned_data.get("is_current"):
            self.employee.contracts.exclude(pk=self.object.pk).update(is_current=False)
        messages.success(self.request, "Contrat mis à jour.")
        return super().form_valid(form)


class ContractDeleteView(HRRequiredMixin, EmployeeScopedMixin, CompanyQuerysetMixin, DeleteView):
    model = Contract
    template_name = "confirm_delete.html"

    def get_queryset(self):
        return super().get_queryset().filter(employee=self.employee)

    def form_valid(self, form):
        messages.success(self.request, "Contrat supprimé.")
        return super().form_valid(form)
