import uuid
from decimal import Decimal
from django.utils.text import slugify
from django.db import models
from django.conf import settings
from django.db.models import DecimalField, Sum, F, ExpressionWrapper, Value
from django.db.models.functions import Coalesce, Cast

from account.models import Department
from core.project_models import Project
from procurement.procureapp.models import PurchaseOrder

User = settings.AUTH_USER_MODEL


class ApprovalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    FINANCE_REVIEW = "finance_review", "Finance Review"
    ASSET_REVIEW = "assets_review", "Assets Review"
    OPERATIONS_REVIEW = "operations_review", "Operations Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class ApprovalMixin(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="%(class)s_created")
    status = models.CharField(max_length=30, choices=ApprovalStatus.choices, default="draft")
    checked_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_checked")
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_reviewed")
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_approved")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class CashRequisition(ApprovalMixin):
    procurement_requisition = models.ForeignKey(
        'procureapp.Requisition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cash_requisitions'
    )
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_requisitions')
    donor_code = models.CharField(max_length=100)
    to = models.CharField(max_length=255)
    purpose = models.TextField()
    date = models.DateField()
    reason_for_rejection = models.TextField(null=True, blank=True)
    amount_in_words = models.CharField(max_length=255, blank=True)
    attachment = models.FileField(upload_to='cash_requisitions/attachments/', blank=True, null=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{uuid.uuid4().hex[:200]}{self.donor_code}")
        return super(CashRequisition, self).save(*args, **kwargs)

    def total_amount(self):
        return sum(item.total_cost for item in self.items.all())

    def __str__(self):
        return f'{self.donor_code} - {self.purpose}'

    @staticmethod
    def get_total_amount(qs):
        return qs.aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        Cast(F("items__quantity"), DecimalField(max_digits=12, decimal_places=2)) *
                        F("items__unit_cost"),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )["total"]


class CashRequisitionItem(models.Model):
    requisition = models.ForeignKey(CashRequisition, related_name="items", on_delete=models.CASCADE)
    activity_code = models.CharField(max_length=50)
    program_code = models.CharField(max_length=50)
    particulars = models.TextField()
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total_cost(self):
        try:
            return Decimal(self.quantity or 0) * (self.unit_cost or Decimal("0.00"))
        except TypeError:
            return 0


class AdminExpenseNote(ApprovalMixin):
    cash_req = models.OneToOneField(CashRequisition, related_name='admin_concept', on_delete=models.DO_NOTHING, blank=True, null=True)
    date_of_submission = models.DateTimeField(auto_now_add=True)
    purpose = models.TextField()
    department = models.ForeignKey(Department, on_delete=models.DO_NOTHING, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.DO_NOTHING, blank=True, null=True)
    timeframe_from = models.DateField()
    timeframe_to = models.DateField()
    location = models.CharField(max_length=255)
    objectives = models.TextField()
    expected_outputs = models.TextField()
    proposed_budget = models.DecimalField(max_digits=12, decimal_places=2)
    service_providers = models.TextField()
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{uuid.uuid4().hex[:200]}"
        return super(AdminExpenseNote, self).save(*args, **kwargs)


class AccountingForm(ApprovalMixin):
    reference = models.CharField(max_length=100, blank=True, null=True, unique=True, editable=False)
    requisition = models.OneToOneField(CashRequisition, on_delete=models.CASCADE, related_name="accountings")
    donor_code = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.DO_NOTHING, blank=True, null=True)
    date_of_return = models.DateField()
    description = models.TextField(help_text="Receipts and expenditures for: ......")
    # amount_spent_words = models.CharField(max_length=255)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{uuid.uuid4().hex[:200]}{self.donor_code}"
        if not self.reference:
            self.reference = f"{self.donor_code}-{self.requisition.donor_code}-{self.slug[:5]}"
        return super(AccountingForm, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.donor_code}-{self.requisition.donor_code}-{self.slug[:5]}"

    @property
    def total_received(self):
        return self.items.aggregate(
            total=Sum('amount_received')
        )['total'] or 0

    @property
    def total_spent(self):
        return self.items.aggregate(
            total=Sum('amount_spent')
        )['total'] or 0

    @property
    def total_balance(self):
        return self.total_received - self.total_spent


class AccountingItem(models.Model):
    form = models.ForeignKey(AccountingForm, related_name="items", on_delete=models.CASCADE)
    activity_code = models.CharField(max_length=50)
    program_code = models.CharField(max_length=50)
    details = models.TextField()
    amount_received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def balance(self):
        return (self.amount_received or 0) - (self.amount_spent or 0)


class ApprovalLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    form_type = models.CharField(max_length=50)
    object_id = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
