from django import forms
from .models import Broadcast, PhotoGallery, GalleryPhoto, SocialMediaContent, Newsletter


class BroadcastForm(forms.ModelForm):
    class Meta:
        model = Broadcast
        fields = ["title", "summary", "media_url", "media_type", "cover_image", "published_date", "is_live", "is_published"]
        widgets = {"published_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
                   "summary": forms.Textarea(attrs={"rows": 3}),
                   "media_url": forms.URLInput(attrs={"placeholder": "https://example.com/media-link"})
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
        fields = ["year", "quarter", "project", "activity", "cover_image", "published"]

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
        self.fields["image"].label = "Google Drive photo link"
        self.fields["image"].widget = forms.URLInput(attrs={
            "class": "form-control",
            "placeholder": "https://drive.google.com/file/d/.../view?usp=sharing",
        })
        self.fields["image"].help_text = "Upload the photo to Google Drive, enable link sharing, then paste the link here."


class SocialMediaContentForm(forms.ModelForm):
    class Meta:
        model = SocialMediaContent
        fields = ["platform", "title", "content", "url", "published_at"]
        widgets = {"content": forms.Textarea(attrs={"rows": 4}), "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = Newsletter
        fields = ["year", "quarter", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean_file(self):
        file = self.cleaned_data["file"]
        if not file.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Newsletter files must be PDF documents.")
        return file
