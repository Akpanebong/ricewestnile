from django.contrib import admin

from .models import (
    Notification,
    NotificationRecipient,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    list_display = (

        "title",

        "category",

        "source_app",

        "created_by",

        "created_at",

        "recipient_count",

    )

    list_filter = (

        "category",

        "source_app",

        "created_at",

    )

    search_fields = (

        "title",

        "message",

    )

    readonly_fields = (

        "slug",

        "created_at",

        "updated_at",

    )

    ordering = (

        "-created_at",

    )

    def recipient_count(self, obj):

        return obj.recipients.count()


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):

    list_display = (

        "notification",

        "recipient",

        "is_read",

        "read_at",

        "email_sent",

    )

    list_filter = (

        "is_read",

        "email_sent",

    )

    autocomplete_fields = (

        "notification",

        "recipient",

    )

    search_fields = (

        "notification__title",

        "recipient__username",

    )