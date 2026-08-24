from django.contrib import admin

from .models import Control, Policy, DecisionRecord, StakeholderEngagement


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("policy_id", "title", "status", "approval_status", "next_review_date")
    list_filter = ("status", "approval_status", "category")
    search_fields = ("policy_id", "title")


@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    list_display = ("control_id", "title", "status", "effectiveness", "next_test_date")
    list_filter = ("status", "effectiveness", "control_type")
    search_fields = ("control_id", "title")


@admin.register(DecisionRecord)
class ControlAdmin(admin.ModelAdmin):
    list_display = ("title", "meeting_date")


@admin.register(StakeholderEngagement)
class ControlAdmin(admin.ModelAdmin):
    list_display = ("stakeholder_name", "source_area")
