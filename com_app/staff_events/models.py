import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def validate_pdf(value):
    extension = os.path.splitext(value.name)[1].lower()
    if extension != ".pdf":
        raise ValidationError("Meeting minutes must be a PDF file.")
    content_type = getattr(value, "content_type", "")
    if content_type and content_type != "application/pdf":
        raise ValidationError("The uploaded file must have PDF content.")


class StaffEvent(models.Model):
    class EventType(models.TextChoices):
        CUSTOM = "custom", "Staff event"
        MONTHLY_MEETING = "monthly_meeting", "Staff monthly meeting"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    event_type = models.CharField(max_length=30, choices=EventType.choices, default=EventType.CUSTOM)
    meeting_month = models.DateField(null=True, blank=True, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_events_created",
    )
    minutes = models.FileField(upload_to="staff_event_minutes/%Y/%m/", blank=True, null=True, validators=[validate_pdf])
    minutes_uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("starts_at", "title")
        indexes = [models.Index(fields=("event_type", "starts_at"))]

    def clean(self):
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The event end must be after its start."})
        if self.event_type == self.EventType.MONTHLY_MEETING and not self.meeting_month:
            raise ValidationError({"meeting_month": "Monthly meetings require a meeting month."})

    def save(self, *args, **kwargs):
        if self.minutes and not self.minutes_uploaded_at:
            self.minutes_uploaded_at = timezone.now()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({timezone.localtime(self.starts_at):%Y-%m-%d})"


class StaffEventInvitation(models.Model):
    class Kind(models.TextChoices):
        CREATED = "created", "Event invitation"
        REMINDER = "reminder", "Reminder invitation"

    event = models.ForeignKey(StaffEvent, on_delete=models.CASCADE, related_name="invitations")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_event_invitations")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    sent_at = models.DateTimeField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "recipient", "kind"), name="unique_staff_event_invitation")
        ]
        indexes = [models.Index(fields=("event", "kind", "email_sent"))]

    def __str__(self):
        return f"{self.event} -> {self.recipient} ({self.kind})"
