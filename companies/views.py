import datetime

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from accounts.mixins import CompanyFormMixin, CompanyQuerysetMixin, HRRequiredMixin

from .benin import benin_holidays
from .forms import CompanySettingsForm, HolidayForm
from .models import Holiday


class CompanySettingsView(HRRequiredMixin, UpdateView):
    form_class = CompanySettingsForm
    template_name = "form_page.html"
    success_url = reverse_lazy("companies:settings")
    extra_context = {"title": "Entreprise et horaires", "cancel_url": reverse_lazy("dashboard")}

    def get_object(self, queryset=None):
        return self.request.user.company

    def form_valid(self, form):
        messages.success(self.request, "Paramètres enregistrés.")
        return super().form_valid(form)


class HolidayListView(HRRequiredMixin, CompanyQuerysetMixin, ListView):
    model = Holiday
    template_name = "companies/holiday_list.html"
    context_object_name = "holidays"

    def get_queryset(self):
        qs = super().get_queryset()
        try:
            self.year = int(self.request.GET.get("year", timezone.localdate().year))
        except ValueError:
            self.year = timezone.localdate().year
        return qs.filter(date__year=self.year)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["year"] = self.year
        return ctx


class HolidayCreateView(HRRequiredMixin, CompanyFormMixin, CreateView):
    model = Holiday
    form_class = HolidayForm
    template_name = "form_page.html"
    success_url = reverse_lazy("companies:holidays")
    extra_context = {"title": "Nouveau jour férié", "cancel_url": reverse_lazy("companies:holidays")}


class HolidayUpdateView(HRRequiredMixin, CompanyQuerysetMixin, CompanyFormMixin, UpdateView):
    model = Holiday
    form_class = HolidayForm
    template_name = "form_page.html"
    success_url = reverse_lazy("companies:holidays")
    extra_context = {"title": "Modifier le jour férié", "cancel_url": reverse_lazy("companies:holidays")}


class HolidayDeleteView(HRRequiredMixin, CompanyQuerysetMixin, DeleteView):
    model = Holiday
    template_name = "confirm_delete.html"
    success_url = reverse_lazy("companies:holidays")
    extra_context = {"cancel_url": reverse_lazy("companies:holidays")}


class HolidayGenerateView(HRRequiredMixin, View):
    """Ajoute les jours fériés légaux du Bénin pour l'année demandée (sans écraser l'existant)."""

    http_method_names = ["post"]

    def post(self, request):
        try:
            year = int(request.POST.get("year", ""))
            datetime.date(year, 1, 1)
        except (ValueError, OverflowError):
            messages.error(request, "Année invalide.")
            return redirect("companies:holidays")
        added = 0
        for date, name in benin_holidays(year):
            _, created = Holiday.objects.get_or_create(
                company=request.user.company, date=date, defaults={"name": name}
            )
            added += created
        messages.success(request, f"{added} jour(s) férié(s) ajouté(s) pour {year}.")
        return redirect(f"{reverse_lazy('companies:holidays')}?year={year}")
