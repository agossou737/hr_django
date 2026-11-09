from django.urls import path

from . import views

app_name = "meetings"

urlpatterns = [
    path("", views.MyMeetingsView.as_view(), name="mine"),
    path("toutes/", views.MeetingListView.as_view(), name="list"),
    path("nouvelle/", views.MeetingCreateView.as_view(), name="create"),
    path("<int:pk>/", views.MeetingDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.MeetingUpdateView.as_view(), name="update"),
    path("<int:pk>/compte-rendu/", views.MinutesView.as_view(), name="minutes"),
    path("<int:pk>/annuler/", views.CancelView.as_view(), name="cancel"),
    path("<int:pk>/action/", views.ActionAddView.as_view(), name="action_add"),
    path("action/<int:pk>/basculer/", views.ActionToggleView.as_view(), name="action_toggle"),
    path("<int:pk>/pdf/<str:which>/", views.PdfView.as_view(), name="pdf"),
]
