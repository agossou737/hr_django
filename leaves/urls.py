from django.urls import path

from . import views

app_name = "leaves"

urlpatterns = [
    path("", views.MyLeavesView.as_view(), name="mine"),
    path("demande/", views.LeaveRequestCreateView.as_view(), name="create"),
    path("<int:pk>/annuler/", views.LeaveCancelView.as_view(), name="cancel"),
    path("a-traiter/", views.PendingLeavesView.as_view(), name="pending"),
    path("interim/", views.ReplacementListView.as_view(), name="replacements"),
    path("interim/<int:pk>/<str:action>/", views.ReplacementRespondView.as_view(), name="replacement_respond"),
    path("<int:pk>/pdf/", views.LeavePdfView.as_view(), name="pdf"),
    path("permissions/", views.MyPermissionsView.as_view(), name="permission_mine"),
    path("permissions/demande/", views.PermissionCreateView.as_view(), name="permission_create"),
    path("permissions/a-traiter/", views.PermissionPendingView.as_view(), name="permission_pending"),
    path("permissions/toutes/", views.PermissionListView.as_view(), name="permission_list"),
    path("permissions/<int:pk>/annuler/", views.PermissionCancelView.as_view(), name="permission_cancel"),
    path("permissions/<int:pk>/pdf/", views.PermissionPdfView.as_view(), name="permission_pdf"),
    path("permissions/<int:pk>/<str:action>/", views.PermissionReviewView.as_view(), name="permission_review"),
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
