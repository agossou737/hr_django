from django.urls import path

from . import views

app_name = "biometrics"

urlpatterns = [
    path("", views.ManageView.as_view(), name="manage"),
    path("mon-empreinte/", views.CredentialsView.as_view(), name="mine"),
    path("employes/<int:pk>/", views.CredentialsView.as_view(), name="employee"),
    path("employes/<int:pk>/options/", views.RegisterOptionsView.as_view(), name="register_options"),
    path("employes/<int:pk>/verifier/", views.RegisterVerifyView.as_view(), name="register_verify"),
    path("appareils/<int:pk>/supprimer/", views.CredentialDeleteView.as_view(), name="credential_delete"),
    path("pointer/", views.ClockView.as_view(), name="clock"),
    path("pointer/options/", views.ClockOptionsView.as_view(), name="clock_options"),
    path("pointer/verifier/", views.ClockVerifyView.as_view(), name="clock_verify"),
    path("lecteurs/nouveau/", views.ReaderCreateView.as_view(), name="reader_create"),
    path("lecteurs/<int:pk>/basculer/", views.ReaderToggleView.as_view(), name="reader_toggle"),
    path("lecteurs/<int:pk>/supprimer/", views.ReaderDeleteView.as_view(), name="reader_delete"),
    path("correspondances/ajouter/", views.MappingAddView.as_view(), name="mapping_add"),
    path("correspondances/<int:pk>/supprimer/", views.MappingDeleteView.as_view(), name="mapping_delete"),
    path("api/lecteur/", views.ReaderScanAPIView.as_view(), name="api_reader"),
]
