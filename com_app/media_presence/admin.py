from django.contrib import admin
from .models import Broadcast, PhotoGallery, GalleryPhoto


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ("title", "is_live", "starts_at", "is_published")
    list_filter = ("is_live", "is_published")
    search_fields = ("title", "summary")


class GalleryPhotoInline(admin.TabularInline):
    model = GalleryPhoto
    extra = 1


@admin.register(PhotoGallery)
class PhotoGalleryAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "published", "created_at")
    list_filter = ("published", "project")
    inlines = [GalleryPhotoInline]
