from django.urls import path

from . import views

app_name = "evaluations"

urlpatterns = [
    path("equipe/", views.EvaluationListView.as_view(), name="list"),
    path("nouvelle/", views.EvaluationCreateView.as_view(), name="create"),
    path("<int:pk>/", views.EvaluationDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.EvaluationUpdateView.as_view(), name="update"),
    path("<int:pk>/transmettre/", views.EvaluationSubmitView.as_view(), name="submit"),
    path("", views.MyEvaluationsView.as_view(), name="mine"),
    path("mes-evaluations/<int:pk>/", views.MyEvaluationDetailView.as_view(), name="my_detail"),
    path("mes-evaluations/<int:pk>/prise-en-compte/", views.AcknowledgeView.as_view(), name="acknowledge"),
]
