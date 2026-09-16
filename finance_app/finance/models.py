import uuid
from decimal import Decimal
from django.utils.text import slugify
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from django.db.models import DecimalField, Sum, F, ExpressionWrapper, Value
from django.db.models.functions import Coalesce, Cast
from account.models import Department
from assets.assetapp.models import AssetMaintenance, Asset
from core.project_models import Project
from core.services import SUPPORTED_CURRENCIES, get_base_currency, quantize_money, convert_amount, get_usd_rate, \
    normalize_currency
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
    currency = models.CharField(max_length=3, default=get_base_currency, help_text="The currency this requisition was actually raised in.")
    exchange_rate_used = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, help_text="Base-currency units per 1 unit of `currency`, as used to convert item costs at submission time.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{uuid.uuid4().hex[:200]}{self.donor_code}")
        return super(CashRequisition, self).save(*args, **kwargs)

    def total_amount(self):
        return sum(item.total_cost for item in self.items.all())

    def original_total_amount(self):
        return sum((item.original_unit_cost if item.original_unit_cost is not None else item.unit_cost) * (item.quantity or 0) for item in self.items.all())

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
    original_unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Unit cost in the parent requisition's own currency, before conversion to the base currency.")

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
    currency = models.CharField(max_length=3, default=get_base_currency, help_text="The currency this expense note was actually raised in.")
    original_proposed_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Proposed budget in the note's own `currency`, before conversion to the base currency.")
    exchange_rate_used = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, help_text="Base-currency units per 1 unit of `currency`, as used to convert proposed_budget at submission time.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{uuid.uuid4().hex[:200]}"
        return super(AdminExpenseNote, self).save(*args, **kwargs)

    def original_total_amount(self):
        return self.original_proposed_budget if self.original_proposed_budget is not None else self.proposed_budget


class AccountingForm(ApprovalMixin):
    reference = models.CharField(max_length=100, blank=True, null=True, unique=True, editable=False)
    requisition = models.OneToOneField(CashRequisition, on_delete=models.CASCADE, related_name="accountings")
    donor_code = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.DO_NOTHING, blank=True, null=True)
    date_of_return = models.DateField()
    description = models.TextField(help_text="Receipts and expenditures for: ......")
    # amount_spent_words = models.CharField(max_length=255)
    slug = models.SlugField(null=True, blank=True, unique=True, editable=False)
    currency = models.CharField(max_length=3, default=get_base_currency, help_text="The currency this retirement was actually accounted in.")
    exchange_rate_used = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, help_text="Base-currency units per 1 unit of `currency`, as used to convert item amounts at retirement time.")

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

    def original_total_spent(self):
        return sum((item.original_amount_spent if item.original_amount_spent is not None else item.amount_spent) for item in self.items.all())


class AccountingItem(models.Model):
    form = models.ForeignKey(AccountingForm, related_name="items", on_delete=models.CASCADE)
    activity_code = models.CharField(max_length=50)
    program_code = models.CharField(max_length=50)
    details = models.TextField()
    amount_received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    original_amount_received = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Amount received in the parent form's own currency, before conversion to the base currency.")
    original_amount_spent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Amount spent in the parent form's own currency, before conversion to the base currency.")

    @property
    def balance(self):
        return (self.amount_received or 0) - (self.amount_spent or 0)


class ApprovalLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    form_type = models.CharField(max_length=50)
    object_id = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)


class FinanceBudget(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="finance_budgets", null=True, blank=True)
    donor = models.CharField(max_length=200, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    currency = models.CharField(max_length=10, default="UGX")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="finance_budgets_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_start", "name")

    def clean(self):
        if self.period_end and self.period_start and self.period_end < self.period_start:
            raise ValidationError("Budget end date cannot be before its start date.")

    @property
    def total_amount(self):
        return sum((line.total for line in self.lines.all()), Decimal("0.00"))

    def __str__(self):
        return self.name


class FinanceBudgetLine(models.Model):
    budget = models.ForeignKey(FinanceBudget, on_delete=models.CASCADE, related_name="lines")
    code = models.CharField(max_length=50)
    outcome = models.CharField(max_length=255, blank=True)
    activity = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    unit = models.CharField(max_length=100, blank=True)
    price_per_unit = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    units = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    frequency = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    justification = models.TextField(blank=True)

    class Meta:
        ordering = ("code", "id")
        constraints = [models.UniqueConstraint(fields=("budget", "code"), name="unique_budget_line_code")]

    @property
    def total(self):
        return (self.price_per_unit or 0) * (self.units or 0) * (self.frequency or 0)

    def __str__(self):
        return f"{self.code} - {self.description}"


class BudgetPerformance(models.Model):
    budget = models.ForeignKey(FinanceBudget, on_delete=models.CASCADE, related_name="performance_records")
    line = models.ForeignKey(FinanceBudgetLine, on_delete=models.PROTECT, related_name="performance_records")
    period = models.DateField(help_text="Use the first day of the reporting month")
    funds_received = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    expenditure = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    comment = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="budget_performance_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period", "line__code")
        constraints = [models.UniqueConstraint(fields=("budget", "line", "period"), name="unique_budget_performance_period")]

    @property
    def budget_amount(self):
        return self.line.total

    @property
    def variance(self):
        return self.budget_amount - self.expenditure

    @property
    def donor_balance(self):
        return self.budget_amount - self.funds_received

    @property
    def burn_rate(self):
        return (self.expenditure / self.funds_received * 100) if self.funds_received else Decimal("0.00")

    @property
    def absorption_rate(self):
        return (self.expenditure / self.budget_amount * 100) if self.budget_amount else Decimal("0.00")


class CashBook(models.Model):
    name = models.CharField(max_length=200, default="Main Cash Book")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, null=True, blank=True, related_name="cash_books")
    donor = models.CharField(max_length=200, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    opening_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="cash_books_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_start", "name")

    @property
    def total_receipts(self):
        return self.entries.aggregate(total=Coalesce(Sum("receipt"), Value(0, output_field=DecimalField(max_digits=16, decimal_places=2))))["total"]

    @property
    def total_payments(self):
        return self.entries.aggregate(total=Coalesce(Sum("payment"), Value(0, output_field=DecimalField(max_digits=16, decimal_places=2))))["total"]

    @property
    def closing_balance(self):
        return self.opening_balance + self.total_receipts - self.total_payments

    def __str__(self):
        return self.name


class CashBookEntry(models.Model):
    cash_book = models.ForeignKey(CashBook, on_delete=models.CASCADE, related_name="entries")
    date = models.DateField(default=timezone.now)
    pv_number = models.CharField(max_length=80, blank=True)
    budget_line = models.CharField(max_length=80, blank=True)
    cheque_number = models.CharField(max_length=80, blank=True)
    payee = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    receipt = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    payment = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    comments = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="cash_book_entries_created")

    class Meta:
        ordering = ("date", "id")

    @property
    def running_balance(self):
        prior = self.cash_book.entries.filter(
            models.Q(date__lt=self.date) | models.Q(date=self.date, id__lt=self.id)
        ).aggregate(
            receipts=Coalesce(Sum("receipt"), Value(0, output_field=DecimalField(max_digits=16, decimal_places=2))),
            payments=Coalesce(Sum("payment"), Value(0, output_field=DecimalField(max_digits=16, decimal_places=2))),
        )
        return self.cash_book.opening_balance + prior["receipts"] - prior["payments"] + self.receipt - self.payment


class BankReconciliation(models.Model):
    cash_book = models.OneToOneField(CashBook, on_delete=models.CASCADE, related_name="bank_reconciliation")
    statement_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    prepared_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bank_reconciliations_prepared")
    prepared_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    @property
    def total_unpresented_payments(self):
        return self.items.filter(item_type="payment").aggregate(total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField(max_digits=16, decimal_places=2))))["total"]

    @property
    def total_uncredited_receipts(self):
        return self.items.filter(item_type="receipt").aggregate(total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField(max_digits=16, decimal_places=2))))["total"]

    @property
    def adjusted_balance(self):
        return self.statement_balance - self.total_unpresented_payments + self.total_uncredited_receipts

    @property
    def difference(self):
        return self.adjusted_balance - self.cash_book.closing_balance


class BankReconciliationItem(models.Model):
    ITEM_TYPES = (("payment", "Payment in cash book, not on statement"), ("receipt", "Receipt on statement, not in cash book"))
    reconciliation = models.ForeignKey(BankReconciliation, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    payee = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    notes = models.TextField(blank=True)



class FinancialCategory(models.Model):
    """A lightweight chart-of-accounts entry used to classify FinancialTransaction records."""

    class CategoryType(models.TextChoices):
        # Ordered to match the standard 5-group chart of accounts layout
        # (Assets, Liabilities, Equity, Income, Expenses) — the view relies
        # on this iteration order to render groups top-to-bottom.
        ASSET = "asset", "Assets"
        LIABILITY = "liability", "Liabilities"
        EQUITY = "equity", "Equity"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expenses"

    # Which side of the ledger each group normally carries a balance on —
    # used only to label a group/account's total as Dr or Cr for display.
    # This app doesn't record true double-entry debit/credit postings, so
    # this is a display convention, not a computed balance side.
    NATURAL_BALANCE_SIDE = {
        CategoryType.ASSET: "Dr",
        CategoryType.LIABILITY: "Cr",
        CategoryType.EQUITY: "Cr",
        CategoryType.INCOME: "Cr",
        CategoryType.EXPENSE: "Dr",
    }

    code = models.CharField(max_length=20, unique=True)
    alt_code = models.CharField(max_length=20, blank=True, help_text="Optional secondary/legacy code for this account.")
    name = models.CharField(max_length=100, unique=True)
    category_type = models.CharField(max_length=20, choices=CategoryType.choices)

    # Tree structure: any node can be a group (a folder that organizes other
    # groups or accounts, but is never posted to directly) or a leaf ledger
    # account (postable — FinancialTransaction.category points only here).
    # category_type is denormalized onto every node (not just roots) so
    # grouping/ordering doesn't need a recursive parent-chain walk; the view
    # is responsible for keeping a child's category_type in sync with its
    # parent's when the tree is edited.
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children",
        help_text="The group this account/sub-group sits under. Root groups (Assets, Liabilities, ...) leave this blank.",
    )
    is_group = models.BooleanField(
        default=False,
        help_text="A group (folder) organizes other groups/accounts underneath it. Transactions can only post to non-group (leaf) accounts.",
    )

    currency = models.CharField(
        max_length=3, choices=[(c, c) for c in SUPPORTED_CURRENCIES], default=get_base_currency,
        help_text="The currency this specific account is denominated in — opening/closing balance are shown in this currency.",
    )
    opening_balance = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0.00"),
        help_text="Balance carried in when this account was set up, in the account's own currency.",
    )

    class Meta:
        verbose_name = "Financial Category"
        verbose_name_plural = "Financial Categories"
        ordering = ("category_type", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def balance_side(self):
        return self.NATURAL_BALANCE_SIDE[self.category_type]


class FinancialTransaction(models.Model):
    """
    The organization's consolidated financial ledger: one record per money
    movement (income, expense, or inter-fund transfer), normalized to the
    organization's configured base currency (core.services.get_base_currency
    — defaults to UGX, but is a per-deployment setting under
    Settings → Currency & Region, not a hardcoded assumption).

    Every transaction is optionally linked back to the source document that
    generated it, spanning Finance's own requisition/retirement workflow as
    well as Procurement (purchase orders) and Assets (purchase cost,
    maintenance) — so a single model gives a full financial picture instead
    of leaving spend scattered, unlinked, across four apps.
    """

    class TransactionType(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"
        TRANSFER = "transfer", "Transfer"
        JOURNAL = "journal", "Journal Entry"

    reference = models.CharField(max_length=40, unique=True, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    category = models.ForeignKey(FinancialCategory, on_delete=models.PROTECT, related_name="transactions")

    # `amount` stays normalized to the organization's configured base
    # currency (see core.services.get_base_currency — defaults to UGX, but
    # is set per-deployment to match the region) — every existing
    # report/aggregate in the ledger sums this field, so it remains the one
    # number that's always comparable across currencies. `currency`/
    # `original_amount`/`exchange_rate_used` preserve what the transaction
    # actually was, so donor reports can show real USD/KES/etc figures
    # instead of only the base-currency-converted number.
    # Always non-negative for every transaction type except JOURNAL: a
    # journal entry line can be negative — it means "this decreases the
    # account's natural-side balance" (e.g. a credit posted to a Dr-normal
    # asset account). Every balance computation across the app is a plain
    # Sum(amount), so a signed amount here is what actually lets a journal
    # entry both increase one account and decrease another without any of
    # that aggregation logic needing to change.
    amount = models.DecimalField(max_digits=16, decimal_places=2, help_text="Base-currency-equivalent amount, for cross-currency totals.")
    currency = models.CharField(max_length=3, default=get_base_currency, help_text="The currency this transaction was actually recorded in.")
    original_amount = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        help_text="Amount in the original `currency`, before conversion to the base currency.",
    )
    exchange_rate_used = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        help_text="UGX per 1 unit of `currency`, as used to compute `amount` at recording time.",
    )

    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)

    donor_code = models.CharField(max_length=100, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")

    # Links to whichever source document produced this transaction. All
    # optional and independent — a transaction typically sets one of these.
    cash_requisition = models.ForeignKey(CashRequisition, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")
    accounting_form = models.ForeignKey(AccountingForm, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")
    admin_expense = models.ForeignKey(AdminExpenseNote, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")
    asset_maintenance = models.ForeignKey(AssetMaintenance, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="financial_transactions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Financial Transaction"
        ordering = ("-date", "-created_at")
        indexes = [
            models.Index(fields=["transaction_type", "date"]),
            models.Index(fields=["project", "date"]),
        ]

    def __str__(self):
        return f"{self.reference} · {self.get_transaction_type_display()} · {self.amount}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    @classmethod
    def _get_category(cls, code, name, category_type):
        """
        `code` here is a stable internal mnemonic (kept in `alt_code`), not
        the account's numeric `code` — Finance staff can freely renumber
        accounts from the Chart of Accounts UI, so looking this up by the
        numeric code would silently create a duplicate category the moment
        someone renumbers the real one.
        """
        category = FinancialCategory.objects.filter(alt_code=code).first()
        if category:
            return category

        root = FinancialCategory.objects.filter(
            parent__isnull=True, is_group=True, category_type=category_type
        ).first()
        next_code = code
        if root and root.code.isdigit():
            sibling_codes = FinancialCategory.objects.filter(parent=root).values_list("code", flat=True)
            numeric_siblings = [int(c) for c in sibling_codes if c.isdigit()]
            next_code = str(max(numeric_siblings, default=int(root.code)) + 10)

        return FinancialCategory.objects.create(
            code=next_code, alt_code=code, name=name, category_type=category_type, parent=root,
        )

    @classmethod
    def record_cash_advance(cls, cash_requisition, user):
        """Fund release/advance recorded the moment a CashRequisition is fully approved.

        currency/original_amount/exchange_rate_used are the requisition's
        true original figures, captured at data-entry time on the
        requisition and its items (see create_cash_requisition() in
        finance/views.py) — amount stays the base-currency-equivalent
        total, unchanged, for every existing report/aggregate.
        """
        project = None
        procurement_req = cash_requisition.procurement_requisition
        if procurement_req and procurement_req.procurement:
            project = procurement_req.procurement.project

        amount = cash_requisition.total_amount()
        original_amount = cash_requisition.original_total_amount()
        currency = normalize_currency(cash_requisition.currency) if cash_requisition.currency in SUPPORTED_CURRENCIES else get_base_currency()
        rate_used = cash_requisition.exchange_rate_used if cash_requisition.exchange_rate_used is not None else Decimal("1")
        return cls.objects.create(
            transaction_type=cls.TransactionType.TRANSFER,
            category=cls._get_category("FUND-ADV", "Fund Advance / Transfer", FinancialCategory.CategoryType.ASSET),
            amount=amount,
            currency=currency,
            original_amount=original_amount,
            exchange_rate_used=rate_used,
            date=cash_requisition.date,
            description=f"Fund advance released — {cash_requisition.purpose}"[:255],
            donor_code=cash_requisition.donor_code,
            project=project,
            cash_requisition=cash_requisition,
            created_by=user,
        )

    @classmethod
    def record_accounting_expense(cls, accounting_form, user):
        """Actual accounted expenditure recorded when a fund retirement (AccountingForm) is approved.

        currency/original_amount/exchange_rate_used are the retirement's
        true original figures, captured at data-entry time (see
        save_accounting() in finance/views.py) — amount stays the
        base-currency-equivalent total, unchanged, for every existing
        report/aggregate.
        """
        requisition = accounting_form.requisition
        project = None
        if requisition and requisition.procurement_requisition and requisition.procurement_requisition.procurement:
            project = requisition.procurement_requisition.procurement.project

        amount = accounting_form.total_spent
        original_amount = accounting_form.original_total_spent()
        currency = normalize_currency(accounting_form.currency) if accounting_form.currency in SUPPORTED_CURRENCIES else get_base_currency()
        rate_used = accounting_form.exchange_rate_used if accounting_form.exchange_rate_used is not None else Decimal("1")
        return cls.objects.create(
            transaction_type=cls.TransactionType.EXPENSE,
            category=cls._get_category("PROG-EXP", "Program Expenditure", FinancialCategory.CategoryType.EXPENSE),
            amount=amount,
            currency=currency,
            original_amount=original_amount,
            exchange_rate_used=rate_used,
            date=accounting_form.date_of_return,
            description=f"Fund retirement — {accounting_form.donor_code}"[:255],
            donor_code=accounting_form.donor_code,
            department=accounting_form.department,
            project=project,
            accounting_form=accounting_form,
            cash_requisition=requisition,
            created_by=user,
        )

    @classmethod
    def record_admin_expense(cls, admin_expense, user):
        """Administrative expense recorded when an AdminExpenseNote is approved.

        currency/original_amount/exchange_rate_used are the note's true
        original figures, captured at data-entry time (see
        create_admin_expense() in finance/views.py) — amount stays the
        base-currency-equivalent proposed_budget, unchanged, for every
        existing report/aggregate.
        """
        amount = admin_expense.proposed_budget
        original_amount = admin_expense.original_total_amount()
        currency = normalize_currency(admin_expense.currency) if admin_expense.currency in SUPPORTED_CURRENCIES else get_base_currency()
        rate_used = admin_expense.exchange_rate_used if admin_expense.exchange_rate_used is not None else Decimal("1")
        return cls.objects.create(
            transaction_type=cls.TransactionType.EXPENSE,
            category=cls._get_category("ADMIN-EXP", "Administrative Expense", FinancialCategory.CategoryType.EXPENSE),
            amount=amount,
            currency=currency,
            original_amount=original_amount,
            exchange_rate_used=rate_used,
            date=admin_expense.timeframe_from,
            description=admin_expense.purpose[:255],
            department=admin_expense.department,
            project=admin_expense.project,
            admin_expense=admin_expense,
            cash_requisition=admin_expense.cash_req,
            created_by=user,
        )

    @staticmethod
    def convert_to_base_currency(amount, currency):
        """
        Convert `amount` in `currency` to the organization's configured
        base currency (see core.services.get_base_currency — this is a
        per-deployment setting, not always UGX) using the organization's
        actual configured exchange rates, not the acting user's personal
        display-currency preference — a transaction's currency is a fact
        about the transaction, not about who's viewing it. Returns
        (base_amount, exchange_rate_used) where the rate is base-currency
        units per 1 unit of `currency`.
        """
        base_currency = get_base_currency()
        currency = currency if currency in SUPPORTED_CURRENCIES else base_currency
        if currency == base_currency:
            return quantize_money(amount), Decimal("1")

        base_amount = convert_amount(amount, currency, base_currency)
        from_rate = get_usd_rate(currency)
        to_rate = get_usd_rate(base_currency)
        rate_used = (to_rate / from_rate) if from_rate else Decimal("0")
        return base_amount, rate_used


class JournalEntry(models.Model):
    """
    A manual double-entry posting: one header with two or more lines, where
    total debits must equal total credits — the "going forward, real
    double-entry" mechanism agreed on earlier, kept as its own model rather
    than retrofitted onto every existing single-sided transaction path
    (cash requisitions, retirements, admin expenses), which continue to
    record exactly as they did before. Each line still creates a normal
    FinancialTransaction row (see JournalEntryLine.post()), so every
    existing report (Chart of Accounts, General Ledger, Income Statement,
    Balance Sheet) picks up journal entries automatically without needing
    to know this model exists.
    """

    reference = models.CharField(max_length=40, unique=True, editable=False)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_entries_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"
        ordering = ("-date", "-created_at")

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"JV-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_debit(self):
        return sum((line.debit for line in self.lines.all()), Decimal("0.00"))

    @property
    def total_credit(self):
        return sum((line.credit for line in self.lines.all()), Decimal("0.00"))

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class JournalEntryLine(models.Model):
    """
    One side of a JournalEntry — exactly one of debit/credit is non-zero.
    Posting a line (see post()) creates the corresponding FinancialTransaction
    with a SIGNED amount: positive if this line increases the account's own
    natural balance side, negative if it decreases it. Every existing
    balance computation is a plain Sum(amount), so a signed amount is what
    lets one entry increase one account and decrease another without any
    of that aggregation logic needing to change — the same convention a
    real ledger uses, just expressed as a sign instead of two columns.
    """

    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    category = models.ForeignKey(FinancialCategory, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))
    description = models.CharField(max_length=255, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_lines")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_lines")
    transaction = models.OneToOneField(
        FinancialTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="journal_line",
    )

    class Meta:
        ordering = ("pk",)

    def __str__(self):
        return f"{self.category} — Dr {self.debit} / Cr {self.credit}"

    def post(self):
        """Create (or update, if already posted) the FinancialTransaction
        this line represents, with the signed amount described above.

        Journal entries don't support multi-currency posting yet — amounts
        are entered and recorded in the org's base currency regardless of
        which currency the account itself is denominated in, rather than
        mislabeling a base-currency figure as if it were in the account's
        native currency.
        """
        base_currency = get_base_currency()
        raw = self.debit - self.credit
        signed_amount = raw if self.category.balance_side == "Dr" else -raw

        if self.transaction_id:
            txn = self.transaction
            txn.category = self.category
            txn.amount = signed_amount
            txn.original_amount = signed_amount
            txn.currency = base_currency
            txn.date = self.journal_entry.date
            txn.description = self.description or self.journal_entry.description
            txn.department = self.department
            txn.project = self.project
            txn.save()
            return txn

        txn = FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.JOURNAL,
            category=self.category,
            amount=signed_amount,
            currency=base_currency,
            original_amount=signed_amount,
            exchange_rate_used=Decimal("1"),
            date=self.journal_entry.date,
            description=self.description or self.journal_entry.description,
            department=self.department,
            project=self.project,
            created_by=self.journal_entry.created_by,
        )
        self.transaction = txn
        self.save(update_fields=["transaction"])
        return txn
