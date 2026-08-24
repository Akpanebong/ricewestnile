import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from account.models import Profile


class ApprovalMixin(models.Model):
    approved_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_%(class)s")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    approved = models.BooleanField(default=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_by = models.ForeignKey(Profile, related_name="%(class)s_created", on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Document(TimeStampedModel):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="docs/")
    tag = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title


class SystemActivity(models.Model):
    actor = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    module = models.CharField(max_length=50)
    action = models.CharField(max_length=20)
    object_repr = models.CharField(max_length=255)
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(default=200)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.module}:{self.action} [{self.status_code}]"


RESOURCE_TYPES = (
    ("presentation", "Presentation"),
    ("report", "Report"),
    ("success_story", "Success Story"),
)


class Resource(models.Model):
    title = models.CharField(max_length=250)
    resource_type = models.CharField(max_length=25, choices=RESOURCE_TYPES)
    file = models.FileField(upload_to="resources/")
    downloads = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class CurrencyRate(models.Model):
    UGX = "UGX"
    USD = "USD"
    KES = "KES"
    NGN = "NGN"
    SSP = "SSP"

    base_currency = models.CharField(max_length=3, default=USD)
    quote_currency = models.CharField(max_length=3, default=UGX)
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    source = models.CharField(max_length=255, blank=True)
    fetched_at = models.DateTimeField(default=timezone.now)
    rate_date = models.DateField(default=timezone.localdate)
    is_manual = models.BooleanField(default=False)
    is_fallback = models.BooleanField(default=False)
    input_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="currency_rates_input",
    )

    class Meta:
        ordering = ("-fetched_at",)
        indexes = [
            models.Index(fields=["base_currency", "quote_currency", "-fetched_at"]),
            models.Index(fields=["base_currency", "quote_currency", "is_manual", "-rate_date"]),
        ]

    @classmethod
    def fallback_rate(cls):
        from decimal import Decimal

        return Decimal("3700.000000")

    def __str__(self):
        return f"1 {self.base_currency} = {self.rate} {self.quote_currency}"
