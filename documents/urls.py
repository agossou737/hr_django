from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.DocumentListView.as_view(), name="list"),
    path("a-renouveler/", views.ExpiringDocumentsView.as_view(), name="expiring"),
    path("mes-documents/", views.MyDocumentsView.as_view(), name="mine"),
    path("nouveau/", views.DocumentCreateView.as_view(), name="create"),
    path("<int:pk>/modifier/", views.DocumentUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.DocumentDeleteView.as_view(), name="delete"),
    path("<int:pk>/telecharger/", views.DocumentDownloadView.as_view(), name="download"),
]
