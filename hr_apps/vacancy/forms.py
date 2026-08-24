from django import forms

from account.models import Department, Unit
from .models import RecruitmentRequest, Applicant, JobOpening


class JobOpeningForm(forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = ['request', 'department', 'deadline', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Input message here.'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(),
            'deadline': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['request'].disabled = True


class RecruitmentRequestForm(forms.ModelForm):
    class Meta:
        model = RecruitmentRequest
        fields = ["title",  "unit", "justification", "attach_file",]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "justification": forms.Textarea(attrs={"class": "form-control","rows": 3,}),
            "attach_file": forms.FileInput(attrs={"class": "form-control"}),
            "unit": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user:
            units = Unit.objects.filter(head=user).order_by("name")
            self.fields["unit"].queryset = units

            if units.count() == 1:
                self.fields["unit"].initial = units.first()
                self.fields["unit"].widget = forms.HiddenInput()


class JobPublishForm(forms.Form):
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}))
    deadline = forms.DateField(widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))


class ApplicantForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = ["full_name", "email", "resume"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }



class ApplicantReviewForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = ["status", "interview_score", "interview_notes"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "interview_score": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "interview_notes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
