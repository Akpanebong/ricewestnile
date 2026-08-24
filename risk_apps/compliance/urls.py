from django.urls import path
from .views import *

urlpatterns = [
    path('', ComplianceDashboardView.as_view(), name='compliance_dashboard'),
    path("framework/add/", ComplianceFrameworkCreate.as_view(), name="framework_create"),
    path("framework/<uuid:pk>/edit/", ComplianceFrameworkUpdate.as_view(), name="framework_update"),
    path("framework/list/", ComplianceFrameworkView.as_view(), name="framework"),
    path("framework/<uuid:pk>/delete/", compliance_frame_delete, name="framework_delete"),
    path("framework/<uuid:pk>/", ComplianceFrameworkDetailView.as_view(), name="framework_detail"),

    path("requirement/<uuid:pk>/delete/", compliance_requirement_delete, name="requirement_delete"),
    path('register/', ComplianceRequirementView.as_view(), name='compliance_register'),
    path('requirement/<uuid:pk>/', ComplianceDetailView.as_view(), name='compliance_detail'),
    path("framework/<uuid:framework_id>/requirement/create/", ComplianceRequirementCreateView.as_view(),
         name="requirement_create"),


    path('calendar/', ComplianceCalendarView.as_view(), name='compliance_calendar'),
    path("requirement/<uuid:requirement_id>/task/create/", ComplianceTaskCreateView.as_view(),
         name="task_create"),
    path("task/<uuid:pk>/", ComplianceTaskDetailView.as_view(), name="task_detail"),
    path("task/<uuid:pk>/update/", ComplianceTaskUpdateView.as_view(), name="task_update"),
    path("task/<uuid:pk>/trash/", compliance_task_delete, name="compliance_task_delete"),

    path('assessment/', ComplianceAssessmentView.as_view(), name='compliance_assessment'),
    path("requirement/<uuid:requirement_id>/assessment/create/", ComplianceAssessmentCreateView.as_view(),
         name="assessment_create"),
    path("assessment/<uuid:pk>/update/", ComplianceAssessmentUpdateView.as_view(), name="assessment_update"),
    path("assessment/<uuid:pk>/delete/", compliance_assessment_delete, name="assessment_delete"),

    path('report/', ComplianceReportView.as_view(), name='compliance_report'),
    # Partner
    path("partner/add/", PartnerCreate.as_view(), name="partner_create"),
    path("partner/<uuid:pk>/", PartnerDetail.as_view(), name="partner_detail"),
    path("partner/<uuid:pk>/edit/", PartnerUpdate.as_view(), name="partner_update"),
    path("partner/<uuid:pk>/delete/", partner_delete, name="partner_delete"),
    path("partner/<uuid:pk>/approve/", approve_partner, name="partner_approve"),
    path("partner/<uuid:pk>/reject/", reject_partner, name="partner_reject"),
    path("partner/<uuid:pk>/review/", review_partner, name="partner_review"),
    path('partners/', PartnerDueDiligenceListView.as_view(), name='partner_due_diligence_list'),

    path('vendors/', VendorDueDiligenceListView.as_view(), name='vendor_due_diligence_list'),
    path("vendor/add/", VendorCreate.as_view(), name="vendor_create"),
    path("vendor/<uuid:pk>/", VendorDetail.as_view(), name="vendor_detail"),
    path("vendor/<uuid:pk>/edit/", VendorUpdate.as_view(), name="vendor_update"),
    path("vendor/<uuid:pk>/delete/", vendor_delete, name="vendor_delete"),
    path('compliance/report/pdf/', compliance_report_pdf, name='compliance_report_pdf'),

    path('documents/', ComplianceDocumentListView.as_view(), name='compliance_doc_list'),
    path('documents/<uuid:pk>/update/', ComplianceDocumentUpdateView.as_view(), name='compliance_doc_update'),
    path('documents/<uuid:pk>/delete/', compliance_doc_delete, name='compliance_doc_delete'),
    path('documents/<uuid:pk>/verify/', verify_document, name='verify_document'),
]
