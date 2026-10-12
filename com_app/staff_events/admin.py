from django.contrib import admin

from .models import StaffEvent, StaffEventInvitation


@admin.register(StaffEvent)
class StaffEventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "starts_at", "created_by", "minutes")
    list_filter = ("event_type", "starts_at")
    search_fields = ("title", "description", "location")
    readonly_fields = ("created_at", "updated_at", "minutes_uploaded_at")


@admin.register(StaffEventInvitation)
class StaffEventInvitationAdmin(admin.ModelAdmin):
    list_display = ("event", "recipient", "kind", "email_sent", "sent_at")
    list_filter = ("kind", "email_sent")
    search_fields = ("event__title", "recipient__email", "recipient__username")
    readonly_fields = ("sent_at",)
