from django.urls import path

from . import views

app_name = "discipline"

urlpatterns = [
    path("", views.SanctionListView.as_view(), name="list"),
    path("nouvelle/", views.SanctionCreateView.as_view(), name="create"),
    path("mes-mesures/", views.MySanctionsView.as_view(), name="mine"),
    path("<int:pk>/pdf/", views.SanctionPdfView.as_view(), name="pdf"),
    path("<int:pk>/lu/", views.AcknowledgeView.as_view(), name="acknowledge"),
    path("<int:pk>/supprimer/", views.SanctionDeleteView.as_view(), name="delete"),
]
