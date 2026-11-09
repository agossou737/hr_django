from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import DashboardView

admin.site.site_header = "JEV — Administration"
admin.site.site_title = "JEV"
admin.site.index_title = "Administration de la plateforme"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", DashboardView.as_view(), name="dashboard"),
    path("compte/", include("accounts.urls")),
    path("employes/", include("employees.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
