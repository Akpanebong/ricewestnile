from django.conf import settings
from django.core.validators import URLValidator
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import re
from urllib.parse import parse_qs, urlparse

from core.project_models import Project


class Broadcast(models.Model):
    MEDIA_TYPE_CHOICES = (
        ("radio", "Radio"),
        ("television", "Television"),
        ("podcast", "Podcast"),
        ("webinar", "Webinar"),
        ("livestream", "Live stream"),
        ("newspaper", "Newspaper"),
        ("other", "Other"),
    )

    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    media_url = models.URLField(validators=[URLValidator()], help_text="Link to the broadcast on its streaming or media platform")
    media_type = models.CharField(max_length=20, default="newspaper")
    cover_image = models.ImageField(upload_to="media/broadcasts/", blank=True, null=True)
    published_date = models.DateTimeField(default=timezone.now)
    is_live = models.BooleanField(default=False, db_index=True)
    is_published = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="broadcasts_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_live", "-published_date")

    def __str__(self):
        return self.title

    @property
    def status_label(self):
        if self.is_live:
            return "Live now"
        return "Published"


class PhotoGallery(models.Model):
    QUARTER_CHOICES = ((1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4"))

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="photo_galleries")
    year = models.PositiveIntegerField(default=timezone.now().year, db_index=True)
    quarter = models.PositiveSmallIntegerField(choices=QUARTER_CHOICES, default=1, db_index=True)
    activity = models.CharField(max_length=200, default="General Activity", help_text="Activity name, for example: Farmer field demonstration")
    cover_image = models.ImageField(upload_to="media/galleries/covers/", blank=True, null=True)
    published = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="galleries_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-year", "quarter", "project__name", "activity")
        indexes = [models.Index(fields=("year", "quarter", "project"))]

    def __str__(self):
        return f"{self.year} Q{self.quarter} - {self.project} - {self.activity}"


def gallery_photo_upload_path(instance, filename):
    project_slug = slugify(instance.gallery.project.name) or str(instance.gallery.project_id)
    activity_slug = slugify(instance.gallery.activity) or str(instance.gallery.pk)
    return f"media/galleries/{instance.gallery.year}/Q{instance.gallery.quarter}/{project_slug}/{activity_slug}/{filename}"


class GalleryPhoto(models.Model):
    gallery = models.ForeignKey(PhotoGallery, on_delete=models.CASCADE, related_name="photos")
    title = models.CharField(max_length=200)
    image = models.URLField(help_text="Paste a publicly accessible Google Drive sharing link to the photo")
    caption = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "-uploaded_at")

    def __str__(self):
        return self.title

    @property
    def display_url(self):
        """Convert a Google Drive file-sharing URL into a browser image URL."""
        raw_url = self.image or ""
        match = re.search(r"/(?:file/d|d)/([^/?]+)", raw_url)
        file_id = match.group(1) if match else parse_qs(urlparse(raw_url).query).get("id", [None])[0]
        if file_id and "drive.google.com" in raw_url:
            return f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
        return raw_url


class SocialMediaContent(models.Model):
    TRACKING_STATUS_CHOICES = (
        ("planned", "Planned"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
        ("unknown", "Unknown"),
    )
    PLATFORM_CHOICES = (
        ("twitter", "Twitter / X"),
        ("whatsapp", "WhatsApp"),
        ("facebook", "Facebook"),
        ("linkedin", "LinkedIn"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("other", "Other"),
    )

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    url = models.URLField(blank=True)
    published_at = models.DateTimeField(default=timezone.now)
    tracking_status = models.CharField(max_length=20, choices=TRACKING_STATUS_CHOICES, default="unknown")
    post_identifier = models.CharField(max_length=255, blank=True)
    source_key = models.CharField(max_length=255, unique=True, null=True, blank=True, editable=False)
    source_data = models.JSONField(default=dict, blank=True, editable=False)
    last_synced_at = models.DateTimeField(null=True, blank=True, editable=False)
    week_number = models.CharField(max_length=20, blank=True, editable=False)
    topic_type = models.CharField(max_length=255, blank=True)
    project = models.CharField(max_length=255, blank=True)
    media_visual_type = models.CharField(max_length=100, blank=True)
    views_count = models.PositiveBigIntegerField(null=True, blank=True)
    likes_count = models.PositiveBigIntegerField(null=True, blank=True)
    dislikes_count = models.PositiveBigIntegerField(null=True, blank=True)
    comments_count = models.PositiveBigIntegerField(null=True, blank=True)
    shares_count = models.PositiveBigIntegerField(null=True, blank=True)
    metrics_synced_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="social_media_content_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-published_at", "-created_at")
        verbose_name = "Social media content"

    def __str__(self):
        return f"{self.get_platform_display()}: {self.title}"


class SocialMediaSyncState(models.Model):
    provider = models.CharField(max_length=20, unique=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    posts_fetched = models.PositiveIntegerField(default=0)
    posts_created = models.PositiveIntegerField(default=0)
    posts_updated = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("provider",)

    def __str__(self):
        return f"{self.provider} social media sync"


class Newsletter(models.Model):
    year = models.PositiveIntegerField()
    quarter = models.PositiveSmallIntegerField(choices=((1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")))
    file = models.FileField(upload_to="media/newsletters/", validators=[FileExtensionValidator(["pdf"])])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-year", "-quarter", "-created_at")
        constraints = [models.UniqueConstraint(fields=("year", "quarter"), name="unique_newsletter_year_quarter")]

    def __str__(self):
        return f"{self.year} Q{self.quarter} Newsletter"
