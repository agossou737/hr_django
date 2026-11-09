from django.urls import path

from . import views

app_name = "assets"

urlpatterns = [
    path("", views.AssetListView.as_view(), name="list"),
    path("nouveau/", views.AssetCreateView.as_view(), name="create"),
    path("mon-materiel/", views.MyAssetsView.as_view(), name="mine"),
    path("<int:pk>/", views.AssetDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.AssetUpdateView.as_view(), name="update"),
    path("<int:pk>/supprimer/", views.AssetDeleteView.as_view(), name="delete"),
    path("<int:pk>/reformer/", views.AssetRetireView.as_view(), name="retire"),
    path("<int:pk>/affecter/", views.AssignView.as_view(), name="assign"),
    path("affectation/<int:pk>/restituer/", views.ReturnView.as_view(), name="return"),
    path("affectation/<int:pk>/pdf/", views.DischargePdfView.as_view(), name="pdf"),
]
