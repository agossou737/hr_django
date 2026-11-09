from django.urls import path

from . import views

app_name = "recruitment"

urlpatterns = [
    path("offres/", views.JobListView.as_view(), name="job_list"),
    path("offres/nouvelle/", views.JobCreateView.as_view(), name="job_create"),
    path("offres/<int:pk>/modifier/", views.JobUpdateView.as_view(), name="job_update"),
    path("offres/<int:pk>/supprimer/", views.JobDeleteView.as_view(), name="job_delete"),
    path("candidatures/", views.ApplicationListView.as_view(), name="application_list"),
    path("candidatures/nouvelle/", views.ApplicationCreateView.as_view(), name="application_create"),
    path("candidatures/<int:pk>/", views.ApplicationDetailView.as_view(), name="application_detail"),
    path("candidatures/<int:pk>/modifier/", views.ApplicationUpdateView.as_view(), name="application_update"),
    path("candidatures/<int:pk>/supprimer/", views.ApplicationDeleteView.as_view(), name="application_delete"),
    path("candidatures/<int:pk>/etape/", views.ApplicationStageView.as_view(), name="application_stage"),
    path("candidatures/<int:pk>/embaucher/", views.ApplicationHireView.as_view(), name="application_hire"),
    path("candidatures/<int:pk>/cv/", views.ApplicationCVView.as_view(), name="application_cv"),
]
