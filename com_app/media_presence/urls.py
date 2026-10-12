from django.urls import path
from . import views

app_name = "media_presence"

urlpatterns = [
    path("broadcasts/", views.BroadcastListView.as_view(), name="broadcasts"),
    path("broadcasts/new/", views.BroadcastCreateView.as_view(), name="broadcast_create"),
    path("galleries/", views.gallery_years, name="galleries"),
    path("galleries/year/<int:year>/", views.gallery_quarters, name="gallery_quarters"),
    path("galleries/year/<int:year>/quarter/<int:quarter>/", views.gallery_projects, name="gallery_projects"),
    path("galleries/year/<int:year>/quarter/<int:quarter>/project/<int:project_id>/", views.gallery_activities, name="gallery_activities"),
    path("galleries/new/", views.GalleryCreateView.as_view(), name="gallery_create"),
    path("galleries/<int:pk>/", views.gallery_detail, name="gallery_detail"),
    path("photos/<int:pk>/download/", views.photo_download, name="photo_download"),
    path("social-media/", views.SocialMediaListView.as_view(), name="social_media"),
    path("social-media/sync/<str:provider>/", views.sync_social_media_provider, name="social_media_sync_provider"),
    path("social-media/new/", views.SocialMediaCreateView.as_view(), name="social_media_create"),
    path("social-media/export.csv", views.export_social_media_csv, name="social_media_export_csv"),
    path("social-media/export.xlsx", views.export_social_media_excel, name="social_media_export_excel"),
    path("newsletters/", views.NewsletterListView.as_view(), name="newsletters"),
    path("newsletters/new/", views.NewsletterCreateView.as_view(), name="newsletter_create"),
]
