from django.contrib import admin
from . import models


# 🔹 Inline for requisition items
class CashRequisitionItemInline(admin.TabularInline):
    model = models.CashRequisitionItem
    extra = 1
    fields = (
        "activity_code",
        "program_code",
        "particulars",
        "quantity",
        "unit_cost",
        "total_cost",
    )
    readonly_fields = ("total_cost",)

    def total_cost(self, obj):
        return obj.total_cost


# 🔹 Cash Requisition Admin
@admin.register(models.CashRequisition)
class CashRequisitionAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "donor_code",
        "status",
        "created_by",
        "approved_by",
        "created_at",
        "total_amount_display",
    )

    list_filter = (
        "status",
        "created_at",
        "approved_by",
        "created_by",
    )

    search_fields = (
        "donor_code",
        "purpose",
        "to",
        "slug",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "slug",
        "created_by",
        "checked_by",
        "reviewed_by",
        "approved_by",
        "created_at",
    )

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "donor_code",
                "procurement_requisition",
                "to",
                "purpose",
                "date",
                "amount_in_words",
                "attachment",
                "purchase_order",
            )
        }),

        ("Workflow", {
            "fields": (
                "status",
                "reason_for_rejection",
            )
        }),

        ("Approval Trail", {
            "fields": (
                "created_by",
                "checked_by",
                "reviewed_by",
                "approved_by",
                "created_at",
            )
        }),

        ("System", {
            "fields": ("slug",),
        }),
    )

    inlines = [CashRequisitionItemInline]

    def total_amount_display(self, obj):
        return obj.total_amount()
    total_amount_display.short_description = "Total"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# 🔹 Requisition Items Admin (optional but useful)
@admin.register(models.CashRequisitionItem)
class CashRequisitionItemAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "requisition",
        "activity_code",
        "program_code",
        "quantity",
        "unit_cost",
        "total_cost",
    )

    search_fields = (
        "activity_code",
        "program_code",
        "particulars",
    )

    list_filter = ("program_code",)

    def total_cost(self, obj):
        return obj.total_cost


# 🔹 Accounting Form
@admin.register(models.AccountingForm)
class AccountingFormAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        # "reference",
        "requisition",
        "created_at",
    )

    search_fields = (
        "reference",
    )

    list_filter = ("created_at",)


# 🔹 Accounting Items
@admin.register(models.AccountingItem)
class AccountingItemAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "form",
        "details",
        "amount_received",
        "amount_spent",
    )

    search_fields = ("description",)


# 🔹 Approval Logs
@admin.register(models.ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "action",
        "timestamp",
    )

    list_filter = ("action", "timestamp")

    search_fields = ("user__username",)


# 🔹 Admin Expense Notes
@admin.register(models.AdminExpenseNote)
class AdminExpenseNoteAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "created_by",
        "created_at",
    )

    list_filter = ("created_at",)

    search_fields = ("created_by__username",)


@admin.register(models.FinanceBudget)
class FinanceBudgetAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "period_start", "period_end", "status", "created_by", "total_amount_display")
    list_filter = ("status", "currency")
    search_fields = ("name", "donor", "project__name")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def total_amount_display(self, obj):
        return obj.total_amount
    total_amount_display.short_description = "Total"


@admin.register(models.FinanceBudgetLine)
class FinanceBudgetLineAdmin(admin.ModelAdmin):
    list_display = ("budget", "code", "description", "price_per_unit", "units", "frequency", "total")
    list_filter = ("budget",)
    search_fields = ("code", "description", "activity")


@admin.register(models.BudgetPerformance)
class BudgetPerformanceAdmin(admin.ModelAdmin):
    list_display = ("budget", "line", "period", "funds_received", "expenditure", "variance", "absorption_rate")
    list_filter = ("period", "budget")


@admin.register(models.CashBook)
class CashBookAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "period_start", "period_end", "opening_balance", "closing_balance")
    list_filter = ("period_start", "project")
    search_fields = ("name", "donor")


@admin.register(models.CashBookEntry)
class CashBookEntryAdmin(admin.ModelAdmin):
    list_display = ("cash_book", "date", "pv_number", "payee", "receipt", "payment", "running_balance")
    list_filter = ("date", "cash_book")
    search_fields = ("pv_number", "payee", "description", "budget_line")


@admin.register(models.BankReconciliation)
class BankReconciliationAdmin(admin.ModelAdmin):
    list_display = ("cash_book", "statement_balance", "adjusted_balance", "difference", "prepared_by", "prepared_at")


@admin.register(models.BankReconciliationItem)
class BankReconciliationItemAdmin(admin.ModelAdmin):
    list_display = ("reconciliation", "item_type", "date", "reference", "payee", "amount")
    list_filter = ("item_type", "date")
