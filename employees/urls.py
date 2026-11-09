from django.urls import path

from . import views

app_name = "employees"

urlpatterns = [
    path("acces/creer-tous/", views.BulkAccessView.as_view(), name="access_bulk"),
    path("<int:pk>/acces/", views.EmployeeAccessView.as_view(), name="access"),
    path("import/", views.ImportView.as_view(), name="import"),
    path("import/modele/", views.ImportTemplateView.as_view(), name="import_template"),
    path("import/apercu/", views.ImportPreviewView.as_view(), name="import_preview"),
    path("import/confirmer/", views.ImportConfirmView.as_view(), name="import_confirm"),
    path("import/erreurs/", views.ImportErrorsView.as_view(), name="import_errors"),
    path("import/annuler/", views.ImportCancelView.as_view(), name="import_cancel"),
    path("", views.EmployeeListView.as_view(), name="list"),
    path("nouveau/", views.EmployeeCreateView.as_view(), name="create"),
    path("<int:pk>/", views.EmployeeDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.EmployeeUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.EmployeeDeleteView.as_view(), name="delete"),
    # Contrats
    path("<int:employee_pk>/contrats/nouveau/", views.ContractCreateView.as_view(), name="contract_create"),
    path("<int:employee_pk>/contrats/<int:pk>/modifier/", views.ContractUpdateView.as_view(), name="contract_update"),
    path("<int:employee_pk>/contrats/<int:pk>/supprimer/", views.ContractDeleteView.as_view(), name="contract_delete"),
    # Départements
    path("departements/", views.DepartmentListView.as_view(), name="department_list"),
    path("departements/nouveau/", views.DepartmentCreateView.as_view(), name="department_create"),
    path("departements/<int:pk>/modifier/", views.DepartmentUpdateView.as_view(), name="department_update"),
    path("departements/<int:pk>/supprimer/", views.DepartmentDeleteView.as_view(), name="department_delete"),
    # Postes
    path("postes/", views.PositionListView.as_view(), name="position_list"),
    path("postes/nouveau/", views.PositionCreateView.as_view(), name="position_create"),
    path("postes/<int:pk>/modifier/", views.PositionUpdateView.as_view(), name="position_update"),
    path("postes/<int:pk>/supprimer/", views.PositionDeleteView.as_view(), name="position_delete"),
]
