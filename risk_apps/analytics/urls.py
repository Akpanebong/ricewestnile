from django.urls import path

from . import views


urlpatterns = [
    path("", views.AnalyticsDashboardView.as_view(), name="analytics_dashboard"),
    path("metrics/", views.ProgramMetricListView.as_view(), name="program_metric_list"),


    path('<int:pk>/', views.ProgramMetricDetailView.as_view(), name='metric_detail'),
    path('create/', views.ProgramMetricCreateView.as_view(), name='metric_create'),
    path('<int:pk>/edit/', views.ProgramMetricUpdateView.as_view(), name='metric_update'),
    path('<int:pk>/delete/', views.program_metric_delete, name='metric_delete'),
]
