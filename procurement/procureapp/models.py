import uuid
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, F, DecimalField
from django.core.exceptions import ValidationError
from core.project_models import Project, ProjectBudget
from decimal import Decimal


class ApprovalStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    REVIEWED = "Reviewed", "Reviewed"
    CHECKED = "Checked", "Checked"
    APPROVED = "Approved", "Approved"
    REJECTED = "Rejected", "Rejected"


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_created")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_updated")

    class Meta:
        abstract = True


class ApprovalWorkflowModel(TimestampedModel):
    status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="%(class)s_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="%(class)s_checked")
    checked_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="%(class)s_approved")
    approved_at = models.DateTimeField(null=True, blank=True)

    rejected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="%(class)s_rejected")
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        abstract = True

    @property
    def is_approved(self):
        return self.status == ApprovalStatus.APPROVED


class Product(models.Model):
    name = models.CharField(max_length=255)
    est_unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=120, blank=True, null=True)
    abpc = models.BooleanField(default=False)# approved by project coodinator

    def __str__(self):
        return f'{self.name}'


class Supplier(models.Model):
    full_name = models.CharField(max_length=255, blank=True,null=True)
    title = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    organisation_name = models.CharField(max_length=255, blank=True,null=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    tin_number = models.CharField(max_length=64, blank=True)
    active = models.BooleanField(default=False)  # approved by procurement
    documents = models.FileField(upload_to='suppliers/docs/', blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:200]
        return super(Supplier, self).save(*args, **kwargs)

    def __str__(self):
        return f'{self.organisation_name if self.organisation_name else self.full_name or self.phone}'


class ProcurementPlan(ApprovalWorkflowModel):
    number = models.CharField(max_length=50, unique=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,
                                  related_name='procurements')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    donor = models.CharField(max_length=128, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fiscal_year = models.CharField(max_length=128, null=True, blank=True)
    budget_period = models.CharField(max_length=20, choices=ProjectBudget.PERIOD_CHOICES, default=ProjectBudget.FULL_YEAR)
    project_budget = models.ForeignKey(ProjectBudget, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='procurement_plans')
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['status']),
            models.Index(fields=['project', 'fiscal_year', 'budget_period']),
        ]

    def __str__(self):
        return self.number

    @property
    def department(self):
        """
        Always derive department from project.
        Avoid storing duplicate department data.
        """
        if self.project:
            return self.project.department
        return None

    @property
    def project_head(self):
        return self.project.project_head if self.project else None

    @property
    def project_accountant(self):
        return self.project.project_accountant if self.project else None

    @property
    def project_officer(self):
        return self.project.project_officer if self.project else None

    @property
    def is_locked(self):
        return self.status == 'Approved'

    @property
    def is_reviewed(self):
        return bool(self.reviewed_by)

    @property
    def is_approved(self):
        return bool(self.approved_by)

    @property
    def remaining_budget(self):
        project_budget = self.resolve_project_budget()
        if project_budget:
            return project_budget.amount_remaining(exclude_plan=self) - self.total_amount
        return self.budget - self.total_amount

    def resolve_project_budget(self):
        if not self.project_id or not self.fiscal_year:
            return None

        exact_budget = ProjectBudget.objects.filter(
            project=self.project,
            fiscal_year=self.fiscal_year,
            period=self.budget_period or ProjectBudget.FULL_YEAR,
        ).first()

        if exact_budget:
            return exact_budget

        if self.budget_period != ProjectBudget.FULL_YEAR:
            return ProjectBudget.objects.filter(
                project=self.project,
                fiscal_year=self.fiscal_year,
                period=ProjectBudget.FULL_YEAR,
            ).first()

        return None

    def amount_already_planned(self):
        project_budget = self.resolve_project_budget()
        if not project_budget:
            return Decimal('0.00')
        return project_budget.amount_used(exclude_plan=self)

    def validate_budget_limit(self, proposed_total=None):
        proposed_total = proposed_total if proposed_total is not None else self.total_amount
        project_budget = self.resolve_project_budget()

        if not self.project_id:
            raise ValidationError("A procurement plan must be linked to a project.")

        if not self.fiscal_year:
            raise ValidationError("A procurement plan must include a fiscal year.")

        if not project_budget:
            period = self.get_budget_period_display() if self.budget_period else 'Full Year'
            raise ValidationError(
                f"No budget exists for {self.project} in fiscal year {self.fiscal_year} ({period})."
            )

        used_elsewhere = project_budget.amount_used(exclude_plan=self)
        if used_elsewhere + proposed_total > project_budget.budget_amount:
            remaining = project_budget.budget_amount - used_elsewhere
            raise ValidationError(
                f"Plan total {proposed_total:,.2f} exceeds the remaining budget "
                f"for {self.project} in {self.fiscal_year} ({project_budget.get_period_display()}). "
                f"Remaining budget is {remaining:,.2f}."
            )

        return project_budget

    def update_total(self):
        total = (
            self.items.aggregate(
                total=Sum(
                    F('qty') * F('est_unit_cost'),
                    output_field=DecimalField(
                        max_digits=14,
                        decimal_places=2
                    )
                )
            )['total']
            or Decimal('0.00')
        )

        self.total_amount = total
        self.validate_budget_limit(total)
        self.save(update_fields=['total_amount'])

    def update_workflow_status(self):
        """
        Programs Head → ED
        """

        if self.rejected_by:
            self.status = 'Rejected'

        elif (
            self.reviewed_by and
            self.approved_by
        ):
            self.status = 'Approved'

        else:
            self.status = 'Pending'

        self.save(update_fields=['status'])

    def sync_project_fields(self):
        """
        Auto-populate donor and budget from project budget.
        """
        if self.project and not self.donor:
            self.donor = self.project.donor
        project_budget = self.resolve_project_budget()
        if project_budget:
            self.project_budget = project_budget
            self.budget = project_budget.budget_amount

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = uuid.uuid4().hex

        self.sync_project_fields()

        super().save(*args, **kwargs)


class ProcurementPlanItem(models.Model):
    procurement = models.ForeignKey(ProcurementPlan, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, help_text='Specification')
    description = models.CharField(max_length=512, help_text='Subject of Procurement')
    qty = models.DecimalField(max_digits=10, decimal_places=2)
    est_unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(blank=True, null=True)
    unit_measure = models.CharField(max_length=100, default='Pcs', help_text='Unit of measure')

    def line_total(self):
        return (self.qty or 0) * (self.est_unit_cost or 0)

    def __str__(self):
        return f'{self.product.name}'


class Requisition(ApprovalWorkflowModel):
    number = models.CharField(max_length=60, unique=True)
    procurement = models.ForeignKey(ProcurementPlan, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='requisitions')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                  related_name='issued_requisitions')
    activity_name = models.CharField(max_length=128, blank=True, null=True)
    date = models.DateField(default=timezone.now)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    awarded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['number']),
            models.Index(fields=['status']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return self.number

    @property
    def project(self):
        return self.procurement.project if self.procurement else None

    @property
    def project_head(self):
        return (
            self.project.project_head
            if self.project else None
        )

    @property
    def project_accountant(self):
        return (
            self.project.project_accountant
            if self.project else None
        )

    @property
    def project_officer(self):
        return (
            self.project.project_officer
            if self.project else None
        )

    @property
    def is_fully_approved(self):
        return (
            self.reviewed_by and
            self.checked_by and
            self.approved_by and
            self.status == 'Approved'
        )

    @property
    def is_locked(self):
        return self.status == 'Approved'

    def update_total(self):
        total = (
            self.items.aggregate(
                total=Sum(
                    F('qty') * F('unit_price'),
                    output_field=DecimalField(
                        max_digits=14,
                        decimal_places=2
                    )
                )
            )['total']
            or Decimal('0.00')
        )

        self.total = total
        self.save(update_fields=['total'])

    def update_workflow_status(self):
        """
        Project Head → Project Accountant → ED
        """

        if self.rejected_by:
            self.status = 'Rejected'

        elif (
            self.reviewed_by and
            self.checked_by and
            self.approved_by
        ):
            self.status = 'Approved'

        else:
            self.status = 'Pending'

        self.save(update_fields=['status'])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex

        super().save(*args, **kwargs)


class RequisitionItem(models.Model):
    po = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='items')
    procurement_item = models.ForeignKey(ProcurementPlanItem, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=512, help_text='Subject of Procurement')
    unit_measure = models.CharField(max_length=120, blank=True, null=True)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_date = models.DateField(blank=True, null=True)

    def line_total(self):
        return (self.qty or 0) * (self.unit_price or 0)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.procurement_item and self.po and self.po.procurement_id:
            if self.procurement_item.procurement_id != self.po.procurement_id:
                raise ValidationError("Selected item is not part of this project's approved procurement plan.")

    def __str__(self):
        return f"{self.description} ({self.qty} @ {self.unit_price})"


class RFQ(TimestampedModel):
    """Request for Quotation linked to approved Procurement Plans."""
    req = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='rfqs', null=True, blank=True)
    reference_no = models.CharField(max_length=60, unique=True)
    date_issued = models.DateField(default=timezone.now)
    status = models.CharField(max_length=30, choices=[('Pending','Pending'),('Sent','Sent'),('Responded','Responded')], default='Pending')
    file = models.FileField(upload_to='Rfq', default='')
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)
    deadline = models.DateField(null=True, blank=True)
    supplier = models.ManyToManyField(Supplier, related_name='rfq_supplier')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:200]
        return super(RFQ, self).save(*args, **kwargs)

    def __str__(self):
        return f"RFQ - {self.reference_no}"


@receiver([post_save, post_delete], sender=RequisitionItem)
def update_req_total(sender, instance, **kwargs):
    po = instance.po
    total = sum(item.line_total() for item in po.items.all())
    po.total = total
    po.save(update_fields=['total'])


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                             related_name='procurement_audit_logs')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(null=True, blank=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:200]
        return super(AuditLog, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action}"


class RFQSendLog(models.Model):
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='send_logs')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='rfq_send_logs')
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    date_sent = models.DateTimeField(auto_now_add=True)
    awarded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    request_id = models.CharField(max_length=120, null=True, blank=True)

    class Meta:
        unique_together = ('rfq', 'supplier')
        ordering = ['-date_sent']

    def __str__(self):
        return f"{self.rfq.reference_no} -> {self.supplier.full_name or self.supplier.title} : {self.amount}"


class PurchaseOrder(models.Model):
    send_log = models.ForeignKey(RFQSendLog, on_delete=models.CASCADE, related_name='purchase_orders')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='purchase_orders')
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE,related_name='purchase_orders')
    procurement_plan = models.ForeignKey(ProcurementPlan, on_delete=models.CASCADE, related_name='purchase_orders')
    final_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    po_number = models.CharField(max_length=50, unique=True, null=True)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    pdf = models.FileField(upload_to='purchase_orders/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = uuid.uuid4().hex[:200]
        return super(PurchaseOrder, self).save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PO-{self.po_number} ({self.supplier})"

    def get_absolute_url(self):
        return reverse('purchase_order_detail', args=[str(self.id)])


class SupplierSpendReport(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='spend_reports')
    total_spent = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='spend_reports')
    requisition = models.ForeignKey(Requisition, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplier_spend_reports')
    invoice_no = models.CharField(max_length=80, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=[('Not Paid', 'Not Paid'), ('Paid', 'Paid')], default='Not Paid')
    last_updated = models.DateTimeField(auto_now=True)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = uuid.uuid4().hex

        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['purchase_order'],
                name='unique_supplier_spend_report_per_purchase_order',
            )
        ]

    def recompute(self):
        total = self.supplier.purchase_orders.filter(sent=True).aggregate(total=Sum('final_amount'))['total'] or 0
        self.total_spent = total
        if self.purchase_order:
            self.requisition = self.purchase_order.requisition
        else:
            latest_po = self.supplier.purchase_orders.filter(sent=True).order_by('-issue_date', '-id').first()
            if latest_po:
                self.purchase_order = latest_po
                self.requisition = latest_po.requisition
            # invoice = latest_po.requisition.invoices.filter(supplier=self.supplier).order_by('-date', '-id').first()
            # if invoice:
            #     self.invoice_no = invoice.invoice_number
            #     self.invoice_date = invoice.date
            #     self.invoice_amount = invoice.amount
            #     self.payment_status = 'Paid' if invoice.status == 'Paid' else 'Not Paid'
        self.save(update_fields=[
            'total_spent', 'purchase_order', 'requisition', 'invoice_no',
            'invoice_date', 'invoice_amount', 'payment_status', 'last_updated'
        ])
        return self.total_spent

    def __str__(self):
        return f"{self.supplier.full_name or self.supplier.title} : {self.total_spent}"
