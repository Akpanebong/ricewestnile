import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.project_models import Project

PROGRAM_AREA = (
    ("ARUA", "Arua Program Area"),
    ("MOYO", "Moyo Program Area"),
)

STATUS_CHOICES = [
    ("Active", "Active"),
    ("On Leave", "On Leave"),
    ("Exit", "Exit"),
    ("Suspended", "Suspended"),
    ("Probation", "Probation"),
]

# Kept as a plain literal (not imported from core.models.CurrencyRate) to
# avoid a circular import — core/models.py already imports from account.models.
DISPLAY_CURRENCY_CHOICES = [
    ("UGX", "Ugandan Shilling"),
    ("KES", "Kenyan Shilling"),
    ("NGN", "Nigerian Naira"),
    ("SSP", "South Sudanese Pound"),
    ("USD", "US Dollar"),
]

PROFILE_TYPE = [
    ("Staff", "Staff"),
    ("Volunteer", "Volunteer"),
    ("Intern", "Intern"),
    ("Community Structure", "Community Structure"),
]


class ProgramArea(models.Model):
    """
    A manageable replacement for the old hardcoded PROGRAM_AREA choices on
    Profile — that tuple is still used as-is by the unrelated Presentation
    model in com_app.communication, so it's left alone; only Profile's own
    program_area needed a real place to add new values from.
    """
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Program Area"
        verbose_name_plural = "Program Areas"

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    head = models.ForeignKey("Profile", on_delete=models.SET_NULL, null=True, blank=True,
                             verbose_name="Dept Head", related_name="headed_departments",)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Unit(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=120)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)
    head = models.ForeignKey("Profile", on_delete=models.SET_NULL, null=True, blank=True,
                             verbose_name="Unit Head", related_name="headed_units",)

    class Meta:
        unique_together = ("department", "name")
        ordering = ("department__name", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.department} - {self.name}"


class Profile(AbstractUser):
    program_area = models.ForeignKey(ProgramArea, on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    profile_type = models.CharField(choices=PROFILE_TYPE, max_length=255, default="Staff", null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    title = models.CharField(max_length=120, blank=True)
    designation = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)
    signature = models.FileField(upload_to="Signature", blank=True, null=True)
    device_hash = models.CharField(max_length=225, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Probation", db_index=True)
    probation_starts = models.DateField(null=True, blank=True)
    probation_ends = models.DateField(null=True, blank=True)
    is_CMT = models.BooleanField(default=False)
    can_review = models.BooleanField(default=False)
    display_currency = models.CharField(
        max_length=3,
        choices=DISPLAY_CURRENCY_CHOICES,
        default="UGX",
        help_text="Preferred currency for viewing monetary amounts across the system.",
    )

    class Meta:
        verbose_name = "Profile"
        ordering = ("first_name", "last_name", "username")
        permissions = [
            ("can_edit_records", "Can edit, update, and delete records through temporary Edit access"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]

        super().save(*args, **kwargs)

    # def save(self, *args, **kwargs):
    #     creating = self._state.adding
    #     if not self.slug:
    #         self.slug = uuid.uuid4().hex[:10]
    #     super().save(*args, **kwargs)
    #
    #     if self.program_area:
    #         group, _ = Group.objects.get_or_create(name=self.program_area)
    #         self.groups.add(group)
    #     if self.department and self.can_review:
    #         group, _ = Group.objects.get_or_create(name=self.department.name)
    #         self.groups.add(group)
    #         if creating and not self.department.head:
    #             self.department.head = self
    #             self.department.save(update_fields=["head"])
    #     if self.unit:
    #         unit_group, _ = Group.objects.get_or_create(name=f"{self.unit.name}")
    #         self.groups.add(unit_group)
    #     if self.project:
    #         project_group, _ = Group.objects.get_or_create(name=self.project.name)
    #         self.groups.add(project_group)
    #     if self.can_review:
    #         review_group, _ = Group.objects.get_or_create(name="REVIEW")
    #         self.groups.add(review_group)

    def __str__(self):
        return self.get_full_name() or self.username


class EditAccessGrant(models.Model):
    """A temporary grant attached to membership of the Edit group."""

    user = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="edit_access_grant")
    granted_by = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="edit_access_grants_issued",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-granted_at",)
        indexes = [models.Index(fields=("expires_at",))]

    def __str__(self):
        return f"Edit access for {self.user} until {timezone.localtime(self.expires_at):%Y-%m-%d %H:%M}"


class EditAccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    applicant = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="edit_access_requests")
    requested_minutes = models.PositiveIntegerField(default=30)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="edit_access_requests_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("applicant",),
                condition=models.Q(status="pending"),
                name="one_pending_edit_request_per_applicant",
            ),
        ]

    def __str__(self):
        return f"{self.applicant} - {self.get_status_display()} edit access request"


class ExitStepStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    DONE = "done", _("Done")
    FAILED = "failed", _("Failed")


class ExitStepType(models.TextChoices):
    CLEARANCE_FORM_SENT = "clearance_form_sent", _("Clearance form sent")
    CLEARANCE_FORM_SUBMITTED = "clearance_form_submitted", _("Clearance form submitted")
    HANDOVER_REPORT_SUBMITTED = "handover_report_submitted", _("Handover report submitted")
    EXIT_MEETING_DONE = "exit_meeting_done", _("Exit meeting with HR")
    HR_REPORT_SUBMITTED_TO_CMT = "hr_report_submitted_to_cmt", _("HR report submitted to CMT")
    STAFF_DUES_PAID = "staff_dues_paid", _("Staff dues paid")

    @classmethod
    def ordered(cls):
        return [
            cls.CLEARANCE_FORM_SENT,
            cls.CLEARANCE_FORM_SUBMITTED,
            cls.HANDOVER_REPORT_SUBMITTED,
            cls.EXIT_MEETING_DONE,
            cls.HR_REPORT_SUBMITTED_TO_CMT,
            cls.STAFF_DUES_PAID,
        ]


class ExitProcess(models.Model):
    staff = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exit_process")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_exit_processes",
    )

    @property
    def completion_percent(self):
        total = len(ExitStepType.ordered())
        done = self.steps.filter(status=ExitStepStatus.DONE).count()
        return int(round((done / total) * 100)) if total else 0

    def ensure_steps(self):
        ordered = ExitStepType.ordered()
        existing = set(self.steps.values_list("step_type", flat=True))
        ExitProcessStep.objects.bulk_create(
            [
                ExitProcessStep(process=self, step_type=step, step_order=ordered.index(step))
                for step in ordered
                if step not in existing
            ]
        )

    def __str__(self):
        return f"ExitProcess({self.staff})"


class ExitProcessStep(models.Model):
    process = models.ForeignKey(ExitProcess, on_delete=models.CASCADE, related_name="steps")
    step_type = models.CharField(max_length=64, choices=ExitStepType.choices)
    step_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    status = models.CharField(max_length=16, choices=ExitStepStatus.choices, default=ExitStepStatus.PENDING)
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_exit_steps",
    )
    notes = models.TextField(blank=True)
    attachment = models.FileField(upload_to="exit_flow/", blank=True, null=True)

    class Meta:
        unique_together = (("process", "step_type"),)
        ordering = ["step_order", "id"]

    def mark(self, *, status, user=None, notes=None):
        self.status = status
        self.updated_at = timezone.now()
        if user is not None:
            self.updated_by = user
        if notes is not None:
            self.notes = notes
        self.save()

    def __str__(self):
        return f"{self.process.staff} | {self.step_type}"
