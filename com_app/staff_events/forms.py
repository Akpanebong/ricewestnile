from django import forms

from .models import StaffEvent


class StaffEventForm(forms.ModelForm):
    class Meta:
        model = StaffEvent
        fields = ("title", "description", "location", "starts_at", "ends_at")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        for name in ("starts_at", "ends_at"):
            self.fields[name].input_formats = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S")


class MinutesUploadForm(forms.ModelForm):
    class Meta:
        model = StaffEvent
        fields = ("minutes",)
        widgets = {"minutes": forms.FileInput(attrs={"accept": "application/pdf,.pdf", "class": "form-control"})}
