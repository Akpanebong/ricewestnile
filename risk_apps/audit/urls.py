from django.urls import path

from .views import *


urlpatterns = [
    path("", AuditDashboardView.as_view(), name="audit_dashboard"),
    path("audits/", AuditLogListView.as_view(), name="audit_log_list"),
    # path("audits/", AuditLogListView.as_view(), name="audit_list"),
    path("audits/create/", AuditLogCreateView.as_view(), name="audit_create"),
    path("audits/<uuid:pk>/update/", AuditLogUpdateView.as_view(), name="audit_update"),
    path("audits/<uuid:pk>/delete/", audit_log_delete, name="audit_delete"),
    path("engagements/<uuid:pk>/detail/", AuditLogDetailView.as_view(), name="audit_log_detail"),
    path('audit/log/<uuid:pk>/approve/', approve_auditlog, name='auditlog_approve'),
    path('audit/log/<uuid:pk>/reject/', reject_auditlog, name='auditlog_reject'),

    path("findings/", AuditFindingListView.as_view(), name="audit_finding_list"),
    path("findings/<uuid:pk>/update/", AuditFindingUpdateView.as_view(), name="finding_update"),
    path("findings/<uuid:pk>/delete/", audit_finding_delete, name="finding_delete"),

    path("evidence/", AuditEvidenceListView.as_view(), name="audit_evidence_list"),
    path("evidence/<uuid:pk>/update/", AuditEvidenceUpdateView.as_view(), name="evidence_update"),
    path("evidence/<uuid:pk>/delete/", audit_evidence_delete, name="evidence_delete"),

    path("external/", ExternalAuditDashboardView.as_view(), name="external_audit_dashboard"),
    path("external/engagements/", ExternalAuditEngagementListView.as_view(), name="external_audit_engagement_list"),
    path("external-audit/<uuid:pk>/", ExternalAuditEngagementDetailView.as_view(), name="external_audit_detail"),
    path("external/engagements/create/", ExternalAuditCreateView.as_view(), name="external_audit_create"),
    path("external/engagements/<uuid:pk>/edit/", ExternalAuditUpdateView.as_view(), name="external_audit_edit"),
    path('audit/external/<uuid:pk>/approve/', approve_external_audit, name='external_audit_approve'),
    path('audit/external/<uuid:pk>/reject/', reject_external_audit, name='external_audit_reject'),
    path('audit/external/<uuid:pk>/delete/', ext_audit_delete, name='external_audit_delete'),

    path("external/findings/", ExternalAuditFindingListView.as_view(), name="external_audit_finding_list"),
]



