from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View

from accounts import access
from accounts.models import User
from companies.models import Company
from companies.onboarding import onboard_company
from employees.models import Employee

from .forms import AdminUserForm, CompanyCreateForm, CompanyEditForm


class SuperAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


def credentials_page(request, title, rows):
    return render(request, "superadmin/credentials.html", {"title": title, "rows": rows})


class DashboardView(SuperAdminMixin, TemplateView):
    template_name = "superadmin/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        companies = Company.objects.all()
        ctx.update(
            companies_total=companies.count(), companies_active=companies.filter(is_active=True).count(),
            users_total=User.objects.filter(company__isnull=False).count(),
            employees_total=Employee.objects.count(),
            recent=companies.annotate(n_emp=Count("employees_employee_set", distinct=True)).order_by("-created_at")[:8],
            month_new=companies.filter(created_at__gte=timezone.now().replace(day=1, hour=0, minute=0, second=0)).count(),
        )
        return ctx


class CompanyListView(SuperAdminMixin, ListView):
    template_name = "superadmin/company_list.html"
    context_object_name = "companies"
    paginate_by = 25

    def get_queryset(self):
        qs = Company.objects.annotate(n_emp=Count("employees_employee_set", distinct=True),
                                      n_users=Count("users", distinct=True)).order_by("name")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(email__icontains=q))
        status = self.request.GET.get("status")
        if status in ("active", "suspended"):
            qs = qs.filter(is_active=(status == "active"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(q=self.request.GET.get("q", ""), status=self.request.GET.get("status", ""))
        return ctx


class CompanyCreateView(SuperAdminMixin, FormView):
    form_class = CompanyCreateForm
    template_name = "form_page.html"
    extra_context = {"title": "Nouvelle entreprise cliente", "cancel_url": reverse_lazy("superadmin:companies")}

    def form_valid(self, form):
        d = form.cleaned_data
        password = access.temp_password()
        company, admin = onboard_company(
            d["name"], d["admin_email"], password, d["admin_first_name"], d["admin_last_name"], must_change=True,
            city=d["city"] or "Cotonou", phone=d["phone"], email=d["email"])
        access.send_invitation(admin, password)
        return credentials_page(self.request, f"Entreprise « {company.name} » créée",
                                [(f"Administrateur de {company.name}", admin.email, password)])


class CompanyDetailView(SuperAdminMixin, TemplateView):
    template_name = "superadmin/company_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = get_object_or_404(Company, pk=self.kwargs["pk"])
        ctx.update(company_obj=c, users=c.users.order_by("role", "email"),
                   n_employees=Employee.objects.filter(company=c).count(),
                   n_active=Employee.objects.filter(company=c, status="active").count())
        return ctx


class CompanyUpdateView(SuperAdminMixin, UpdateView):
    model = Company
    form_class = CompanyEditForm
    template_name = "form_page.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Modifier {self.object.name}", cancel_url=reverse("superadmin:company", args=[self.object.pk]))
        return ctx

    def get_success_url(self):
        return reverse("superadmin:company", args=[self.object.pk])


class CompanyToggleView(SuperAdminMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        c = get_object_or_404(Company, pk=pk)
        c.is_active = not c.is_active
        c.save(update_fields=["is_active"])
        messages.success(request, "Entreprise réactivée." if c.is_active else "Entreprise suspendue : ses utilisateurs ne peuvent plus se connecter.")
        return redirect("superadmin:company", pk=pk)


class CompanyAdminCreateView(SuperAdminMixin, FormView):
    form_class = AdminUserForm
    template_name = "form_page.html"

    def dispatch(self, request, *args, **kwargs):
        self.company = get_object_or_404(Company, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Nouvel administrateur — {self.company.name}",
                   cancel_url=reverse("superadmin:company", args=[self.company.pk]))
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        password = access.temp_password()
        user = User.objects.create_user(email=d["email"], password=password, company=self.company, role="admin",
                                        first_name=d["first_name"], last_name=d["last_name"], must_change_password=True)
        access.send_invitation(user, password)
        return credentials_page(self.request, "Administrateur créé", [(self.company.name, user.email, password)])


class UserListView(SuperAdminMixin, ListView):
    template_name = "superadmin/user_list.html"
    context_object_name = "users"
    paginate_by = 30

    def get_queryset(self):
        qs = User.objects.filter(company__isnull=False).select_related("company")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                           | Q(company__name__icontains=q))
        if self.request.GET.get("role") in User.Role.values:
            qs = qs.filter(role=self.request.GET["role"])
        return qs.order_by("company__name", "email")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(q=self.request.GET.get("q", ""), role=self.request.GET.get("role", ""), roles=User.Role.choices)
        return ctx


class SuperAdminListView(SuperAdminMixin, ListView):
    template_name = "superadmin/superadmin_list.html"
    context_object_name = "admins"

    def get_queryset(self):
        return User.objects.filter(is_superuser=True).order_by("email")


class SuperAdminCreateView(SuperAdminMixin, FormView):
    form_class = AdminUserForm
    template_name = "form_page.html"
    extra_context = {"title": "Nouveau super-administrateur", "cancel_url": reverse_lazy("superadmin:admins")}

    def form_valid(self, form):
        d = form.cleaned_data
        password = access.temp_password()
        user = User.objects.create_superuser(email=d["email"], password=password, first_name=d["first_name"],
                                             last_name=d["last_name"], must_change_password=True)
        access.send_invitation_platform(user, password)
        return credentials_page(self.request, "Super-administrateur créé", [("Plateforme", user.email, password)])


class UserToggleView(SuperAdminMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        if u.pk == request.user.pk:
            messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        else:
            u.is_active = not u.is_active
            u.save(update_fields=["is_active"])
            messages.success(request, "Compte réactivé." if u.is_active else "Compte désactivé.")
        return redirect(request.POST.get("next") or "superadmin:users")


class UserResetPasswordView(SuperAdminMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        if u.pk == request.user.pk:
            messages.error(request, "Utilisez « Changer mon mot de passe » pour votre propre compte.")
            return redirect(request.POST.get("next") or "superadmin:users")
        password = access.temp_password()
        u.set_password(password)
        u.must_change_password = True
        u.save(update_fields=["password", "must_change_password"])
        return credentials_page(request, "Mot de passe réinitialisé", [(u.company.name if u.company else "Plateforme", u.email, password)])
