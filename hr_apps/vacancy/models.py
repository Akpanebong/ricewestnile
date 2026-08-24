import uuid
from django.utils import timezone
from django.db.models import Count, Case, When, Value, IntegerField
from django.conf import settings
from django.db import models

from account.models import Department, Unit


class RecruitmentRequest(models.Model):
    STATUS = [
        ("Pending", "Pending"),
        ("HRReviewed", "HR Reviewed"),
        ("EDApproved", "ED Approved"),
        ("Rejected", "Rejected"),
        ("Published", "Published"),
    ]

    title = models.CharField(max_length=200)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, blank=True, null=True,
                                   limit_choices_to=~models.Q(name="ED"))
    justification = models.TextField()

    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="recruitment_requests")
    hr_reviewed = models.BooleanField(default=False)
    ed_approved = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    attach_file = models.FileField(upload_to="recruitment_requests/", null=True, blank=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:60]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.unit})"

    class Meta:
        ordering = [
            Case(
                When(status="Pending", then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            ),
            "-created_at"
        ]


class JobOpening(models.Model):
    request = models.OneToOneField(RecruitmentRequest, on_delete=models.CASCADE, related_name="job_opening")
    description = models.TextField()
    department = models.CharField(max_length=50, blank=True, null=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    deadline = models.DateField(null=True, blank=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:60]
        super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        if not self.deadline:
            return None

        today = timezone.now().date()
        return max((self.deadline - today).days, 0)

    def auto_close_if_expired(self):
        if self.deadline and timezone.now().date() > self.deadline:
            self.is_active = False
            self.save(update_fields=["is_active"])

    def __str__(self):
        return self.request.title

    class Meta:
        ordering = ['-posted_at', 'deadline']


class Applicant(models.Model):
    STATUS = [
        ('Pending', 'Pending'),
        ('Interview', 'Interview'),
        ('Rejected', 'Rejected'),
        ('Hired', 'Hired')
    ]

    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name="applicants")
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    resume = models.FileField(upload_to='resumes/')
    status = models.CharField(max_length=20, choices=STATUS, default='Pending')
    interview_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    interview_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_applicants"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_sent_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.job}"
