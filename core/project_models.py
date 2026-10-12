import uuid
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.core.validators import FileExtensionValidator
from django.utils import timezone
# from django.contrib.auth import get_user_model
# User = get_user_model()


class Location(models.Model):
    district = models.CharField(max_length=200)
    settlement = models.CharField(max_length=200, blank=True)
    sub_county = models.CharField(max_length=200, blank=True)

    def __str__(self):
        parts = [self.district]
        if self.sub_county: parts.append(self.sub_county)
        if self.settlement: parts.append(self.settlement)
        return " / ".join(parts)


class CoreProgram(models.Model):
    name = models.CharField(max_length=200)
    create_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"


class Project(models.Model):
    code = models.CharField(max_length=50, blank=True)
    projected_reach = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=120, unique=True)
    donor = models.CharField(max_length=255, blank=True)
    unit = models.ForeignKey('account.Unit', on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    project_head = models.ForeignKey('account.Profile', on_delete=models.SET_NULL, null=True, blank=True, related_name="project_head_projects")
    project_accountant = models.ForeignKey('account.Profile', on_delete=models.SET_NULL, null=True, blank=True, related_name="accountant_projects")
    project_officer = models.ForeignKey('account.Profile', on_delete=models.SET_NULL, null=True, blank=True, related_name="officer_projects")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    duration_days = models.CharField(max_length=300, null=True, blank=True)
    program_area = models.ForeignKey(
        "account.ProgramArea",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)

    slug = models.SlugField(null=True, blank=True, editable=False, unique=True)

    class Meta:
        ordering = ("name",)

    @property
    def duration(self):
        if not self.start_date or not self.end_date:
            return ""
        months = (self.end_date.year - self.start_date.year) * 12 + self.end_date.month - self.start_date.month
        if self.end_date.day < self.start_date.day:
            months -= 1
        years, remaining_months = divmod(max(months, 0), 12)
        return f"{years} years, {remaining_months} months"

    @property
    def department(self):
        return self.unit.department if self.unit_id else None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:10]
        if self.start_date and self.end_date:
            rd = relativedelta(self.end_date, self.start_date)
            self.duration_days = f"{rd.years}y {rd.months}m {rd.days}d"
        else:
            self.duration_days = None

        super().save(*args, **kwargs)

        for person in [self.project_head, self.project_accountant, self.project_officer]:
            if person:
                group, _ = Group.objects.get_or_create(name=self.name)
                person.groups.add(group)

    def __str__(self):
        return self.name

    def _schedule_documents(self):
        return getattr(self, "_prefetched_schedule_documents", self.documents.all())

    def _latest_workplan(self):
        workplans = [
            document for document in self._schedule_documents()
            if document.document_type == ProjectDocument.WORKPLAN
        ]
        return max(workplans, key=lambda document: document.uploaded_at) if workplans else None

    @property
    def planned_activity_count(self):
        workplan = self._latest_workplan()
        if not workplan:
            return None
        activities = [activity for activity in getattr(workplan, "_prefetched_activities", workplan.activities.all()) if activity.confirmed]
        return len(activities)

    @property
    def activity_report_count(self):
        workplan = self._latest_workplan()
        if not workplan:
            return 0
        activities = [
            activity for activity in getattr(workplan, "_prefetched_activities", workplan.activities.all())
            if activity.confirmed
        ]
        activity_ids = {activity.pk for activity in activities}
        return sum(
            document.document_type == ProjectDocument.REPORT
            and document.report_type == ProjectDocument.ACTIVITY_REPORT
            and document.activity_id in activity_ids
            for document in self._schedule_documents()
        )

    @property
    def schedule_status(self):
        workplan = self._latest_workplan()
        if not workplan:
            return "Not Started"
        activities = [activity for activity in getattr(workplan, "_prefetched_activities", workplan.activities.all()) if activity.confirmed]
        statuses = [activity.status for activity in activities]
        if not statuses:
            return "Not Started"
        if statuses and all(status == ProjectActivity.ON_SCHEDULE for status in statuses):
            return "On Schedule"
        if any(status == ProjectActivity.IN_PROGRESS for status in statuses):
            return "In Progress"
        return "Off Schedule"


def project_document_upload_to(instance, filename):
    return f"projects/{instance.project_id}/{instance.document_type}/{filename}"


def project_submission_upload_to(instance, filename):
    return f"projects/{instance.project_id}/submissions/{instance.document_type}/{filename}"


def activity_concept_note_upload_to(instance, filename):
    return f"projects/{instance.activity.workplan.project_id}/concept-notes/{instance.activity_id}/{filename}"


class ProjectDocument(models.Model):
    WORKPLAN = "workplan"
    REPORT = "report"
    DOCUMENT_TYPES = ((WORKPLAN, "Workplan"), (REPORT, "Report"))

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    WORKPLAN_PERIODS = (
        (MONTHLY, "Monthly"),
        (QUARTERLY, "Quarterly"),
        (ANNUAL, "Annual"),
    )

    ACTIVITY_REPORT = "activity_report"
    MONTHLY_REPORT = "monthly_report"
    QUARTERLY_REPORT = "quarterly_report"
    ANNUAL_REPORT = "annual_report"
    REPORT_TYPES = (
        (ACTIVITY_REPORT, "Activity Report"),
        (MONTHLY_REPORT, "Monthly Report"),
        (QUARTERLY_REPORT, "Quarterly Report"),
        (ANNUAL_REPORT, "Annual Report"),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(
        upload_to=project_document_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"])],
    )
    workplan_period = models.CharField(max_length=20, choices=WORKPLAN_PERIODS, blank=True)
    activities_count = models.PositiveIntegerField(null=True, blank=True)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES, blank=True)
    activity = models.ForeignKey("ProjectActivity", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="uploaded_project_documents")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def clean(self):
        if self.activity_id and self.project_id:
            activity_project_id = self.activity.workplan.project_id
            if activity_project_id != self.project_id:
                raise ValidationError({"activity": "The selected activity belongs to another project."})

    def __str__(self):
        label = self.get_workplan_period_display() if self.document_type == self.WORKPLAN else self.get_report_type_display()
        return f"{self.project} - {label}"


class ProjectActivity(models.Model):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    ON_SCHEDULE = "On Schedule"
    OFF_SCHEDULE = "Off Schedule"

    workplan = models.ForeignKey(ProjectDocument, on_delete=models.CASCADE, related_name="activities")
    code = models.CharField(max_length=80, blank=True)
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    confirmed = models.BooleanField(default=False)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="confirmed_project_activities")
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("start_date", "name")

    @property
    def status(self):
        today = timezone.localdate()
        reports = self.reports.filter(
            document_type=ProjectDocument.REPORT,
            report_type=ProjectDocument.ACTIVITY_REPORT,
        )
        if reports.exists():
            report_dates = [report.uploaded_at.date() for report in reports]
            if any(self.start_date <= report_date <= self.end_date for report_date in report_dates):
                return self.ON_SCHEDULE
            return self.OFF_SCHEDULE
        if self.start_date <= today <= self.end_date:
            return self.IN_PROGRESS
        if today < self.start_date:
            return self.NOT_STARTED
        return self.OFF_SCHEDULE

    def __str__(self):
        return self.name


class ActivityConceptNote(models.Model):
    ONLINE = "online"
    UPLOADED = "uploaded"
    SOURCE_CHOICES = ((ONLINE, "Completed online"), (UPLOADED, "Uploaded completed form"))

    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (SUBMITTED, "Pending Project Head Review"),
        (REVIEWED, "Pending Program Head Approval"),
        (APPROVED, "Approved"),
        (REJECTED, "Returned for Revision"),
    )

    activity = models.OneToOneField(ProjectActivity, on_delete=models.CASCADE, related_name="concept_note")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=ONLINE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    uploaded_file = models.FileField(upload_to=activity_concept_note_upload_to, blank=True, null=True)

    project_name = models.CharField(max_length=255, blank=True)
    activity_code = models.CharField(max_length=80, blank=True)
    activity_name = models.CharField(max_length=255, blank=True)
    core_program_area = models.CharField(max_length=255, blank=True)
    outcome_result_area = models.TextField(blank=True)
    activity_start_date = models.DateField(null=True, blank=True)
    activity_end_date = models.DateField(null=True, blank=True)
    activity_venue = models.CharField(max_length=255, blank=True)
    concept_date = models.DateField(null=True, blank=True)

    background = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    methodology = models.TextField(blank=True)
    expected_outputs = models.TextField(blank=True)
    inputs_required = models.TextField(blank=True)
    cross_cutting_themes = models.TextField(blank=True)
    safeguarding_integration = models.TextField(blank=True)
    aap_integration = models.TextField(blank=True)
    tasks = models.JSONField(default=list, blank=True)
    budget_lines = models.JSONField(default=list, blank=True)
    total_amount_in_words = models.TextField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="concept_notes_created")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="concept_notes_submitted")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="concept_notes_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="concept_notes_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def project(self):
        return self.activity.workplan.project

    @property
    def project_head(self):
        return self.project.project_head

    @property
    def program_head(self):
        project = self.project
        return project.unit.department.head if project.unit_id and project.unit.department_id else None

    def __str__(self):
        return f"Concept note - {self.activity}"


class StakeholderUpdate(models.Model):
    CATEGORY_CHOICES = (
        ("government", "Government"),
        ("donor", "Donor"),
        ("community", "Community"),
        ("cso", "CSO"),
        ("private_sector", "Private Sector"),
        ("other", "Other"),
    )
    ENGAGEMENT_CHOICES = (
        ("meeting", "Meeting"),
        ("call", "Call"),
        ("email", "Email"),
        ("visit", "Visit"),
        ("other", "Other"),
    )
    FOLLOW_UP_CHOICES = (
        ("pending", "Pending"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="stakeholder_updates")
    date = models.DateField()
    stakeholder_name = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    designation = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=255, blank=True, verbose_name="Email / Phone")
    engagement_method = models.CharField(max_length=30, choices=ENGAGEMENT_CHOICES)
    update_summary = models.TextField(verbose_name="Update / Discussion Summary")
    action_points = models.TextField(blank=True, verbose_name="Decisions / Action Points")
    responsible_person = models.CharField(max_length=255, blank=True)
    deadline = models.DateField(null=True, blank=True)
    follow_up_status = models.CharField(max_length=20, choices=FOLLOW_UP_CHOICES, default="pending")
    remarks = models.TextField(blank=True, verbose_name="Remarks / Notes")
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="stakeholder_updates_entered")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-created_at")

    def __str__(self):
        return f"{self.project} - {self.stakeholder_name} - {self.date}"


class TeamMeeting(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="team_meetings")
    meeting_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    chairperson = models.CharField(max_length=255, blank=True)
    minute_taker = models.CharField(max_length=255, blank=True)
    participants_m_f = models.CharField(max_length=100, blank=True, verbose_name="Participants (M/F)")
    key_action_items = models.TextField(blank=True, verbose_name="Key Action Items")
    timeline = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    area_of_support = models.TextField(blank=True, verbose_name="Area of Support")
    person_responsible = models.CharField(max_length=255, blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="team_meetings_entered")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-meeting_date", "-start_time")

    def __str__(self):
        return f"{self.project} team meeting - {self.meeting_date}"


class ProjectSubmission(models.Model):
    NARRATIVE = "narrative"
    FINANCIAL = "financial"
    DOCUMENT_TYPES = (
        (NARRATIVE, "Narrative Report (PDF)"),
        (FINANCIAL, "Financial Report (Excel)"),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="submissions")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to=project_submission_upload_to)
    reporting_period = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="project_submissions_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def clean(self):
        super().clean()
        filename = (self.file.name if self.file else "").lower()
        if self.document_type == self.NARRATIVE and not filename.endswith(".pdf"):
            raise ValidationError({"file": "Narrative reports must be PDF files."})
        if self.document_type == self.FINANCIAL and not filename.endswith((".xls", ".xlsx")):
            raise ValidationError({"file": "Financial reports must be Excel files (.xls or .xlsx)."})

    def __str__(self):
        return f"{self.project} - {self.get_document_type_display()}"


class ProjectBudget(models.Model):
    FULL_YEAR = "FULL_YEAR"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"

    PERIOD_CHOICES = (
        (FULL_YEAR, "Full Year"),
        (Q1, "Quarter 1"),
        (Q2, "Quarter 2"),
        (Q3, "Quarter 3"),
        (Q4, "Quarter 4"),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="budgets")
    fiscal_year = models.CharField(max_length=128)
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default=FULL_YEAR)
    budget_amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year", "period")
        unique_together = ("project", "fiscal_year", "period")
        indexes = [models.Index(fields=["project", "fiscal_year", "period"])]

    def __str__(self):
        return f"{self.project} - {self.fiscal_year} - {self.get_period_display()}"

    def amount_used(self, exclude_plan=None):
        from django.apps import apps

        ProcurementPlan = apps.get_model("procureapp", "ProcurementPlan")
        queryset = ProcurementPlan.objects.filter(project=self.project, fiscal_year=self.fiscal_year)
        if self.period != self.FULL_YEAR:
            queryset = queryset.filter(budget_period=self.period)
        if exclude_plan and exclude_plan.pk:
            queryset = queryset.exclude(pk=exclude_plan.pk)
        return queryset.aggregate(total=Sum("total_amount"))["total"] or 0

    def actual_amount_used(self):
        from django.apps import apps

        PurchaseOrder = apps.get_model("procureapp", "PurchaseOrder")
        queryset = PurchaseOrder.objects.filter(
            sent=True,
            procurement_plan__project=self.project,
            procurement_plan__fiscal_year=self.fiscal_year,
        )
        if self.period != self.FULL_YEAR:
            queryset = queryset.filter(procurement_plan__budget_period=self.period)
        return queryset.aggregate(total=Sum("final_amount"))["total"] or 0

    def amount_remaining(self, exclude_plan=None):
        return self.budget_amount - self.amount_used(exclude_plan=exclude_plan)

    def actual_amount_remaining(self):
        return self.budget_amount - self.actual_amount_used()

    @classmethod
    def current_fiscal_year(cls):
        return str(timezone.now().date().year)
