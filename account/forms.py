from django import forms
from django.core.validators import RegexValidator
from .models import Profile, Department, ExitProcessStep
from django.forms import CheckboxInput
from hr_apps.HRapp.employee_models import (BankDetail, Dependant, EducationHistory,EmergencyContact, Employee, EmployeeAddress, EmployeeContact, EmployeePersonalInfo, WorkExperience,)
from django.forms import inlineformset_factory, modelformset_factory


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'head']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'head': forms.Select(attrs={'class': 'form-control'})
        }


class EmployeeUpdateForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "staff_id",
            "job_title",
            "supervised_by",
            "date_joined",
        ]
        widgets = {
            "date_joined": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        readonly_fields = set(kwargs.pop("readonly_fields", ()))
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            if name in readonly_fields:
                field.disabled = True
                field.widget.attrs.update({
                    "class": f"{field.widget.attrs.get('class', '')} bg-light text-muted".strip(),
                    "aria-readonly": "true",
                })

        self.fields['job_title'].widget.attrs.update({'placeholder': 'e.g. Software Engineer'})
        self.fields['staff_id'].widget.attrs.update({'placeholder': 'e.g. EMP-001'})

    def get_groups(self):
        return {
            "Employment": ["staff_id", "job_title", "supervised_by", "date_joined"],
        }


class EmployeePersonalInfoForm(forms.ModelForm):
    class Meta:
        model = EmployeePersonalInfo
        exclude = ("employee",)
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


class EmployeeAddressForm(forms.ModelForm):
    class Meta:
        model = EmployeeAddress
        exclude = ("employee",)
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }


class EmployeeContactForm(forms.ModelForm):
    class Meta:
        model = EmployeeContact
        exclude = ("employee",)


class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = EmergencyContact
        exclude = ("employee",)
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
        }


class DependantForm(forms.ModelForm):
    class Meta:
        model = Dependant
        exclude = ("employee",)
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }


class EducationHistoryForm(forms.ModelForm):
    class Meta:
        model = EducationHistory
        exclude = ("employee",)
        widgets = {
            "certifications": forms.Textarea(attrs={"rows": 2}),
        }


class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        exclude = ("employee",)
        widgets = {
            "skills": forms.Textarea(attrs={"rows": 2}),
            "years": forms.NumberInput(attrs={"type": "year"}),

        }


class BankDetailForm(forms.ModelForm):
    class Meta:
        model = BankDetail
        exclude = ("employee",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


EMPLOYEE_SINGLE_FORM_CLASSES = {
    "personal_info_form": EmployeePersonalInfoForm,
    "bank_detail_form": BankDetailForm,
}


EMPLOYEE_FORMSET_CLASSES = {
    "address_formset": inlineformset_factory(
        Employee,
        EmployeeAddress,
        form=EmployeeAddressForm,
        extra=1,
        can_delete=True,
    ),
    "contact_formset": inlineformset_factory(
        Employee,
        EmployeeContact,
        form=EmployeeContactForm,
        extra=1,
        can_delete=True,
    ),
    "emergency_contact_formset": inlineformset_factory(
        Employee,
        EmergencyContact,
        form=EmergencyContactForm,
        extra=1,
        can_delete=True,
    ),
    "dependant_formset": inlineformset_factory(
        Employee,
        Dependant,
        form=DependantForm,
        extra=1,
        can_delete=True,
    ),
    "education_history_formset": inlineformset_factory(
        Employee,
        EducationHistory,
        form=EducationHistoryForm,
        extra=1,
        can_delete=True,
    ),
    "work_experience_formset": inlineformset_factory(
        Employee,
        WorkExperience,
        form=WorkExperienceForm,
        extra=1,
        can_delete=True,
    ),
}


def style_employee_profile_forms(forms_or_formsets):
    for item in forms_or_formsets:
        forms = item.forms if hasattr(item, "forms") else [item]
        for form in forms:
            for field in form.fields.values():
                if field.widget.__class__.__name__ == "CheckboxInput":
                    field.widget.attrs.update({"class": "form-check-input"})
                elif field.widget.__class__.__name__ == "Select":
                    field.widget.attrs.update({"class": "form-select"})
                else:
                    field.widget.attrs.update({"class": "form-control"})


def get_employee_profile_form_sections(*, post_data=None, files=None, employee=None):
    personal_info = EmployeePersonalInfo.objects.filter(employee=employee).first()
    bank_detail = BankDetail.objects.filter(employee=employee).first()

    form_kwargs = {"data": post_data, "files": files} if post_data is not None else {}

    single_forms = {
        "personal_info_form": EmployeePersonalInfoForm(
            **form_kwargs,
            instance=personal_info,
            prefix="personal",
        ),
        "bank_detail_form": BankDetailForm(
            **form_kwargs,
            instance=bank_detail,
            prefix="bank",
        ),
    }

    formsets = {
        "address_formset": EMPLOYEE_FORMSET_CLASSES["address_formset"](
            post_data,
            files,
            instance=employee,
            prefix="addresses",
        ),
        "contact_formset": EMPLOYEE_FORMSET_CLASSES["contact_formset"](
            post_data,
            files,
            instance=employee,
            prefix="contacts",
        ),
        "emergency_contact_formset": EMPLOYEE_FORMSET_CLASSES["emergency_contact_formset"](
            post_data,
            files,
            instance=employee,
            prefix="emergency",
        ),
        "dependant_formset": EMPLOYEE_FORMSET_CLASSES["dependant_formset"](
            post_data,
            files,
            instance=employee,
            prefix="dependants",
        ),
        "education_history_formset": EMPLOYEE_FORMSET_CLASSES["education_history_formset"](
            post_data,
            files,
            instance=employee,
            prefix="education",
        ),
        "work_experience_formset": EMPLOYEE_FORMSET_CLASSES["work_experience_formset"](
            post_data,
            files,
            instance=employee,
            prefix="experience",
        ),
    }

    style_employee_profile_forms([*single_forms.values(), *formsets.values()])

    sections = [
        {
            "key": "personal",
            "number": "03",
            "title": "Personal Information",
            "description": "Bio data, identity numbers, and demographic information.",
            "icon": "fa-user-check",
            "form": single_forms["personal_info_form"],
        },
        {
            "key": "addresses",
            "number": "04",
            "title": "Addresses",
            "description": "Permanent, present, and office address records.",
            "icon": "fa-location-dot",
            "formset": formsets["address_formset"],
        },
        {
            "key": "contacts",
            "number": "05",
            "title": "Contact Channels",
            "description": "Personal, official, and home phone or email details.",
            "icon": "fa-address-book",
            "formset": formsets["contact_formset"],
        },
        {
            "key": "emergency",
            "number": "06",
            "title": "Emergency Contacts",
            "description": "People HR can contact in urgent situations.",
            "icon": "fa-kit-medical",
            "formset": formsets["emergency_contact_formset"],
        },
        {
            "key": "dependants",
            "number": "07",
            "title": "Dependants",
            "description": "Dependants attached to this employee profile.",
            "icon": "fa-people-roof",
            "formset": formsets["dependant_formset"],
        },
        {
            "key": "education",
            "number": "08",
            "title": "Education History",
            "description": "Academic qualifications and certifications.",
            "icon": "fa-graduation-cap",
            "formset": formsets["education_history_formset"],
        },
        {
            "key": "experience",
            "number": "09",
            "title": "Work Experience",
            "description": "Previous employers, positions, years, and skills.",
            "icon": "fa-briefcase",
            "formset": formsets["work_experience_formset"],
        },
        {
            "key": "banking",
            "number": "10",
            "title": "Banking Details",
            "description": "Payroll account and bank branch information.",
            "icon": "fa-building-columns",
            "form": single_forms["bank_detail_form"],
        },
    ]

    return single_forms, formsets, sections


class ProfileForm(forms.ModelForm):

    department = forms.ModelChoiceField(
        queryset=Department.objects.exclude(name='ED'),
        empty_label='--Choose Department--',
        help_text='Click <a target="_blank" href="/departments/create/">Add Department</a>'
    )

    class Meta:
        model = Profile
        fields = [
            'username', 'title', 'first_name', 'last_name',
            'email', 'program_area', 'phone',
            'profile_type', 'status', 'probation_starts', 'probation_ends',
             'department',  'unit', 'project', "is_CMT", 'can_review', 'address'
        ]
        widgets = {
            "probation_starts": forms.DateInput(attrs={"type": "date"}),
            "probation_ends": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        readonly_fields = set(kwargs.pop("readonly_fields", ()))
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if field.widget.__class__.__name__ == "CheckboxInput":
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

        self.fields['username'].widget.attrs.update({
            'readonly': False,
            'class': 'form-control bg-light'
        })

        self.fields['address'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2
        })

        self.fields['is_CMT'].widget = CheckboxInput()
        self.fields['is_CMT'].widget.attrs.update({'class': 'form-check-input'})

        for name in readonly_fields:
            if name not in self.fields:
                continue
            field = self.fields[name]
            field.disabled = True
            field.widget.attrs.update({
                "class": f"{field.widget.attrs.get('class', '')} bg-light text-muted".strip(),
                "aria-readonly": "true",
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if email:
            email = email.strip().lower()
            qs = Profile.objects.filter(email__iexact=email)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("This email is already in use.")

        return email

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        probation_starts = cleaned.get("probation_starts")
        probation_ends = cleaned.get("probation_ends")

        if status != "Probation":
            cleaned["probation_starts"] = None
            cleaned["probation_ends"] = None
            return cleaned

        if probation_starts and probation_ends and probation_ends < probation_starts:
            self.add_error("probation_ends", "Probation end date cannot be before start date.")

        return cleaned

    def get_groups(self):
        return {
            "Account Info": ["username", "email"],
            "Personal Info": ["first_name", "last_name", "title", "is_CMT"],
            "Work Info": ["department", "program_area", "profile_type", "status", "probation_starts", "probation_ends"],
            "Contact Info": ["phone", "address"],
        }


class ExitProcessStepUpdateForm(forms.ModelForm):
    class Meta:
        model = ExitProcessStep
        fields = ["status", "notes", "attachment"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["attachment"].widget.attrs.update({"class": "form-control"})


ExitProcessStepFormSet = modelformset_factory(
    ExitProcessStep,
    form=ExitProcessStepUpdateForm,
    extra=0,
    can_delete=False,
)
