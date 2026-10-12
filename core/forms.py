import os
from django import forms
from django.forms import inlineformset_factory

from mne.monitoring.models import Location, Project
from .models import Resource
from .project_models import ActivityConceptNote, ProjectActivity, ProjectBudget, ProjectDocument, ProjectSubmission, StakeholderUpdate, TeamMeeting

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        exclude = ["duration_days"]
        fields = ['name', 'code', 'donor', 'program_area', 'project_head', 'project_accountant', 'project_officer', 'start_date', 'end_date']
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
            'program_area': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class ProjectDocumentForm(forms.ModelForm):
    class Meta:
        model = ProjectDocument
        fields = ["file", "workplan_period", "activities_count", "report_type", "activity"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "workplan_period": forms.Select(attrs={"class": "form-control"}),
            "activities_count": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "report_type": forms.Select(attrs={"class": "form-control"}),
            "activity": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, document_type=None, **kwargs):
        self.document_type = document_type
        project = kwargs.pop("project", None)
        self.project = project
        super().__init__(*args, **kwargs)
        if document_type == ProjectDocument.WORKPLAN:
            self.fields["workplan_period"].required = True
            self.fields["activities_count"].required = False
            self.fields["report_type"].required = False
            self.fields["activity"].required = False
        elif document_type == ProjectDocument.REPORT:
            self.fields["report_type"].required = True
            self.fields["activity"].required = True
            self.fields["activity"].queryset = ProjectActivity.objects.filter(
                workplan__project=project,
                confirmed=True,
            ).order_by("start_date", "name") if project else ProjectActivity.objects.none()
            self.fields["workplan_period"].required = False
            self.fields["activities_count"].required = False

    def clean(self):
        cleaned = super().clean()
        if self.document_type == ProjectDocument.WORKPLAN:
            cleaned["report_type"] = ""
            cleaned["activity"] = None
            cleaned["activities_count"] = None
        elif self.document_type == ProjectDocument.REPORT:
            cleaned["workplan_period"] = ""
            cleaned["activities_count"] = None
            activity = cleaned.get("activity")
            if activity and self.project and activity.workplan.project_id != self.project.pk:
                self.add_error("activity", "Select an activity from this project.")
        return cleaned


class ProjectActivityForm(forms.ModelForm):
    class Meta:
        model = ProjectActivity
        fields = ["code", "name", "start_date", "end_date"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_date") and cleaned.get("end_date") and cleaned["end_date"] < cleaned["start_date"]:
            raise forms.ValidationError("Activity end date cannot be before its start date.")
        return cleaned


class ActivityConceptNoteForm(forms.ModelForm):
    tasks_text = forms.CharField(required=False, label="Tasks (one per line: task | date | person responsible)", widget=forms.Textarea(attrs={"class": "form-control", "rows": 5}))
    budget_lines_text = forms.CharField(required=False, label="Budget lines (one per line: item | unit | qty | frequency | unit cost | amount)", widget=forms.Textarea(attrs={"class": "form-control", "rows": 6}))

    class Meta:
        model = ActivityConceptNote
        fields = [
            "project_name", "activity_code", "activity_name", "core_program_area",
            "outcome_result_area", "activity_start_date", "activity_end_date",
            "activity_venue", "concept_date", "background", "objectives", "methodology",
            "expected_outputs", "inputs_required", "cross_cutting_themes",
            "safeguarding_integration", "aap_integration", "total_amount_in_words",
        ]
        widgets = {
            "activity_start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "activity_end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "concept_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "outcome_result_area": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "background": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "objectives": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "methodology": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "expected_outputs": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "inputs_required": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "cross_cutting_themes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "safeguarding_integration": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "aap_integration": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "total_amount_in_words": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, activity=None, **kwargs):
        self.activity = activity or getattr(kwargs.get("instance"), "activity", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            if "form-control" not in existing and not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs["class"] = f"{existing} form-control".strip()
        if self.activity and not self.instance.pk:
            project = self.activity.workplan.project
            self.initial.setdefault("project_name", project.name)
            self.initial.setdefault("activity_code", self.activity.code)
            self.initial.setdefault("activity_name", self.activity.name)
            self.initial.setdefault("core_program_area", project.program_area.name if project.program_area_id else "")
            self.initial.setdefault("activity_start_date", self.activity.start_date)
            self.initial.setdefault("activity_end_date", self.activity.end_date)
        self.initial.setdefault("tasks_text", "\n".join(" | ".join(str(row.get(key, "")) for key in ("task", "date", "person")) for row in (self.instance.tasks or [])))
        self.initial.setdefault("budget_lines_text", "\n".join(" | ".join(str(row.get(key, "")) for key in ("item", "unit", "qty", "freq", "unit_cost", "amount")) for row in (self.instance.budget_lines or [])))

    @staticmethod
    def _rows(value, keys):
        if not value.strip():
            return []
        return [dict(zip(keys, [part.strip() for part in line.split("|")])) for line in value.splitlines() if line.strip()]

    def clean(self):
        cleaned = super().clean()
        cleaned["tasks"] = self._rows(cleaned.get("tasks_text", ""), ("task", "date", "person"))
        cleaned["budget_lines"] = self._rows(cleaned.get("budget_lines_text", ""), ("item", "unit", "qty", "freq", "unit_cost", "amount"))
        if cleaned.get("activity_start_date") and cleaned.get("activity_end_date") and cleaned["activity_end_date"] < cleaned["activity_start_date"]:
            self.add_error("activity_end_date", "Activity end date cannot be before its start date.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tasks = self.cleaned_data.get("tasks", [])
        instance.budget_lines = self.cleaned_data.get("budget_lines", [])
        if commit:
            instance.save()
        return instance


class ActivityConceptNoteUploadForm(forms.ModelForm):
    class Meta:
        model = ActivityConceptNote
        fields = ["uploaded_file"]
        widgets = {"uploaded_file": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".doc,.docx,.pdf"})}

    def clean_uploaded_file(self):
        uploaded_file = self.cleaned_data["uploaded_file"]
        if not uploaded_file.name.lower().endswith((".doc", ".docx", ".pdf")):
            raise forms.ValidationError("Upload the completed concept note as a Word document or PDF.")
        return uploaded_file


ProjectActivityFormSet = inlineformset_factory(
    ProjectDocument,
    ProjectActivity,
    form=ProjectActivityForm,
    extra=1,
    can_delete=True,
)


class StakeholderUpdateForm(forms.ModelForm):
    class Meta:
        model = StakeholderUpdate
        fields = [
            "date", "stakeholder_name", "category", "designation", "contact",
            "engagement_method", "follow_up_status", "update_summary", "action_points", "responsible_person",
            "deadline",  "remarks",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "deadline": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "update_summary": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "action_points": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "stakeholder_name": forms.TextInput(attrs={"class": "form-control",}),
            "category": forms.Select(attrs={"class": "form-control",}),
            "designation": forms.TextInput(attrs={"class": "form-control",}),
            "contact": forms.TextInput(attrs={"class": "form-control",}),
            "responsible_person": forms.TextInput(attrs={"class": "form-control",}),
            "engagement_method": forms.Select(attrs={"class": "form-control",}),
            "follow_up_status": forms.Select(attrs={"class": "form-control",}),
        }


class TeamMeetingForm(forms.ModelForm):
    class Meta:
        model = TeamMeeting
        fields = [
            "meeting_date", "start_time", "end_time", "chairperson", "area_of_support", "key_action_items",
            "minute_taker", "participants_m_f", "timeline", "status", "person_responsible",
        ]
        widgets = {
            "meeting_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "end_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "key_action_items": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "area_of_support": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "person_responsible": forms.TextInput(attrs={"class": "form-control",}),
            "chairperson": forms.TextInput(attrs={"class": "form-control",}),
            "minute_taker": forms.TextInput(attrs={"class": "form-control",}),
            "participants_m_f": forms.TextInput(attrs={"class": "form-control",}),
            "status": forms.Select(attrs={"class": "form-control",}),
            "timeline": forms.TextInput(attrs={"class": "form-control",}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("start_time") and cleaned.get("end_time") and cleaned["end_time"] < cleaned["start_time"]:
            raise forms.ValidationError("Meeting end time cannot be before the start time.")
        return cleaned


class ProjectSubmissionForm(forms.ModelForm):
    class Meta:
        model = ProjectSubmission
        fields = ["document_type", "file", "reporting_period", "notes"]
        widgets = {
            "document_type": forms.Select(attrs={"class": "form-control"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "reporting_period": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. September 2026 or Q3 2026"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        document_type = cleaned.get("document_type")
        uploaded_file = cleaned.get("file")
        if uploaded_file:
            filename = uploaded_file.name.lower()
            if document_type == ProjectSubmission.NARRATIVE and not filename.endswith(".pdf"):
                self.add_error("file", "Narrative reports must be PDF files.")
            elif document_type == ProjectSubmission.FINANCIAL and not filename.endswith((".xls", ".xlsx")):
                self.add_error("file", "Financial reports must be Excel files (.xls or .xlsx).")
        return cleaned


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
