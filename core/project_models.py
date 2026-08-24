import uuid
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
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
    program_area = models.ForeignKey(CoreProgram, on_delete=models.SET_NULL, null=True, blank=True)
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
