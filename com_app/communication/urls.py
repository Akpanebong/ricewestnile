from django.urls import path
from . import views

app_name = 'comm'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('presentations/', views.PresentationListView.as_view(), name='presentations'),
    path('presentations/<int:pk>/<slug:slug>/reply', views.presentation_reply, name='presentation_reply'),
    path('presentations/add/', views.PresentationCreateView.as_view(), name='presentations_add'),

    path('reports/', views.ReportListView.as_view(), name='reports'),
    path('reports/add/', views.ReportCreateView.as_view(), name='reports_add'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('reports/<int:pk>/review/', views.ReportReviewView.as_view(), name='report_review'),
    # path('reports/<int:pk>/review/', views.report_comment, name='report_review'),
    path('ajax/subgroups/<int:focus_area_id>/', views.subgroups_for_focus_area, name='ajax_subgroups'),
    path('review/queue/', views.ReviewQueueView.as_view(), name='review_queue'),

    path('focus/area/', views.FocusAreaDashboardView.as_view(), name='focusarea-dashboard'),
    path('subgroup/create/', views.SubGroupCreateView.as_view(), name='subgroup-create'),
    path('subgroup/<int:pk>/update/', views.SubGroupUpdateView.as_view(), name='subgroup-update'),
    path('subgroup/<int:pk>/delete/', views.SubGroupDeleteView.as_view(), name='subgroup-delete'),

]
