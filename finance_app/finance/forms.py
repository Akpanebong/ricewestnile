from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import (
    FinanceBudget, FinanceBudgetLine, CashBook,
    CashBookEntry, BankReconciliation, BankReconciliationItem, FinancialCategory,
)


class StyledFinanceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css}".strip()


class FinanceBudgetForm(StyledFinanceForm):
    class Meta:
        model = FinanceBudget
        fields = ["name", "project", "donor", "period_start", "period_end", "currency", "status", "notes"]
        widgets = {"period_start": forms.DateInput(attrs={"type": "date"}), "period_end": forms.DateInput(attrs={"type": "date"}),
                   "notes": forms.Textarea(attrs={"rows": 1})}


class FinanceBudgetLineForm(StyledFinanceForm):
    class Meta:
        model = FinanceBudgetLine
        fields = [
            "category", "outcome", "activity",
            "m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08", "m09", "m10", "m11", "m12",
            "justification",
        ]
        widgets = {
            # Rendered via the shared account-picker modal (search over the
            # full chart of accounts) instead of a long <select> — see
            # templates/finance/includes/account_picker_modal.html.
            "category": forms.HiddenInput(attrs={"data-account-value": ""}),
            "justification": forms.Textarea(attrs={"rows": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only postable (leaf) accounts can carry a budget — a group is a
        # folder, never something transactions post against — same
        # queryset journal_entry_create uses for the same reason.
        self.fields["category"].queryset = FinancialCategory.objects.filter(
            is_group=False
        ).order_by("category_type", "code")

    def clean(self):
        cleaned_data = super().clean()
        # A month left blank means "no budget that month", not invalid —
        # the model column defaults to 0.00, but blank=True makes the form
        # field optional, so an empty submission comes back as None here.
        for field in FinanceBudgetLine.MONTH_FIELDS:
            if cleaned_data.get(field) is None:
                cleaned_data[field] = Decimal("0.00")

        # Income is a credit-side account — budgeted (and, correspondingly,
        # actual) income is entered as zero or negative so a budget's totals
        # net to its true cost instead of adding receipts to disbursements.
        # Catching a stray positive figure here, per month, is what makes
        # that convention reliable rather than a note nobody remembers.
        category = cleaned_data.get("category")
        if category and category.category_type == FinancialCategory.CategoryType.INCOME:
            for field in FinanceBudgetLine.MONTH_FIELDS:
                if cleaned_data.get(field, Decimal("0.00")) > 0:
                    self.add_error(field, "Income is a credit — enter it as zero or a negative amount.")

        return cleaned_data


class BudgetLineFormSetBase(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            # Individual lines already have problems — don't pile on with a
            # balance figure computed from data that isn't even valid yet.
            return

        total_income = Decimal("0.00")
        total_expense = Decimal("0.00")
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            category = form.cleaned_data.get("category")
            if category is None:
                continue
            line_total = sum(
                (form.cleaned_data.get(field) or Decimal("0.00") for field in FinanceBudgetLine.MONTH_FIELDS),
                Decimal("0.00"),
            )
            if category.category_type == FinancialCategory.CategoryType.INCOME:
                total_income += line_total
            elif category.category_type == FinancialCategory.CategoryType.EXPENSE:
                total_expense += line_total

        # Income is a credit-side account, so a line against it may be typed
        # as a negative figure following that convention — compare
        # magnitudes, not raw signed sums, so a budget entered that way
        # isn't wrongly flagged as unbalanced.
        if abs(total_income) != abs(total_expense):
            raise forms.ValidationError(
                "This budget doesn't balance — total expected income (%(income)s) must equal "
                "total expected costs (%(expense)s). Lines on asset/liability/equity accounts "
                "aren't counted on either side." % {
                    "income": f"{abs(total_income):,.2f}",
                    "expense": f"{abs(total_expense):,.2f}",
                }
            )


BudgetLineFormSet = inlineformset_factory(
    FinanceBudget, FinanceBudgetLine, form=FinanceBudgetLineForm, formset=BudgetLineFormSetBase,
    extra=1, can_delete=True,
)


class CashBookForm(StyledFinanceForm):
    class Meta:
        model = CashBook
        fields = ["name", "project", "donor", "period_start", "period_end", "opening_balance"]
        widgets = {"period_start": forms.DateInput(attrs={"type": "date"}), "period_end": forms.DateInput(attrs={"type": "date"})}


class CashBookEntryForm(StyledFinanceForm):
    class Meta:
        model = CashBookEntry
        fields = ["date", "pv_number", "budget_line", "cheque_number", "payee", "description", "receipt", "payment", "comments"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "description": forms.Textarea(attrs={"rows": 2}),
                   "comments": forms.Textarea(attrs={"rows": 1})}


class BankReconciliationForm(StyledFinanceForm):
    class Meta:
        model = BankReconciliation
        fields = ["statement_balance", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 1})}


class BankReconciliationItemForm(StyledFinanceForm):
    class Meta:
        model = BankReconciliationItem
        fields = ["item_type", "date", "reference", "payee", "amount", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 2})}


BankReconciliationItemFormSet = inlineformset_factory(BankReconciliation, BankReconciliationItem, form=BankReconciliationItemForm, extra=1, can_delete=True)
