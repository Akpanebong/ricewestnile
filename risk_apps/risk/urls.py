from django.urls import path
from . import views
from risk_apps.risk.view import scenario_views

urlpatterns = [
    path('', views.RiskListView.as_view(), name='risk_list'),
    path('create/', views.RiskCreateView.as_view(), name='risk_create'),
    path('<uuid:pk>/', views.RiskDetailView.as_view(), name='risk_detail'),
    path('<uuid:pk>/update/', views.RiskUpdateView.as_view(), name='risk_update'),
    path('<uuid:pk>/delete/<str:risk_id>/', views.trash_risk, name='risk_delete'),

    # Treatments
    path('<uuid:pk>/treatments/', views.RiskTreatmentListView.as_view(), name='risk_treatments'),
    path('<uuid:pk>/treatments/create/', views.RiskTreatmentCreateView.as_view(), name='risk_treatment_create'),

    # Matrix & Dashboard
    path('matrix/', views.RiskMatrixView.as_view(), name='risk_matrix'),

    # GARCIS risk feature registers
    path('incidents/', views.RiskIncidentListView.as_view(), name='risk_incident_list'),
    path('incidents/create/', views.RiskIncidentCreateView.as_view(), name='risk_incident_create'),
    path('incidents/<uuid:pk>/', views.RiskIncidentDetailView.as_view(), name='risk_incident_detail'),
    path('incidents/<uuid:pk>/update/', views.RiskIncidentUpdateView.as_view(), name='risk_incident_update'),

    path('kris/', views.KeyRiskIndicatorListView.as_view(), name='risk_kri_list'),
    path('kris/create/', views.KeyRiskIndicatorCreateView.as_view(), name='risk_kri_create'),
    path('kris/<uuid:pk>/', views.KeyRiskIndicatorDetailView.as_view(), name='risk_kri_detail'),
    path('kris/<uuid:pk>/update/', views.KeyRiskIndicatorUpdateView.as_view(), name='risk_kri_update'),

    path('controls/', views.RiskControlListView.as_view(), name='risk_control_list'),
    path('controls/create/', views.RiskControlCreateView.as_view(), name='risk_control_create'),
    path('controls/<uuid:pk>/', views.RiskControlDetailView.as_view(), name='risk_control_detail'),
    path('controls/<uuid:pk>/update/', views.RiskControlUpdateView.as_view(), name='risk_control_update'),

    path('continuity/', views.BusinessContinuityPlanListView.as_view(), name='risk_continuity_list'),
    path('continuity/create/', views.BusinessContinuityPlanCreateView.as_view(), name='risk_continuity_create'),
    path('continuity/<uuid:pk>/', views.BusinessContinuityPlanDetailView.as_view(), name='risk_continuity_detail'),
    path('continuity/<uuid:pk>/update/', views.BusinessContinuityPlanUpdateView.as_view(), name='risk_continuity_update'),

    path('third-party/', views.ThirdPartyRiskListView.as_view(), name='risk_third_party_list'),
    path('third-party/create/', views.ThirdPartyRiskCreateView.as_view(), name='risk_third_party_create'),
    path('third-party/<uuid:pk>/', views.ThirdPartyRiskDetailView.as_view(), name='risk_third_party_detail'),
    path('third-party/<uuid:pk>/update/', views.ThirdPartyRiskUpdateView.as_view(), name='risk_third_party_update'),

    path('esg/', views.EnvironmentalSocialRiskListView.as_view(), name='risk_esg_list'),
    path('esg/create/', views.EnvironmentalSocialRiskCreateView.as_view(), name='risk_esg_create'),
    path('esg/<uuid:pk>/', views.EnvironmentalSocialRiskDetailView.as_view(), name='risk_esg_detail'),
    path('esg/<uuid:pk>/update/', views.EnvironmentalSocialRiskUpdateView.as_view(), name='risk_esg_update'),

    path('whistleblowing/', views.WhistleblowerCaseListView.as_view(), name='risk_whistleblower_list'),
    path('whistleblowing/create/', views.WhistleblowerCaseCreateView.as_view(), name='risk_whistleblower_create'),
    path('whistleblowing/<uuid:pk>/', views.WhistleblowerCaseDetailView.as_view(), name='risk_whistleblower_detail'),
    path('whistleblowing/<uuid:pk>/update/', views.WhistleblowerCaseUpdateView.as_view(), name='risk_whistleblower_update'),

    # Export & Reports
    path('export/excel/', views.ExportRiskExcelView.as_view(), name='export_risk_excel'),
    path('export/pdf/', views.RiskPDFView.as_view(), name='export_risk_pdf'),

    # Scenario
    path('scenario/', views.ScenarioListView.as_view(), name='scenario_list'),
    path('scenario/create/', views.ScenarioCreateView.as_view(), name='scenario_create'),
    path('scenario/<int:pk>/', views.ScenarioDetailView.as_view(), name='scenario_detail'),

    path('scenario-analysis/', scenario_views.ScenarioAnalysisView.as_view(), name='scenario_analysis'),
]
