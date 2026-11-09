from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin
from config.files import download

from .forms import DocumentForm
from .models import EmployeeDocument, expiring_documents


class DocumentListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = EmployeeDocument
    template_name = "documents/document_list.html"
    context_object_name = "documents"
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("employee")
        emp, kind = self.request.GET.get("employee"), self.request.GET.get("kind")
        if emp and emp.isdigit():
            qs = qs.filter(employee_id=emp)
        if kind in EmployeeDocument.Kind.values:
            qs = qs.filter(kind=kind)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from employees.models import Employee

        ctx["employees"] = Employee.objects.filter(company=self.request.user.company)
        ctx["kinds"] = EmployeeDocument.Kind.choices
        ctx["selected_employee"] = self.request.GET.get("employee", "")
        ctx["selected_kind"] = self.request.GET.get("kind", "")
        return ctx


class DocumentCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = EmployeeDocument
    form_class = DocumentForm
    template_name = "form_page.html"
    success_url = reverse_lazy("documents:list")
    extra_context = {"title": "Ajouter un document", "cancel_url": reverse_lazy("documents:list")}

    def get_initial(self):
        initial = super().get_initial()
        emp = self.request.GET.get("employee")
        if emp and emp.isdigit():
            initial["employee"] = emp
        return initial

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "Document ajouté.")
        return super().form_valid(form)


class DocumentUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = EmployeeDocument
    form_class = DocumentForm
    template_name = "form_page.html"
    success_url = reverse_lazy("documents:list")
    extra_context = {"title": "Modifier le document", "cancel_url": reverse_lazy("documents:list")}


class DocumentDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = EmployeeDocument
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("documents:list")
    extra_context = {"cancel_url": reverse_lazy("documents:list")}

    def form_valid(self, form):
        self.object.file.delete(save=False)
        return super().form_valid(form)


class ExpiringDocumentsView(HRRequiredMixin, ListView):
    template_name = "documents/expiring.html"
    context_object_name = "documents"

    def get_queryset(self):
        return expiring_documents(self.request.user.company)


class DocumentDownloadView(LoginRequiredMixin, View):
    """La RH télécharge tout ; un employé uniquement ses propres documents."""

    def get(self, request, pk):
        user = request.user
        if user.company_id is None or user.is_kiosk:
            raise PermissionDenied
        doc = get_object_or_404(EmployeeDocument.objects.select_related("employee"), pk=pk, company=user.company)
        if not user.can_manage_hr and doc.employee.user_id != user.pk:
            raise PermissionDenied
        ext = doc.file.name.rsplit(".", 1)[-1] if "." in doc.file.name else "bin"
        return download(doc.file, f"{doc.title}.{ext}")


class MyDocumentsView(LoginRequiredMixin, ListView):
    template_name = "documents/mine.html"
    context_object_name = "documents"

    def get_queryset(self):
        user = self.request.user
        if user.company_id is None or user.is_kiosk:
            raise PermissionDenied
        return EmployeeDocument.objects.filter(company=user.company, employee__user=user)
