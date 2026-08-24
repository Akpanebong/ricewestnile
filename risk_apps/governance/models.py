from django.db import models
from account.models import Profile
from core.models import TimeStampedModel, ApprovalMixin


class Policy(TimeStampedModel, ApprovalMixin):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("retired", "Retired"),
    ]
    APPROVAL_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    policy_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=120, blank=True)
    owner = models.CharField(max_length=255, null=True, blank=True)
    version = models.CharField(max_length=20, default="1.0")
    summary = models.TextField()
    effective_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default="pending")

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.policy_id} - {self.title}"


class Control(TimeStampedModel, ApprovalMixin):
    EFFECTIVENESS_CHOICES = [
        ("effective", "Effective"),
        ("needs_improvement", "Needs Improvement"),
        ("ineffective", "Ineffective"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("active", "Active"),
        ("testing", "Testing"),
        ("inactive", "Inactive"),
    ]

    control_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=255)
    policy = models.ForeignKey(Policy, on_delete=models.SET_NULL, null=True, blank=True, related_name="controls")
    owner = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    control_type = models.CharField(max_length=100, default="preventive")
    automation_level = models.CharField(max_length=100, default="manual")
    frequency = models.CharField(max_length=100, default="quarterly")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    effectiveness = models.CharField(max_length=30, choices=EFFECTIVENESS_CHOICES, default="effective")
    next_test_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.control_id} - {self.title}"


class DecisionRecord(TimeStampedModel, ApprovalMixin):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("implemented", "Implemented"),
    ]

    title = models.CharField(max_length=255)
    meeting_date = models.DateField()
    resolution = models.TextField()
    vote_summary = models.CharField(max_length=255, blank=True)
    version = models.CharField(max_length=20, default="1.0")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    owner = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["-meeting_date", "title"]

    def __str__(self):
        return self.title


class StakeholderEngagement(TimeStampedModel):
    CHANNEL_CHOICES = [
        ("feedback_form", "Feedback Form"),
        ("survey", "Survey"),
        ("dialogue", "Dialogue"),
        ("community_meeting", "Community Meeting"),
    ]
    STATUS_CHOICES = [
        ("received", "Received"),
        ("reviewed", "Reviewed"),
        ("actioned", "Actioned"),
        ("closed", "Closed"),
    ]

    stakeholder_name = models.CharField(max_length=255)
    source_area = models.CharField(max_length=120, blank=True)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default="feedback_form")
    subject = models.CharField(max_length=255)
    feedback = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="received")
    assigned_to = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stakeholder_engagements",
    )
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stakeholder_name} - {self.subject}"
