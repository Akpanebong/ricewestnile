from django import forms
from .models import Broadcast, PhotoGallery, GalleryPhoto


class BroadcastForm(forms.ModelForm):
    class Meta:
        model = Broadcast
        fields = ["title", "summary", "youtube_url", "cover_image", "starts_at", "ends_at", "is_live", "is_published"]
        widgets = {"starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
                   "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
                   "summary": forms.Textarea(attrs={"rows": 3}),
                   "youtube_url": forms.URLInput(attrs={"placeholder": "https://youtu.be/8ifDzdXmyCI"})
                   }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def _style_fields(self):
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"


class GalleryForm(forms.ModelForm):
    class Meta:
        model = PhotoGallery
        fields = ["project", "title", "description", "cover_image", "published"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class GalleryPhotoForm(forms.ModelForm):
    class Meta:
        model = GalleryPhoto
        fields = ["title", "image", "caption", "sort_order"]
        widgets = {"caption": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
