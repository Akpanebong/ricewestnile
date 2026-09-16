from django import forms
from django.forms import inlineformset_factory

from .models import (
    FinanceBudget, FinanceBudgetLine, BudgetPerformance, CashBook,
    CashBookEntry, BankReconciliation, BankReconciliationItem,
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
        fields = ["code", "outcome", "activity", "description", "unit", "price_per_unit", "units", "frequency", "justification"]
        widgets = {"justification": forms.Textarea(attrs={"rows": 1}), "description": forms.TextInput()}


BudgetLineFormSet = inlineformset_factory(FinanceBudget, FinanceBudgetLine, form=FinanceBudgetLineForm, extra=1, can_delete=True)


class BudgetPerformanceForm(StyledFinanceForm):
    class Meta:
        model = BudgetPerformance
        fields = ["budget", "line", "period", "funds_received", "expenditure", "comment"]
        widgets = {"period": forms.DateInput(attrs={"type": "date"}),
                   "comment": forms.Textarea(attrs={"rows": 1})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["line"].queryset = FinanceBudgetLine.objects.select_related("budget").all()


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
