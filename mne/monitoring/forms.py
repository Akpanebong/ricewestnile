from django import forms

from .models import DataEntry, StrategicObjective, Indicator, Output

class DataEntryForm(forms.ModelForm):
    class Meta:
        model = DataEntry
        fields = [
            'indicator', 'project', 'location', 'program_area', 'donor', 'year', 'month', 'sex', 'status',
            'pwd', 'pwd_nationals', 'pwd_refugees', 'pwd_national_males', 'pwd_refugee_males',
            'pwd_national_females', 'pwd_refugee_females', 'enterprise_type',
            'no_of_enterprise', 'no_of_group_reached', 'no_of_group_members',
            'no_male', 'no_female', 'value', 'program_area', 'notes'
        ]
        widgets = {
            'indicator': forms.HiddenInput(),
            'year': forms.NumberInput(attrs={'min':2000,'max':2100}),
            'month': forms.NumberInput(attrs={'min':1,'max':12}),
            'notes': forms.Textarea(attrs={
                'placeholder': 'Enter additional note here...',
                'rows': 2,
                'cols': 2
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        no_male = cleaned_data.get('no_male') or 0
        no_female = cleaned_data.get('no_female') or 0
        no_of_group_members = cleaned_data.get('no_of_group_members') or 0
        pwd_male = (cleaned_data.get('pwd_national_males') or 0) + (cleaned_data.get('pwd_refugee_males') or 0)
        pwd_female = (cleaned_data.get('pwd_national_females') or 0) + (cleaned_data.get('pwd_refugee_females') or 0)
        pwd_total = sum(
            cleaned_data.get(field) or 0
            for field in [
                'pwd_nationals',
                'pwd_refugees',
                'pwd_national_males',
                'pwd_refugee_males',
                'pwd_national_females',
                'pwd_refugee_females',
            ]
        )

        if no_male + no_female != no_of_group_members:
            self.add_error(
                'no_of_group_members',
                "Group members must equal no. of males + no. of females."
            )
        if pwd_male > no_male:
            self.add_error('pwd_national_males', "PWD males cannot exceed total males.")
            self.add_error('pwd_refugee_males', "PWD males cannot exceed total males.")
        if pwd_female > no_female:
            self.add_error('pwd_national_females', "PWD females cannot exceed total females.")
            self.add_error('pwd_refugee_females', "PWD females cannot exceed total females.")
        if pwd_total and cleaned_data.get('pwd') not in [None, pwd_total]:
            cleaned_data['pwd'] = pwd_total

        return cleaned_data




class IndicatorForm(forms.ModelForm):
    class Meta:
        model = Indicator
        fields = ["code", "name", "unit_of_measure", "description"]


class StrategicObjectiveForm(forms.ModelForm):
    class Meta:
        model = StrategicObjective
        fields = ["code", "title", "description"]


class OutputForm(forms.ModelForm):
    class Meta:
        model = Output
        exclude = ["so"]

