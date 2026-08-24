import uuid

from django.conf import settings
from django.db import models
from django.shortcuts import get_object_or_404
from django.views import View
from datetime import date
from account.models import Profile
from core.models import TimeStampedModel, ApprovalMixin


class ComplianceFramework(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ComplianceRequirement(models.Model):
    LEVEL_CHOICES = [
        ("program", "Program"),
        ("project", "Project"),
        ("partner", "Partner"),
        ("vendor", "Vendor"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, blank=True)
    framework = models.ForeignKey(ComplianceFramework, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    level = models.CharField(max_length=50, choices=LEVEL_CHOICES)
    evidence_required = models.TextField()
    frequency = models.CharField(max_length=100, blank=True, default="monthly")
    owner = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class ComplianceTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("warning", "Warning"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(ComplianceRequirement, on_delete=models.CASCADE, related_name="tasks")
    due_date = models.DateField()
    responsible = models.CharField(max_length=255)
    responsible_user = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_tasks",
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    progress = models.PositiveSmallIntegerField(default=0)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")

    def __str__(self):
        return f"{self.requirement.title} - {self.status}"

    def save(self, *args, **kwargs):
        if isinstance(self.due_date, str):
            from datetime import datetime
            self.due_date = datetime.strptime(self.due_date, "%Y-%m-%d").date()

        if self.due_date < date.today() and self.status != "completed":
            self.status = "overdue"

        super().save(*args, **kwargs)


class ComplianceDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(ComplianceRequirement, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="compliance_docs/")
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    verified_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class ComplianceAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(ComplianceRequirement, on_delete=models.CASCADE)
    score = models.IntegerField()
    gap = models.TextField(blank=True)
    recommendation = models.TextField(blank=True)
    assessed_at = models.DateTimeField(auto_now_add=True)

    def get_rating_display(self):
        if self.score >= 80:
            return "Compliant", "success"
        elif self.score >= 50:
            return ("Partial", "warning")
        return ("Non-Compliant", "danger")


class PartnerDueDiligence(TimeStampedModel, ApprovalMixin):
    RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    partner_name = models.CharField(max_length=255)
    governance_score = models.PositiveSmallIntegerField(default=0)
    financial_capacity_score = models.PositiveSmallIntegerField(default=0)
    compliance_score = models.PositiveSmallIntegerField(default=0)
    risk_rating = models.CharField(max_length=20, choices=RISK_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    donor_alignment_notes = models.TextField(blank=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ["partner_name"]

    def __str__(self):
        return self.partner_name


class VendorDueDiligence(TimeStampedModel):
    RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    PERFORMANCE_CHOICES = [
        ("active", "Active"),
        ("watch", "Watch"),
        ("critical", "Critical"),
        ("due_for_renewal", "Due for Renewal"),
        ("terminated", "Terminated"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor_name = models.CharField(max_length=255)
    service_category = models.CharField(max_length=120)
    legal_compliance_status = models.CharField(max_length=120, default="pending review")
    financial_stability_score = models.PositiveSmallIntegerField(default=0)
    ethical_screening_passed = models.BooleanField(default=False)
    risk_rating = models.CharField(max_length=20, choices=RISK_CHOICES, default="medium")
    performance_status = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, default="active")
    contract_ready = models.BooleanField(default=False)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ["vendor_name"]

    def __str__(self):
        return self.vendor_name
