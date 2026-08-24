from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("",views.NotificationListView.as_view(),name="list",),
    path("dashboard/", views.NotificationDashboardView.as_view(), name="dashboard",),
    path("create/",views.NotificationCreateView.as_view(), name="create",),
    path("<uuid:pk>/",views.NotificationDetailView.as_view(),name="detail",),
    path("<uuid:pk>/update/",views.NotificationUpdateView.as_view(),name="update",),
    path("<uuid:pk>/delete/",views.notification_delete,name="delete",),
    path("<uuid:pk>/read/",views.mark_notification_read,name="read",),
    path("mark-all-read/",views.mark_all_as_read,name="mark_all_read",),
]