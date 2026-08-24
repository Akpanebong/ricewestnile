from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model

from account.models import Profile
from core.project_models import ProjectBudget, Project
from .models import (
    ProcurementPlan, ProcurementPlanItem, Supplier, SupplierSpendReport,
    Requisition, RequisitionItem, RFQ, Product, PurchaseOrder
)

User = get_user_model()


class ProcurementPlanForm(forms.ModelForm):

    class Meta:
        model = ProcurementPlan
        fields = ['number', 'project', 'donor', 'fiscal_year', 'budget_period']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'project': forms.Select(attrs={'class': 'form-control'}),
            'donor': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'fiscal_year': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'budget_period': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('project'):
            raise forms.ValidationError("A procurement plan must be linked to a project.")
        project = cleaned.get('project')
        fiscal_year = cleaned.get('fiscal_year')

        if project:
            cleaned['donor'] = project.donor

        if project and not fiscal_year:
            fiscal_year = ProjectBudget.current_fiscal_year()
            if not ProjectBudget.objects.filter(project=project, fiscal_year=fiscal_year).exists():
                project_budget = ProjectBudget.objects.filter(project=project).order_by('-fiscal_year').first()
                if project_budget:
                    fiscal_year = project_budget.fiscal_year
            cleaned['fiscal_year'] = fiscal_year

        if not cleaned.get('fiscal_year'):
            raise forms.ValidationError("A procurement plan must include a fiscal year.")
        return cleaned

    def clean_project(self):
        project = self.cleaned_data.get("project")
        user = getattr(self, "user", None)
        if user and project and project.project_head != user:
            raise forms.ValidationError(
                "You can only create procurement plans for projects you head."
            )
        return project

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["project"].queryset = Project.objects.none()

        if self.user and self.user.is_authenticated:
            self.fields["project"].queryset = (Project.objects.filter(project_head=self.user).order_by("name"))
            self.fields["project"].empty_label = "Select Project"


class ProcurementPlanItemForm(forms.ModelForm):
    class Meta:
        model = ProcurementPlanItem
        fields = ['product', 'description', 'qty', 'est_unit_cost', 'delivery_date', 'unit_measure']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control product-field'}),
            'unit_measure': forms.TextInput(attrs={'class': 'form-control'}),
            'qty': forms.NumberInput(attrs={'class': 'form-control qty-field', 'step': '0.01'}),
            'est_unit_cost': forms.NumberInput(attrs={'class': 'form-control cost-field', 'step': '0.01'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
        }


ProcurementPlanItemFormSet = forms.inlineformset_factory(
    ProcurementPlan,
    ProcurementPlanItem,
    form=ProcurementPlanItemForm,
    extra=1,
    can_delete=True
)


class RFQForm(forms.ModelForm):
    class Meta:
        model = RFQ
        fields = ['supplier', 'deadline']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': True}),
            'supplier': forms.SelectMultiple(attrs={'class': 'form-control'}),

        }


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['final_amount', 'due_date', 'remarks', 'supplier']
        widgets = {
            'final_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': '3'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),

        }

    def __init__(self, *args, **kwargs):
        rfq = kwargs.pop('rfq', None)
        supplier = kwargs.pop('supplier', None)
        super().__init__(*args, **kwargs)
        if rfq:
            self.fields['supplier'].queryset = rfq.supplier.all()
        if supplier:
            self.fields['supplier'].initial = supplier
            self.fields['supplier'].disabled = True


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'est_unit_cost': forms.NumberInput(attrs={'class': 'form-control','placeholder':'Product price'}),
            'name': forms.TextInput(attrs={'class': 'form-control','placeholder':'Product name'}),
            'category': forms.TextInput(attrs={'class': 'form-control','placeholder':'Product category'}),
        }


class SupplierRegistrationForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['title','full_name', 'email', 'contact_person', 'organisation_name',
                  'phone','address','tin_number','documents']
        widgets = {
            'address': forms.Textarea(attrs={'class':'form-control','rows':2}),
            'full_name': forms.TextInput(attrs={'class':'form-control'}),
            'organisation_name': forms.TextInput(attrs={'class':'form-control'}),
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'email': forms.EmailInput(attrs={'class':'form-control'}),
            'contact_person': forms.TextInput(attrs={'class':'form-control'}),
            'phone': forms.TextInput(attrs={'class':'form-control'}),
            'tin_number': forms.NumberInput(attrs={'class':'form-control'}),
            'documents': forms.FileInput(attrs={'class':'form-control', 'type': 'file'}),
                   }


class RequisitionForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ['number', 'procurement', 'activity_name', 'date']
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'procurement': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'activity_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        queryset = ProcurementPlan.objects.filter(status="Approved", project__project_officer=self.user)

        if self.user and not self.user.is_superuser:
            profile = Profile.objects.get(user=self.user)
            queryset = queryset.filter(project__project_officer=profile)

        self.fields["procurement"].queryset = queryset.select_related("project",
            "project__project_officer",)
        self.fields["procurement"].empty_label = "Select Procurement Plan"

    def clean_number(self):
        number = self.cleaned_data.get('number', '').strip()

        # Replace forward slashes with hyphens
        number = number.replace('/', '-')

        return number


RequisitionItemFormSet = inlineformset_factory(
    Requisition, RequisitionItem,
    fields=('procurement_item','description','unit_measure','qty','unit_price','delivery_date'),
    widgets={
        'procurement_item': forms.Select(attrs={'class':'form-control plan-item-field'}),
        'description': forms.TextInput(attrs={'class':'form-control'}),
        'unit_measure': forms.TextInput(attrs={'class':'form-control'}),
        'qty': forms.NumberInput(attrs={'class':'form-control'}),
        'unit_price': forms.NumberInput(attrs={'class':'form-control'}),
        'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),

    },
    extra=0, can_delete=True
)



class SupplierSpendReportUpdateForm(forms.ModelForm):
    class Meta:
        model = SupplierSpendReport
        fields = [
            'invoice_no',
            'invoice_date',
            'invoice_amount',
            'payment_status',
        ]

        widgets = {
            'invoice_date': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'invoice_no': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'invoice_amount': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),
            'payment_status': forms.Select(
                attrs={'class': 'form-select'}
            ),
        }
