from django import forms
from .models import SubGroup
from .models import Report, ReportComment, MonthlyPresentation
from django.utils import timezone
from .utils import check_report_deadline


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['title','file','report_type','focus_area','sub_group','comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['focus_area'].required = True
        self.fields['sub_group'].required = True

    def clean(self):
        cleaned = super().clean()
        report_type = cleaned.get('report_type')
        date_now = timezone.now()
        allowed, message = check_report_deadline(report_type, date_now)
        if not allowed:
            raise forms.ValidationError(message)
        return cleaned


class ReportCommentForm(forms.ModelForm):
    class Meta:
        model = ReportComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        }


class ReportReviewForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['status','comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        }


class PresentationForm(forms.ModelForm):
    class Meta:
        model = MonthlyPresentation
        fields = ['file', 'program_area', 'comment']
        widgets = {
            'program_area': forms.Select(attrs={'required': True, 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['program_area'].required = True


class PresentationReplyForm(forms.ModelForm):
    class Meta:
        model = MonthlyPresentation
        fields = ['reply']
        widgets = {
            'reply': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        }


class SubGroupForm(forms.ModelForm):
    class Meta:
        model = SubGroup
        fields = ['name', 'leader']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter subgroup name'}),
            'leader': forms.Select(attrs={'class': 'form-select'}),
        }
