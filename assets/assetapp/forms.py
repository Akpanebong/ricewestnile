from django import forms
from .models import Asset


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