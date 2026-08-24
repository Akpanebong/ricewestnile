from django.urls import path
from . import project_views as pro
from . import views


app_name = "core"

urlpatterns = [
    path("currency/", views.currency_settings, name="currency_settings"),
    path("currency/set/", views.set_currency, name="set_currency"),

    path("location/", views.LocationListView.as_view(), name="location_list"),
    path("trash/<int:pk>/<str:sub_county>/location/", views.trash_location, name="trash_location"),
    path("update/<str:sub_county>/<int:pk>/location/", views.location_update, name="location_update"),
    path("create/location/", views.create_location, name="location_create"),
    path("project/", pro.project_list, name="project_list"),
    path("trash/<int:pk>/<str:name>/project/", pro.project_delete, name="trash_project"),
    path("update/<int:pk>/project/<slug:slug>/", pro.project_update, name="project_update"),
    path("create/project/", pro.project_create, name="project_create"),
    path("resources/", views.resource_list, name="resource_list"),
    path("resources/download/<int:pk>/", views.download_resource, name="download_resource"),
    path("resources/delete/<int:pk>/", views.resource_delete, name="resource_delete"),
    path("resources/upload/", views.resource_upload, name="resource_upload"),
]