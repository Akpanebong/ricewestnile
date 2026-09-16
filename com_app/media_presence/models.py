from django.conf import settings
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone

from core.project_models import Project


class Broadcast(models.Model):
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    youtube_url = models.URLField(validators=[URLValidator()], help_text="YouTube watch or live link")
    cover_image = models.ImageField(upload_to="media/broadcasts/", blank=True, null=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)
    is_live = models.BooleanField(default=False, db_index=True)
    is_published = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="broadcasts_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_live", "-starts_at")

    def __str__(self):
        return self.title

    @property
    def status_label(self):
        if self.is_live:
            return "Live now"
        if self.starts_at and self.starts_at > timezone.now():
            return "Upcoming"
        return "Ended"


class PhotoGallery(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="photo_galleries")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="media/galleries/covers/", blank=True, null=True)
    published = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="galleries_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.project} - {self.title}"


class GalleryPhoto(models.Model):
    gallery = models.ForeignKey(PhotoGallery, on_delete=models.CASCADE, related_name="photos")
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to="media/galleries/photos/")
    caption = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "-uploaded_at")

    def __str__(self):
        return self.title
