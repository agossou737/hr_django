from django.urls import path

from . import views

app_name = "companies"

urlpatterns = [
    path("entreprise/", views.CompanySettingsView.as_view(), name="settings"),
    path("jours-feries/", views.HolidayListView.as_view(), name="holidays"),
    path("jours-feries/nouveau/", views.HolidayCreateView.as_view(), name="holiday_create"),
    path("jours-feries/generer/", views.HolidayGenerateView.as_view(), name="holiday_generate"),
    path("jours-feries/<int:pk>/modifier/", views.HolidayUpdateView.as_view(), name="holiday_update"),
    path("jours-feries/<int:pk>/supprimer/", views.HolidayDeleteView.as_view(), name="holiday_delete"),
]
