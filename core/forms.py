import os
from django import forms
from django.forms import inlineformset_factory

from mne.monitoring.models import Location, Project
from .models import Resource
from .project_models import ProjectBudget

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        exclude = ["duration_days"]
        fields = ['name', 'code', 'donor', 'project_head', 'project_accountant', 'project_officer', 'start_date', 'end_date']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'project_head': forms.Select(attrs={'class': 'form-control'}),
            'project_accountant': forms.Select(attrs={'class': 'form-control'}),
            'project_officer': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Input Project Name'
            }),
            'donor': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class ProjectBudgetForm(forms.ModelForm):
    class Meta:
        model = ProjectBudget
        fields = ['fiscal_year', 'period', 'budget_amount']
        widgets = {
            'fiscal_year': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'period': forms.Select(attrs={'class': 'form-control'}),
            'budget_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fiscal_year'].initial = ProjectBudget.current_fiscal_year()

    def clean_fiscal_year(self):
        if self.instance and self.instance.pk:
            return self.instance.fiscal_year
        return ProjectBudget.current_fiscal_year()


ProjectBudgetFormSet = inlineformset_factory(
    Project,
    ProjectBudget,
    form=ProjectBudgetForm,
    extra=5,
    can_delete=True,
)


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = "__all__"


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ["title", "resource_type", "file", "description"]

    def clean(self):
        cleaned = super().clean()
        file = cleaned.get("file")
        resource_type = cleaned.get("resource_type")
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            if resource_type == "presentation" and ext not in [".ppt", ".pptx"]:
                raise forms.ValidationError("Presentations must be PowerPoint files (.ppt or .pptx).")
            if resource_type in ["report", "success_story"] and ext != ".pdf":
                raise forms.ValidationError("Reports and success stories must be PDF files.")
        return cleaned

