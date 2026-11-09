from django.urls import path

from . import views

app_name = "training"

urlpatterns = [
    path("", views.MyTrainingsView.as_view(), name="mine"),
    path("toutes/", views.TrainingListView.as_view(), name="list"),
    path("nouvelle/", views.TrainingCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TrainingDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.TrainingUpdateView.as_view(), name="update"),
    path("<int:pk>/inscrire/", views.EnrollView.as_view(), name="enroll"),
    path("participants/<int:pk>/", views.ParticipantUpdateView.as_view(), name="participant"),
    path("participants/<int:pk>/attestation/", views.CertificateView.as_view(), name="certificate"),
]
