from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    path("", views.MyExpensesView.as_view(), name="mine"),
    path("nouvelle/", views.ExpenseCreateView.as_view(), name="create"),
    path("a-traiter/", views.PendingView.as_view(), name="pending"),
    path("toutes/", views.ExpenseListView.as_view(), name="list"),
    path("<int:pk>/annuler/", views.CancelView.as_view(), name="cancel"),
    path("<int:pk>/rembourser/", views.PaidView.as_view(), name="paid"),
    path("<int:pk>/justificatif/", views.ReceiptView.as_view(), name="receipt"),
    path("<int:pk>/pdf/", views.PdfView.as_view(), name="pdf"),
    path("<int:pk>/<str:action>/", views.ReviewView.as_view(), name="review"),
]
