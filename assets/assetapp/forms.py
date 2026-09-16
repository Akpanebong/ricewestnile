from django import forms
from .models import Asset, AssetDisposalRequest, WeeklyVehiclePlan, VehicleAssignment


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['asset_no', 'date_of_entry', 'category', 'purchase_value', 'allocation', 'serial_no',
                  'chasis_no', 'engine_no', 'place', 'mode_of_acquisition', 'additions', 'usage_years',
                  'depreciation_rate', 'write_offs', 'description',  'comments',
                  ]
        widgets = {
            'date_of_entry': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'mode_of_acquisition': forms.Select(attrs={'class': 'form-control'}),
        }


class AssetDisposalForm(forms.ModelForm):
    class Meta:
        model = AssetDisposalRequest
        fields = ["reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 4, "class": "form-control"})}


class WeeklyVehiclePlanForm(forms.ModelForm):
    class Meta:
        model = WeeklyVehiclePlan
        fields = ["week_start", "notes"]
        widgets = {"week_start": forms.DateInput(attrs={"type": "date", "class": "form-control"}), "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control"})}


class VehicleAssignmentForm(forms.ModelForm):
    class Meta:
        model = VehicleAssignment
        fields = ["vehicle", "driver", "location", "purpose", "notes"]
        widgets = {
            "purpose": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "driver": forms.Select(attrs={"class": "form-control"}),
            "vehicle": forms.Select(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
                   }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Asset.objects.filter(category="VEHICLE")
