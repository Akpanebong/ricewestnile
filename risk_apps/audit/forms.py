from django import forms
from django.forms import inlineformset_factory
from .models import (
    AuditLog, AuditFinding, AuditEvidence,
    ExternalAuditEngagement, ExternalAuditFinding
)


class AuditLogForm(forms.ModelForm):
    class Meta:
        model = AuditLog
        fields = "__all__"
        exclude = ['created_by']
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "scope": forms.Textarea(attrs={"rows": 3}),
        }


class AuditFindingForm(forms.ModelForm):
    class Meta:
        model = AuditFinding
        fields = "__all__"
        exclude = ['created_by', 'audit']
        widgets = {
            "issue": forms.Textarea(attrs={"rows": 2}),
            "recommendation": forms.Textarea(attrs={"rows": 2}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }


class AuditEvidenceForm(forms.ModelForm):
    class Meta:
        model = AuditEvidence
        fields = "__all__"
        exclude = ['created_by', 'audit', "uploaded_by"]


class ExternalAuditEngagementForm(forms.ModelForm):
    class Meta:
        model = ExternalAuditEngagement
        fields = "__all__"
        exclude = ['created_by']
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "shared_data_scope": forms.Textarea(attrs={'rows': 2}),
            "scope": forms.Textarea(attrs={'rows': 2})
        }


class ExternalAuditFindingForm(forms.ModelForm):
    class Meta:
        model = ExternalAuditFinding
        fields = "__all__"
        exclude = ['created_by']
        widgets = {
            "recommendation": forms.Textarea(attrs={'rows': 2})
        }


AuditFindingFormSet = inlineformset_factory(
    AuditLog,
    AuditFinding,
    form=AuditFindingForm,
    extra=1,
    can_delete=True
)

AuditEvidenceFormSet = inlineformset_factory(
    AuditLog,
    AuditEvidence,
    form=AuditEvidenceForm,
    extra=1,
    can_delete=True
)


ExternalFindingFormSet = inlineformset_factory(
    ExternalAuditEngagement,
    ExternalAuditFinding,
    form=ExternalAuditFindingForm,
    extra=1,
    can_delete=True
)
