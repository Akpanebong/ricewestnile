from django.urls import path

from . import views


urlpatterns = [
    path("", views.GovernanceDashboardView.as_view(), name="governance_dashboard"),
    # Policy
    path("policies/", views.PolicyListView.as_view(), name="policy_list"),
    path('policies/create/', views.PolicyCreateView.as_view(), name='policy_create'),
    path('<int:pk>/detail/', views.PolicyDetail.as_view(), name='policy_detail'),
    path('policies/<int:pk>/edit/', views.PolicyUpdateView.as_view(), name='policy_update'),
    path('policies/<int:pk>/delete/', views.policy_delete, name='policy_delete'),
    path('policies/<int:pk>/approve/', views.approve_policy, name='policy_approve'),
    path('policies/<int:pk>/reject/', views.reject_policy, name='policy_reject'),
    
    # Control
    path("controls/", views.ControlListView.as_view(), name="control_list"),
    path('control/<int:pk>/detail/', views.ControlDetail.as_view(), name='control_detail'),
    path('controls/create/', views.ControlCreateView.as_view(), name='control_create'),
    path('controls/<int:pk>/edit/', views.ControlUpdateView.as_view(), name='control_update'),
    path('controls/<int:pk>/delete/', views.control_delete, name='control_delete'),
    path('controls/<int:pk>/approve/', views.approve_control, name='control_approve'),
    path('controls/<int:pk>/reject/', views.reject_control, name='control_reject'),

    # Decision
    path("decisions/", views.DecisionRecordListView.as_view(), name="decision_list"),
    path('decision/<int:pk>/detail/', views.DecisionRecordDetail.as_view(), name='decision_detail'),
    path('decisions/create/', views.DecisionCreateView.as_view(), name='decision_create'),
    path('decisions/<int:pk>/edit/', views.DecisionUpdateView.as_view(), name='decision_update'),
    path('decisions/<int:pk>/delete/', views.decision_delete, name='decision_delete'),
    path('decisions/<int:pk>/approve/', views.approve_decision, name='decision_approve'),
    path('decisions/<int:pk>/reject/', views.reject_decision, name='decision_reject'),

    # Stakeholder
    path("engagement/", views.StakeholderEngagementListView.as_view(), name="engagement_list"),
    path('stakeholder/<int:pk>/detail/', views.StakeholderEngagementDetail.as_view(), name='stakeholder_detail'),
    path('stakeholders/create/', views.StakeholderCreateView.as_view(), name='stakeholder_create'),
    path('stakeholders/<int:pk>/edit/', views.StakeholderUpdateView.as_view(), name='stakeholder_update'),
    path('stakeholders/<int:pk>/delete/', views.stakeholder_delete, name='stakeholder_delete'),
]
