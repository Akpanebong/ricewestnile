from django.contrib import admin
from .models import SubGroup, MonthlyPresentation, Report, ReportComment, FocusArea


class ReportCommentInline(admin.TabularInline):
    model = ReportComment
    extra = 0


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title','report_type','focus_area','status','date_sent')
    search_fields = ('title','report_type','focus_area','status','date_sent')
    list_filter = ('status',)
    inlines = [ReportCommentInline]


admin.site.register(SubGroup)
admin.site.register(MonthlyPresentation)
# admin.site.register(Report)
# admin.site.register(ReportComment)
admin.site.register(FocusArea)
