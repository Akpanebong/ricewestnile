from django.urls import path
from . import views
app_name = 'asset'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/new/', views.asset_create, name='asset_create'),
    path('assets/<int:pk>/<slug:slug>/', views.asset_detail, name='asset_detail'),
    path('assets/<int:pk>/maintenance/<slug:slug>/', views.add_maintenance, name='add_maintenance'),
]
