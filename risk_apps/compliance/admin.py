from django.contrib import admin

from .models import ComplianceRequirement, ComplianceFramework, ComplianceDocument, ComplianceAssessment,\
    ComplianceTask, PartnerDueDiligence, VendorDueDiligence


@admin.register(ComplianceRequirement)
class ComplianceRecordAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "framework", "level", "owner"]
    list_filter = ("framework", "level")
    search_fields = ("title", "framework__name", "code")


admin.site.register(ComplianceFramework)
admin.site.register(ComplianceDocument)
admin.site.register(ComplianceAssessment)
admin.site.register(ComplianceTask)
admin.site.register(PartnerDueDiligence)
admin.site.register(VendorDueDiligence)
