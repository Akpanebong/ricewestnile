from django.urls import path
from . import views

app_name = "media_presence"

urlpatterns = [
    path("broadcasts/", views.BroadcastListView.as_view(), name="broadcasts"),
    path("broadcasts/new/", views.BroadcastCreateView.as_view(), name="broadcast_create"),
    path("galleries/", views.GalleryListView.as_view(), name="galleries"),
    path("galleries/new/", views.GalleryCreateView.as_view(), name="gallery_create"),
    path("galleries/<int:pk>/", views.gallery_detail, name="gallery_detail"),
    path("photos/<int:pk>/download/", views.photo_download, name="photo_download"),
]
