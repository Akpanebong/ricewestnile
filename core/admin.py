from django.contrib import admin

from .models import CurrencyRate, Document,  Resource, SystemActivity
from .project_models import Project, ProjectBudget

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


admin.site.register(CurrencyRate)
admin.site.register(Document)
admin.site.register(Resource)
admin.site.register(SystemActivity)

