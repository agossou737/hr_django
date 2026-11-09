from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from accounts.views import DashboardView

urlpatterns = [
    path("plateforme/", include("superadmin.urls")),
    path("", DashboardView.as_view(), name="dashboard"),
    path("compte/", include("accounts.urls")),
    path("employes/", include("employees.urls")),
    path("pointage/", include("attendance.urls")),
    path("conges/", include("leaves.urls")),
    path("paie/", include("payroll.urls")),
    path("recrutement/", include("recruitment.urls")),
    path("evaluations/", include("evaluations.urls")),
    path("documents/", include("documents.urls")),
    path("notifications/", include("notifications.urls")),
    path("explications/", include("explanations.urls")),
    path("materiel/", include("assets.urls")),
    path("reunions/", include("meetings.urls")),
    path("biometrie/", include("biometrics.urls")),
    path("notes-de-frais/", include("expenses.urls")),
    path("formations/", include("training.urls")),
    path("discipline/", include("discipline.urls")),
    path("parametres/", include("companies.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
