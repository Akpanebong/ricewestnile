from django import forms
from .models import Policy, Control, DecisionRecord, StakeholderEngagement


class BaseStyledForm(forms.ModelForm):
    """
    Optional: auto-apply CSS if you don't want to use add_class everywhere
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})


class PolicyForm(BaseStyledForm):
    class Meta:
        model = Policy
        fields = "__all__"
        exclude = ["created_by", "approved", "rejection_reason", "approved_by", "approval_status", "status"]
        widgets = {
            'summary': forms.Textarea(attrs={'rows': 2}),
            'next_review_date': forms.DateInput(attrs={'type': 'date'}),
            'effective_date': forms.DateInput(attrs={'type': 'date'})
        }


class ControlForm(BaseStyledForm):
    class Meta:
        model = Control
        fields = "__all__"
        exclude = ["created_by", "approved", "approved_by", "approval_status",  "rejection_reason",]
        widgets = {
            'next_test_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2})
        }


class DecisionRecordForm(BaseStyledForm):
    class Meta:
        model = DecisionRecord
        fields = "__all__"
        exclude = ["created_by", "approved", "approved_by", "approval_status", "rejection_reason", ]
        widgets = {
            'meeting_date': forms.DateInput(attrs={'type': 'date'}),
            'resolution': forms.Textarea(attrs={'rows': 2})
        }


class StakeholderEngagementForm(BaseStyledForm):
    class Meta:
        model = StakeholderEngagement
        fields = "__all__"
        exclude = ["created_by", "status"]
        widgets = {
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
            'feedback': forms.Textarea(attrs={'rows': 2})
        }
