from django.contrib import admin

from .models import CurrencyRate, Document,  Resource, SystemActivity
from .project_models import ActivityConceptNote, Project, ProjectActivity, ProjectBudget, ProjectDocument, ProjectSubmission, StakeholderUpdate, TeamMeeting

class ProjectBudgetInline(admin.TabularInline):
    model = ProjectBudget
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'donor', 'unit', 'project_head')
    search_fields = ('name', 'donor')
    inlines = [ProjectBudgetInline]
    readonly_fields = ["duration_days"]


@admin.register(ProjectBudget)
class ProjectBudgetAdmin(admin.ModelAdmin):
    list_display = ('project', 'fiscal_year', 'period', 'budget_amount')
    list_filter = ('fiscal_year', 'period')
    search_fields = ('project__name', 'fiscal_year')


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    list_display = ('project', 'document_type', 'workplan_period', 'report_type', 'activities_count', 'uploaded_by', 'uploaded_at')
    list_filter = ('document_type', 'workplan_period', 'report_type')
    search_fields = ('project__name', 'uploaded_by__username', 'uploaded_by__first_name', 'uploaded_by__last_name')


@admin.register(ProjectActivity)
class ProjectActivityAdmin(admin.ModelAdmin):
    list_display = ('name', 'workplan', 'start_date', 'end_date', 'confirmed', 'status')
    list_filter = ('confirmed', 'start_date', 'end_date')
    search_fields = ('name', 'workplan__project__name')


@admin.register(ActivityConceptNote)
class ActivityConceptNoteAdmin(admin.ModelAdmin):
    list_display = ('activity', 'status', 'source', 'created_by', 'reviewed_by', 'approved_by', 'updated_at')
    list_filter = ('status', 'source')
    search_fields = ('activity__name', 'activity__workplan__project__name', 'created_by__username')


admin.site.register(CurrencyRate)
admin.site.register(Document)
admin.site.register(Resource)
admin.site.register(SystemActivity)
admin.site.register(StakeholderUpdate)
admin.site.register(TeamMeeting)
admin.site.register(ProjectSubmission)
