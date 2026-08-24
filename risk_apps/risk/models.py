import uuid
from django.db import models, transaction
from django.db.models import Max
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from core.models import TimeStampedModel
from risk_apps.risk.services.risk_engine import compute_risk


class RiskCategory(models.Model):
    name = models.CharField(max_length=100)
    risk_owner = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    code = models.CharField(max_length=5, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)

    def generate_code(self):
        name = self.name.upper().replace(" ", "")
        for length in range(1, len(name) + 1):
            prefix = f"{name[:length]}R"
            if not RiskCategory.objects.filter(code=prefix).exists():
                return prefix
        return name[:3]

    def __str__(self):
        return f"{self.name} - {self.code}"


# -------------------
# Likelihood & Impact
# -------------------
class Likelihood(models.Model):
    rating = models.PositiveSmallIntegerField(unique=True)
    descriptor = models.CharField(max_length=50)
    definition = models.TextField()

    class Meta:
        ordering = ["rating"]
        constraints = [
            models.CheckConstraint(check=models.Q(rating__gte=1, rating__lte=5), name="likelihood_range")
        ]

    def __str__(self):
        return f"{self.rating} - {self.descriptor}"


class Impact(models.Model):
    rating = models.PositiveSmallIntegerField(unique=True)
    descriptor = models.CharField(max_length=50)
    definition = models.TextField()

    class Meta:
        ordering = ["rating"]
        constraints = [
            models.CheckConstraint(check=models.Q(rating__gte=1, rating__lte=5), name="impact_range")
        ]

    def __str__(self):
        return f"{self.rating} - {self.descriptor}"


# -------------------
# Risk
# -------------------
class Risk(TimeStampedModel):
    STATUS_CHOICES = [
        ("IDENTIFIED", "Identified"),
        ("ACCESSED", "Accessed"),
        ("PLANNED", "Planned"),
        ("IN PROGRESS", "In Progress"),
        ("CONTROLLED", "Controlled"),
        ("RESOLVED", "Resolved"),
        ("ESCALATED", "Escalated")
    ]
    LEVEL_CHOICES = [
        ("LOW", "Low"),
        ("MODERATE", "Moderate"),
        ("SUBSTANTIAL", "Substantial"),
        ("HIGH", "High"),
        ("VERY HIGH", "Very High")
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    risk_id = models.CharField(max_length=10, unique=True, blank=True)
    event = models.TextField()
    cause = models.TextField()
    category = models.ForeignKey(RiskCategory, on_delete=models.SET_NULL, null=True, related_name="risks")
    likelihood = models.ForeignKey(Likelihood, on_delete=models.SET_NULL, null=True)
    impact = models.ForeignKey(Impact, on_delete=models.SET_NULL, null=True)
    risk_score = models.PositiveSmallIntegerField(editable=False)
    risk_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, blank=True)
    risk_owner = models.CharField(max_length=100)
    risk_type = models.CharField(max_length=100, blank=True, null=True)
    mitigation_plan = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="IDENTIFIED")
    date_identified = models.DateField(blank=True, null=True)
    valid_from = models.DateField()
    valid_to = models.DateField()
    next_review_date = models.DateField(blank=True, null=True)
    ai_used = models.BooleanField(default=False)
    ai_confidence = models.FloatField(null=True, blank=True)
    program = models.CharField(max_length=255, blank=True, null=True)  # Project/Program level
    source = models.CharField(max_length=50, blank=True, null=True)  # Staff/Community/etc.
    business_unit = models.CharField(max_length=150, blank=True, null=True)
    is_fraud_related = models.BooleanField(default=False)
    esg_area = models.CharField(max_length=120, blank=True, null=True)
    continuity_dependency = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["risk_level"]),
            models.Index(fields=["status"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.event[:50]}..."

    def clean(self):
        if self.valid_to and self.valid_from:
            if self.valid_to < self.valid_from:
                raise ValidationError("Valid To cannot be before Valid From")
        if self.next_review_date and self.valid_to:
            if self.next_review_date > self.valid_to:
                raise ValidationError("Review date must be within validity period")

    def save(self, *args, **kwargs):
        self.full_clean()

        score, level, explanation, ai_used = compute_risk(
            self.likelihood,
            self.impact,
            self.category
        )

        self.risk_score = score
        self.risk_level = level
        self.ai_used = ai_used
        self.ai_confidence = explanation.get("confidence") if explanation else None

        super().save(*args, **kwargs)


@receiver(pre_save, sender=Risk)
def set_risk_id(sender, instance, **kwargs):
    if instance.risk_id:
        return
    if not instance.category or not instance.category.code:
        raise ValueError("Category must have a valid code")
    prefix = instance.category.code
    with transaction.atomic():
        last = (
            Risk.objects.select_for_update()
                .filter(risk_id__startswith=prefix)
                .aggregate(max_id=Max("risk_id"))
        )["max_id"]
        last_number = int(last.replace(prefix, "")) if last else 0
        instance.risk_id = f"{prefix}{str(last_number + 1).zfill(3)}"


# -------------------
# Risk Treatment
# -------------------
class RiskTreatment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("overdue", "Overdue")
    ]
    risk = models.ForeignKey(Risk, related_name='treatments', on_delete=models.CASCADE)
    description = models.TextField()
    owner = models.CharField(max_length=255)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    due_date = models.DateField(null=True, blank=True)
    resources = models.TextField(blank=True, null=True)
    project_activity = models.CharField(max_length=255, blank=True, null=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    lessons_learned = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["due_date", "status"]

    def __str__(self):
        return f"{self.owner} - {self.get_status_display()}"


# -------------------
# Scenario
# -------------------
class Scenario(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    multiplier = models.FloatField(default=1.0)
    risks = models.ManyToManyField(Risk, related_name="scenarios")

    def __str__(self):
        return self.name


class RiskIncident(TimeStampedModel):
    INCIDENT_TYPES = [
        ("incident", "Incident"),
        ("near_miss", "Near Miss"),
        ("fraud", "Fraud"),
        ("breach", "Control Breach"),
        ("ethics", "Ethics Concern"),
    ]
    STATUS_CHOICES = [
        ("reported", "Reported"),
        ("triage", "Under Triage"),
        ("investigating", "Investigating"),
        ("contained", "Contained"),
        ("closed", "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    incident_type = models.CharField(max_length=30, choices=INCIDENT_TYPES, default="incident")
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents")
    description = models.TextField()
    reported_by = models.CharField(max_length=150, blank=True)
    business_unit = models.CharField(max_length=150, blank=True)
    event_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="reported")
    severity = models.CharField(max_length=20, choices=Risk.LEVEL_CHOICES, default="LOW")
    immediate_action = models.TextField(blank=True)
    investigation_notes = models.TextField(blank=True)
    confidential = models.BooleanField(default=False)

    class Meta:
        ordering = ["-event_date", "-created_at"]
        indexes = [
            models.Index(fields=["incident_type", "status"]),
            models.Index(fields=["severity"]),
        ]

    def __str__(self):
        return self.title


class KeyRiskIndicator(TimeStampedModel):
    STATUS_CHOICES = [
        ("normal", "Normal"),
        ("watch", "Watch"),
        ("breached", "Breached"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="kris")
    metric_owner = models.CharField(max_length=150)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    warning_threshold = models.DecimalField(max_digits=12, decimal_places=2)
    breach_threshold = models.DecimalField(max_digits=12, decimal_places=2)
    unit = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="normal")
    last_measured = models.DateField(null=True, blank=True)
    response_plan = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "name"]
        indexes = [models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        if self.current_value >= self.breach_threshold:
            self.status = "breached"
        elif self.current_value >= self.warning_threshold:
            self.status = "watch"
        else:
            self.status = "normal"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RiskControl(TimeStampedModel):
    CONTROL_TYPES = [
        ("preventive", "Preventive"),
        ("detective", "Detective"),
        ("corrective", "Corrective"),
        ("directive", "Directive"),
    ]
    EFFECTIVENESS_CHOICES = [
        ("strong", "Strong"),
        ("adequate", "Adequate"),
        ("needs_improvement", "Needs Improvement"),
        ("weak", "Weak"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="controls")
    control_type = models.CharField(max_length=30, choices=CONTROL_TYPES, default="preventive")
    owner = models.CharField(max_length=150)
    description = models.TextField()
    effectiveness = models.CharField(max_length=30, choices=EFFECTIVENESS_CHOICES, default="adequate")
    last_tested = models.DateField(null=True, blank=True)
    next_test_due = models.DateField(null=True, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["effectiveness"])]

    def __str__(self):
        return self.name


class BusinessContinuityPlan(TimeStampedModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("testing", "Testing"),
        ("active", "Active"),
        ("retired", "Retired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="continuity_plans")
    critical_process = models.CharField(max_length=255)
    recovery_owner = models.CharField(max_length=150)
    recovery_time_objective = models.CharField(max_length=120, blank=True)
    recovery_point_objective = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    last_tested = models.DateField(null=True, blank=True)
    next_test_due = models.DateField(null=True, blank=True)
    continuity_actions = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "next_test_due"]

    def __str__(self):
        return self.name


class ThirdPartyRisk(TimeStampedModel):
    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("conditional", "Conditional"),
        ("suspended", "Suspended"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    party_name = models.CharField(max_length=255)
    service_category = models.CharField(max_length=150)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="third_party_exposures")
    risk_rating = models.CharField(max_length=20, choices=Risk.LEVEL_CHOICES, default="LOW")
    compliance_status = models.CharField(max_length=120, blank=True)
    contract_owner = models.CharField(max_length=150, blank=True)
    due_diligence_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    mitigation_requirements = models.TextField(blank=True)

    class Meta:
        ordering = ["party_name"]
        indexes = [models.Index(fields=["risk_rating", "status"])]

    def __str__(self):
        return self.party_name


class EnvironmentalSocialRisk(TimeStampedModel):
    STATUS_CHOICES = [
        ("identified", "Identified"),
        ("monitoring", "Monitoring"),
        ("mitigating", "Mitigating"),
        ("resolved", "Resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="esg_records")
    esg_area = models.CharField(max_length=120)
    donor_standard = models.CharField(max_length=150, blank=True)
    affected_stakeholders = models.TextField(blank=True)
    rating = models.CharField(max_length=20, choices=Risk.LEVEL_CHOICES, default="LOW")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="identified")
    mitigation_plan = models.TextField(blank=True)
    next_review_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["status", "next_review_date"]
        indexes = [models.Index(fields=["rating", "status"])]

    def __str__(self):
        return self.title


class WhistleblowerCase(TimeStampedModel):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("screening", "Screening"),
        ("investigating", "Investigating"),
        ("substantiated", "Substantiated"),
        ("unsubstantiated", "Unsubstantiated"),
        ("closed", "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_reference = models.CharField(max_length=30, unique=True, blank=True)
    allegation = models.CharField(max_length=255)
    related_risk = models.ForeignKey(Risk, on_delete=models.SET_NULL, null=True, blank=True, related_name="whistleblower_cases")
    reporter_contact = models.CharField(max_length=255, blank=True)
    anonymous = models.BooleanField(default=True)
    reported_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="submitted")
    assigned_investigator = models.CharField(max_length=150, blank=True)
    summary = models.TextField(blank=True)
    outcome = models.TextField(blank=True)
    donor_report_required = models.BooleanField(default=False)

    class Meta:
        ordering = ["-reported_date", "-created_at"]
        indexes = [models.Index(fields=["status", "donor_report_required"])]

    def save(self, *args, **kwargs):
        if not self.case_reference:
            last = WhistleblowerCase.objects.aggregate(max_id=Max("case_reference"))["max_id"]
            number = int(last.replace("WB", "")) if last else 0
            self.case_reference = f"WB{number + 1:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.case_reference} - {self.allegation}"
