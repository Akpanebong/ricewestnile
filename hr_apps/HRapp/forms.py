from notification.models import Notification
from .models import Leave, Attendance, Training,\
    ForumThread, ForumPost, SituationReport
from django import forms
from hr_apps.HRapp.employee_models import Employee
from .orientation_models import OrientationPlan, OrientationSession
from account.models import Department, Unit


class EmployeeForm(forms.ModelForm):

    class Meta:
        model = Employee
        fields = ['user', 'job_title', 'staff_id', 'supervised_by', 'date_joined',
                  ]
        widgets = {
            'user': forms.Select(attrs={
                'class': 'form-control'
            }),
            'district': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter district'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Employee Address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Employee City.'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Employee Postal code'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter job title'
            }),
            'staff_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Staff ID'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'date_joined': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }


class LeaveForm(forms.ModelForm):
    class Meta:
        model = Leave
        fields = ["leave_type", "special_type", "start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "leave_type": forms.Select(attrs={"class": "form-control"}),
            "special_type": forms.Select(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        s = cleaned.get("start_date")
        e = cleaned.get("end_date")
        leave_type = cleaned.get("leave_type")
        special_type = cleaned.get("special_type")
        reason = cleaned.get("reason")
        if s and e and e < s:
            raise forms.ValidationError("End date cannot be before start date.")

        if leave_type and leave_type.is_special:
            if not special_type:
                self.add_error("special_type", "Select special leave type")
            if not reason:
                self.add_error("reason", "Reason is required for special leave")
        else:
            cleaned["special_type"] = None
        return cleaned



class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['employee', 'status', 'latitude', 'longitude', 'address']
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address': forms.HiddenInput(),
            'employee': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Input message here.'
            }),
        }


class StaffAttendanceForm(forms.ModelForm):

    class Meta:
        model = Attendance
        fields = ['status', 'latitude', 'longitude', 'address']
        widgets = {
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'address': forms.HiddenInput(),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_latitude(self):
        lat = self.cleaned_data.get("latitude")
        if lat is not None:
            return round(float(lat), 6)
        return lat

    def clean_longitude(self):
        lon = self.cleaned_data.get("longitude")
        if lon is not None:
            return round(float(lon), 6)
        return lon


# Training Form
class TrainingForm(forms.ModelForm):
    class Meta:
        model = Training
        fields = ['title', 'start_date', 'end_date', 'description', 'participants']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': '3',
                'placeholder': 'Input message here.'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date'
            }),
            'participants': forms.CheckboxSelectMultiple(),


        }


class ForumThreadForm(forms.ModelForm):
    class Meta:
        model = ForumThread
        fields = ["title"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Thread title"})
        }


class ForumPostForm(forms.ModelForm):
    class Meta:
        model = ForumPost
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "placeholder": "Write your reply...", "rows": 3})
        }


class SituationReportForm(forms.ModelForm):
    class Meta:
        model = SituationReport
        fields = ["title", "description", "attachment"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter situation title"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Describe the situation in detail..."}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }


class UpdateSitrepStatusForm(forms.ModelForm):
    class Meta:
        model = SituationReport
        fields = ["status"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
        }



class OrientationPlanCreateForm(forms.ModelForm):
    units = forms.ModelMultipleChoiceField(
        queryset=Unit.objects.order_by("name"),
        required=True,
        widget=forms.CheckboxSelectMultiple(),
        help_text="Select units that must orient the staff member.",
    )

    class Meta:
        model = OrientationPlan
        fields = ["notes"]
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional HR notes for the orientation plan...",
                }
            ),
        }


class OrientationSessionScheduleForm(forms.ModelForm):
    class Meta:
        model = OrientationSession
        fields = ["scheduled_start", "scheduled_end"]
        widgets = {
            "scheduled_start": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "scheduled_end": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("scheduled_start")
        end = cleaned.get("scheduled_end")
        if start and end and end <= start:
            self.add_error("scheduled_end", "End time must be after start time.")
        return cleaned


class OrientationSessionCompleteForm(forms.ModelForm):
    class Meta:
        model = OrientationSession
        fields = ["completion_notes"]
        widgets = {
            "completion_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Completion notes (optional)...",
                }
            ),
        }
