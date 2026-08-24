import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from account.models import Profile
from .managers import NotificationManager


class Notification(TimeStampedModel):

    class Category(models.TextChoices):
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"
    class Source(models.TextChoices):
        CORE = "core", "Core"
        HR = "hr", "Human Resource"
        PROCUREMENT = "procurement", "Procurement"
        COMMUNICATION = "communication", "Communication"
        MNE = "mne", "Monitoring & Evaluation"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,)
    slug = models.SlugField(unique=True, editable=False, blank=True,)
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.INFO, db_index=True)
    source_app = models.CharField(max_length=30, choices=Source.choices, default=Source.CORE, db_index=True,)
    action_url = models.CharField(max_length=500, blank=True,)
    attachment = models.FileField(upload_to="notifications/",blank=True,null=True,)

    created_by = models.ForeignKey(Profile,null=True,blank=True,on_delete=models.SET_NULL,related_name="notifications_created",
                                   )
    is_deleted = models.BooleanField(default=False)
    objects = NotificationManager()

    class Meta:

        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["source_app"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_deleted"]),
        ]

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = uuid.uuid4().hex[:24]

        super().save(*args, **kwargs)

    def get_absolute_url(self):

        return reverse(
            "notifications:detail",
            kwargs={"pk": self.pk},
        )

    # @classmethod
    # def recipient_model(cls):
    #     return NotificationRecipient

    def __str__(self):
        return self.title


class NotificationRecipient(TimeStampedModel):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="recipients",)
    recipient = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="notifications",)
    is_read = models.BooleanField(default=False, db_index=True,)
    read_at = models.DateTimeField(null=True,blank=True,)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True,)
    is_archived = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:

        ordering = [
            "is_read",
            "-created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "notification",
                    "recipient",
                ],
                name="unique_notification_recipient",
            )
        ]

        indexes = [

            models.Index(
                fields=[
                    "recipient",
                    "is_read",
                ]
            ),

            models.Index(
                fields=[
                    "recipient",
                    "is_deleted",
                ]
            ),

            models.Index(
                fields=[
                    "notification",
                ]
            ),

        ]

    @property
    def badge_class(self):
        return {
            "info": "primary",
            "success": "success",
            "warning": "warning",
            "error": "danger",
            "critical": "dark",
        }.get(self.notification.category, "secondary")

    @property
    def title(self):
        return self.notification.title

    @property
    def message(self):
        return self.notification.message

    @property
    def attachment(self):
        return self.notification.attachment

    @property
    def created_by(self):
        return self.notification.created_by

    @property
    def created(self):
        return self.notification.created_at

    def mark_as_read(self):

        if self.is_read:
            return

        self.is_read = True
        self.read_at = timezone.now()

        self.save(
            update_fields=[
                "is_read",
                "read_at",
            ]
        )

    def mark_email_sent(self):

        if self.email_sent:
            return

        self.email_sent = True

        self.email_sent_at = timezone.now()

        self.save(
            update_fields=[
                "email_sent",
                "email_sent_at",
            ]
        )

    def archive(self):

        if self.is_archived:
            return

        self.is_archived = True

        self.save(update_fields=["is_archived"])

    def soft_delete(self):

        if self.is_deleted:
            return

        self.is_deleted = True

        self.save(update_fields=["is_deleted"])

    def __str__(self):

        return f"{self.notification.title} -> {self.recipient}"