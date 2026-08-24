from django.contrib import admin
from .models import AuditFinding, AuditLog, AuditEvidence, ExternalAuditFinding, ExternalAuditEngagement


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("title", "audit_type", "status", "start_date", "end_date")
    list_filter = ("audit_type", "status")
    search_fields = ("title", "scope")


@admin.register(AuditFinding)
class AuditFindingAdmin(admin.ModelAdmin):
    list_display = ("title", "audit", "severity", "status", "due_date", "updated_at")
    list_filter = ("severity", "status")
    search_fields = ("title", "issue")


admin.site.register(ExternalAuditEngagement)
admin.site.register(AuditEvidence)
admin.site.register(ExternalAuditFinding)
