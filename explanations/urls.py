from django.urls import path

from . import views

app_name = "explanations"

urlpatterns = [
    path("", views.MyExplanationsView.as_view(), name="mine"),
    path("toutes/", views.ExplanationListView.as_view(), name="list"),
    path("nouvelle/", views.ExplanationCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ExplanationDetailView.as_view(), name="detail"),
    path("<int:pk>/repondre/", views.AnswerView.as_view(), name="answer"),
    path("<int:pk>/annuler/", views.CancelView.as_view(), name="cancel"),
    path("<int:pk>/<str:action>/decision/", views.DecideView.as_view(), name="decide"),
    path("<int:pk>/pdf/<str:which>/", views.PdfView.as_view(), name="pdf"),
]
