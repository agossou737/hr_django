from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import DashboardView

admin.site.site_header = "Ruche RH — Administration"
admin.site.site_title = "Ruche RH"
admin.site.index_title = "Administration de la plateforme"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", DashboardView.as_view(), name="dashboard"),
    path("compte/", include("accounts.urls")),
    path("employes/", include("employees.urls")),
    path("pointage/", include("attendance.urls")),
    path("conges/", include("leaves.urls")),
    path("paie/", include("payroll.urls")),
    path("recrutement/", include("recruitment.urls")),
    path("evaluations/", include("evaluations.urls")),
    path("documents/", include("documents.urls")),
    path("parametres/", include("companies.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
