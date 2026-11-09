from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.MyPayslipsView.as_view(), name="mine"),
    path("periodes/", views.PeriodListView.as_view(), name="period_list"),
    path("periodes/nouvelle/", views.PeriodCreateView.as_view(), name="period_create"),
    path("periodes/<int:pk>/", views.PeriodDetailView.as_view(), name="period_detail"),
    path("periodes/<int:pk>/calculer/", views.PeriodGenerateView.as_view(), name="period_generate"),
    path("periodes/<int:pk>/supprimer/", views.PeriodDeleteView.as_view(), name="period_delete"),
    path("periodes/<int:pk>/export/<str:fmt>/", views.PeriodExportView.as_view(), name="period_export"),
    path("periodes/<int:pk>/statut/<str:action>/", views.PeriodStatusView.as_view(), name="period_status"),
    path("bulletins/<int:pk>/", views.PayslipDetailView.as_view(), name="payslip_detail"),
    path("bulletins/<int:pk>/pdf/", views.PayslipPDFView.as_view(), name="payslip_pdf"),
    path("bulletins/<int:pk>/elements/ajouter/", views.ItemCreateView.as_view(), name="item_create"),
    path("bulletins/<int:pk>/elements/<int:item_pk>/supprimer/", views.ItemDeleteView.as_view(), name="item_delete"),
    path("parametres/", views.PayrollSettingsView.as_view(), name="settings"),
]
