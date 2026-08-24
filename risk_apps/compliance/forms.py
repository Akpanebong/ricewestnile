from django import forms
from django.forms import inlineformset_factory

from .models import *


class ComplianceFrameworkForm(forms.ModelForm):
    class Meta:
        model = ComplianceFramework
        fields = "__all__"
        exclude = ['created_by']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3})
        }


class ComplianceRequirementForm(forms.ModelForm):
    class Meta:
        model = ComplianceRequirement
        fields = "__all__"
        exclude = ['framework']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'evidence_required': forms.Textarea(attrs={'rows': 3}),
        }


class ComplianceDocumentForm(forms.ModelForm):
    class Meta:
        model = ComplianceDocument
        fields = ["file"]


ComplianceDocumentFormSet = inlineformset_factory(
    ComplianceRequirement,
    ComplianceDocument,
    form=ComplianceDocumentForm,
    extra=1,
    can_delete=True
)


class ComplianceTaskForm(forms.ModelForm):
    class Meta:
        model = ComplianceTask
        fields = [
            "due_date",
            "responsible",
            "status",
            "priority",
            "progress",
        ]


class ComplianceAssessmentForm(forms.ModelForm):
    class Meta:
        model = ComplianceAssessment
        exclude = ["requirement", "assessed_at"]
        widgets = {
            "score": forms.NumberInput(attrs={"class": "form-control"}),
            "gap": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "recommendation": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class PartnerDueDiligenceForm(forms.ModelForm):
    class Meta:
        model = PartnerDueDiligence
        fields = ['partner_name', 'governance_score', 'financial_capacity_score', 'compliance_score',
                  'risk_rating', 'status', 'start_date', 'end_date', 'donor_alignment_notes']
        widgets = {
                "financial_capacity_score": forms.NumberInput(attrs={"class": "form-control"}),
                "start_date": forms.DateInput(attrs={"class": "form-control", "type": 'date'}),
                "end_date": forms.DateInput(attrs={"class": "form-control", "type": 'date'}),
                "donor_alignment_notes": forms.Textarea(attrs={"rows": 2}),
            }


class VendorDueDiligenceForm(forms.ModelForm):
    class Meta:
        model = VendorDueDiligence
        fields = ["vendor_name", "service_category", "legal_compliance_status", "financial_stability_score",
                  "risk_rating", "performance_status", "start_date", "end_date", "contract_ready", "ethical_screening_passed"]
        widgets = {
        "start_date": forms.DateInput(attrs={"class": "form-control", "type": 'date'}),
        "end_date": forms.DateInput(attrs={"class": "form-control", "type": 'date'}),
    }