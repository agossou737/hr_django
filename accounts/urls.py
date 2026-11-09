from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.UserLoginView.as_view(), name="login"),
    path("deconnexion/", views.UserLogoutView.as_view(), name="logout"),
    path("utilisateurs/", views.UserListView.as_view(), name="user_list"),
    path("utilisateurs/nouveau/", views.UserCreateView.as_view(), name="user_create"),
    path("utilisateurs/<int:pk>/modifier/", views.UserUpdateView.as_view(), name="user_update"),
    path("utilisateurs/<int:pk>/mot-de-passe/", views.UserPasswordView.as_view(), name="user_password"),
]
