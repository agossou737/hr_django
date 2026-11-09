from django.urls import path

from . import views

app_name = "leaves"

urlpatterns = [
    path("", views.MyLeavesView.as_view(), name="mine"),
    path("demande/", views.LeaveRequestCreateView.as_view(), name="create"),
    path("<int:pk>/annuler/", views.LeaveCancelView.as_view(), name="cancel"),
    path("a-traiter/", views.PendingLeavesView.as_view(), name="pending"),
    path("<int:pk>/<str:action>/", views.LeaveReviewView.as_view(), name="review"),
    path("toutes/", views.LeaveListView.as_view(), name="list"),
    path("saisie/", views.HRLeaveCreateView.as_view(), name="hr_create"),
    path("calendrier/", views.LeaveCalendarView.as_view(), name="calendar"),
    path("types/", views.LeaveTypeListView.as_view(), name="type_list"),
    path("types/nouveau/", views.LeaveTypeCreateView.as_view(), name="type_create"),
    path("types/defaut/", views.LeaveTypeDefaultsView.as_view(), name="type_defaults"),
    path("types/<int:pk>/modifier/", views.LeaveTypeUpdateView.as_view(), name="type_update"),
    path("types/<int:pk>/supprimer/", views.LeaveTypeDeleteView.as_view(), name="type_delete"),
]
