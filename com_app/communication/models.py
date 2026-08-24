from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.utils import timezone
from django.utils.text import slugify
import uuid, os
from django.core.exceptions import ValidationError

from account.models import Profile, PROGRAM_AREA


def validate_word_file(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.doc', '.docx']:
        raise ValidationError('Only Word (.doc, .docx) files are allowed.')


def validate_pptx_file(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.ppt', '.pptx']:
        raise ValidationError('Only PowerPoint (.ppt, .pptx) files are allowed.')


REPORT_TYPE_CHOICES = (
    ('MONTHLY', 'Monthly'),
    ('QUARTERLY', 'Quarterly'),
    ('BIANNUAL', 'Biannual'),
    ('ANNUAL', 'Annual'),
)

STATUS_CHOICES = (
    ('SUBMITTED','Submitted'),
    ('UNDER_REVIEW','Under review'),
    ('APPROVED','Approved'),
    ('RETURNED','Returned'),
)


class FocusArea(models.Model):
    PROGRAM_TYPE_CHOICES = (('CORE','Core'), ('CROSS','Cross-cutting'))
    # name = models.CharField(max_length=255)
    name = models.CharField(max_length=10, choices=PROGRAM_TYPE_CHOICES, default='CORE')
    slug = models.SlugField(blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:50]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SubGroup(models.Model):
    focus_area = models.ForeignKey(FocusArea, on_delete=models.CASCADE, related_name='subgroups')
    name = models.CharField(max_length=255, help_text='Example: Skills Development')
    leader = models.ForeignKey(Profile, null=True, blank=True, on_delete=models.SET_NULL, related_name='leading_groups')
    slug = models.SlugField(blank=True, null=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class MonthlyPresentation(models.Model):
    file = models.FileField(upload_to='presentations/', validators=[validate_pptx_file])
    program_area = models.CharField(choices=PROGRAM_AREA, max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    reply = models.TextField(null=True, blank=True)
    date_sent = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name='presentation_sent')
    received = models.BooleanField(default=False)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date_sent']

    def __str__(self):
        return f"Presentation {self.file.name} by {self.sent_by}"


class Report(models.Model):
    file = models.FileField(upload_to='reports/', validators=[validate_word_file])
    title = models.CharField(max_length=255, blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    focus_area = models.ForeignKey(FocusArea, on_delete=models.SET_NULL, null=True, blank=True)
    sub_group = models.ForeignKey(SubGroup, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField(blank=True)
    received = models.BooleanField(default=False)
    sent_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name='reports_sent')
    date_sent = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    reviewed_by = models.ForeignKey(Profile, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviews_done')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_sent']

    def __str__(self):
        return f"{self.report_type} report by {self.sent_by} on {self.date_sent.date()}"


class ReportComment(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"Comment by {self.author} on {self.report}"

