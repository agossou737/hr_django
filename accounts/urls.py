from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.UserLoginView.as_view(), name="login"),
    path("deconnexion/", views.UserLogoutView.as_view(), name="logout"),
]
