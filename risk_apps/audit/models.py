import uuid
from django.db import models
from account.models import Profile
from core.models import TimeStampedModel, ApprovalMixin
from risk_apps.risk.models import Risk


class AuditLog(TimeStampedModel, ApprovalMixin):
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("fieldwork", "Fieldwork"),
        ("reported", "Reported"),
        ("closed", "Closed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    scope = models.TextField(blank=True)
    audit_type = models.CharField(max_length=255, choices=[("internal", "Internal"), ("external", "External")], default="internal")
    lead_auditor = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_audits")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.title


class AuditFinding(TimeStampedModel):
    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("moderate", "Moderate"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("accepted", "Accepted"),
        ("closed", "Closed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.ForeignKey(AuditLog, on_delete=models.CASCADE, related_name="findings")
    title = models.CharField(max_length=255)
    issue = models.TextField()
    recommendation = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="moderate")
    owner = models.CharField(max_length=255, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="open")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class AuditEvidence(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit = models.ForeignKey(AuditLog, on_delete=models.CASCADE, related_name="evidence")
    title = models.CharField(max_length=255)
    evidence_type = models.CharField(max_length=100, default="document")
    document_tag = models.CharField(max_length=120, blank=True)
    reference_code = models.CharField(max_length=120, blank=True)
    uploaded_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_evidence")
    is_finance_reconciled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ExternalAuditEngagement(TimeStampedModel, ApprovalMixin):
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("reported", "Reported"),
        ("closed", "Closed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit_log = models.OneToOneField(AuditLog, on_delete=models.CASCADE, related_name="external_details")
    title = models.CharField(max_length=255)
    audit_firm = models.CharField(max_length=255)
    scope = models.TextField(blank=True)
    shared_data_scope = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="planned")
    donor_report_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.title} - {self.audit_firm}"


class ExternalAuditFinding(TimeStampedModel):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("closed", "Closed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(ExternalAuditEngagement, on_delete=models.CASCADE, related_name="findings")
    related_internal_finding = models.ForeignKey(AuditFinding, on_delete=models.SET_NULL, null=True,
                                                 blank=True,related_name="external_links",)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="external_audit_findings",)
    title = models.CharField(max_length=255)
    recommendation = models.TextField()
    mapped_reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
