from django.urls import path

from . import views

app_name = "superadmin"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("entreprises/", views.CompanyListView.as_view(), name="companies"),
    path("entreprises/nouvelle/", views.CompanyCreateView.as_view(), name="company_create"),
    path("entreprises/<int:pk>/", views.CompanyDetailView.as_view(), name="company"),
    path("entreprises/<int:pk>/modifier/", views.CompanyUpdateView.as_view(), name="company_update"),
    path("entreprises/<int:pk>/basculer/", views.CompanyToggleView.as_view(), name="company_toggle"),
    path("entreprises/<int:pk>/administrateur/", views.CompanyAdminCreateView.as_view(), name="company_admin"),
    path("utilisateurs/", views.UserListView.as_view(), name="users"),
    path("utilisateurs/<int:pk>/basculer/", views.UserToggleView.as_view(), name="user_toggle"),
    path("utilisateurs/<int:pk>/mot-de-passe/", views.UserResetPasswordView.as_view(), name="user_reset"),
    path("super-administrateurs/", views.SuperAdminListView.as_view(), name="admins"),
    path("super-administrateurs/nouveau/", views.SuperAdminCreateView.as_view(), name="admin_create"),
]
