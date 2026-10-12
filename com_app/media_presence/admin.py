from django.contrib import admin
from .models import Broadcast, PhotoGallery, GalleryPhoto, SocialMediaContent, SocialMediaSyncState, Newsletter


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "is_live", "published_date", "is_published")
    list_filter = ("media_type", "is_live", "is_published")
    search_fields = ("title", "summary")


class GalleryPhotoInline(admin.TabularInline):
    model = GalleryPhoto
    extra = 1


@admin.register(PhotoGallery)
class PhotoGalleryAdmin(admin.ModelAdmin):
    list_display = ("year", "quarter", "project", "activity", "published", "created_at")
    list_filter = ("year", "quarter", "published", "project")
    inlines = [GalleryPhotoInline]


@admin.register(SocialMediaContent)
class SocialMediaContentAdmin(admin.ModelAdmin):
    list_display = ("platform", "title", "tracking_status", "published_at", "views_count", "likes_count", "comments_count", "last_synced_at")
    list_filter = ("platform", "tracking_status")
    search_fields = ("title", "content", "post_identifier", "project", "topic_type")


@admin.register(SocialMediaSyncState)
class SocialMediaSyncStateAdmin(admin.ModelAdmin):
    list_display = ("provider", "last_success_at", "posts_fetched", "posts_created", "posts_updated", "last_error")
    readonly_fields = ("provider", "last_started_at", "last_success_at", "last_error", "posts_fetched", "posts_created", "posts_updated")


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ("year", "quarter", "file", "created_at")
    list_filter = ("year", "quarter")
