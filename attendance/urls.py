from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("borne/", views.KioskView.as_view(), name="kiosk"),
    path("api/scan/", views.ScanAPIView.as_view(), name="api_scan"),
    path("presences/", views.AttendanceListView.as_view(), name="list"),
    path("presences/nouveau/", views.AttendanceCreateView.as_view(), name="create"),
    path("presences/<int:pk>/modifier/", views.AttendanceUpdateView.as_view(), name="update"),
    path("presences/<int:pk>/supprimer/", views.AttendanceDeleteView.as_view(), name="delete"),
    path("rapport/", views.MonthlyReportView.as_view(), name="monthly"),
    path("journal/", views.ScanLogListView.as_view(), name="logs"),
    path("employes/<int:employee_pk>/visage/", views.EnrollView.as_view(), name="enroll"),
    path("employes/<int:employee_pk>/visage/api/", views.EnrollAPIView.as_view(), name="api_enroll"),
    path("employes/<int:employee_pk>/visage/supprimer/", views.FaceDeleteView.as_view(), name="face_delete"),
]
