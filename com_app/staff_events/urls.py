from django.urls import path

from . import views

app_name = "staff_events"

urlpatterns = [
    path("", views.StaffEventListView.as_view(), name="list"),
    path("add/", views.StaffEventCreateView.as_view(), name="create"),
    path("<int:pk>/", views.StaffEventDetailView.as_view(), name="detail"),
    path("<int:pk>/minutes/", views.StaffEventMinutesView.as_view(), name="minutes"),
]
