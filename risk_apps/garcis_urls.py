from django.urls import path

from risk_apps.risk.view import dashboard as db
app_name    =   'garcis'

urlpatterns = [
    path("", db.Dashboard.as_view(), name="dashboard"),
]