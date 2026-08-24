from django.contrib import admin
from .models import StrategicObjective, Output, Indicator, Project, Location, DataEntry, CoreProgram


@admin.register(StrategicObjective)
class SOAdmin(admin.ModelAdmin):
    list_display = ('code','title')


@admin.register(Output)
class OutputAdmin(admin.ModelAdmin):
    list_display = ('code','title','so')
    list_filter = ('so',)


@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ('code','name','output')
    list_filter = ('output__so', 'output')



@admin.register(DataEntry)
class DataEntryAdmin(admin.ModelAdmin):
    list_display = (
        "indicator", "project", "location", "year", "month", "status",
        "no_male", "no_female", "pwd", "created_at", "slug",
    )
    list_filter = ("year", "month", "status", "sex", "enterprise_type", "project", "location")
    search_fields = ("indicator__code", "indicator__name", "project__name", "location__district")
    fieldsets = (
        (None, {
            "fields": ("indicator", "project", "program_area", "location", "donor", "year", "month", "status", "sex")
        }),
        ("Participants", {
            "fields": ("no_male", "no_female", "no_of_group_members", "no_of_group_reached")
        }),
        ("PWD Breakdown", {
            "fields": (
                "pwd", "pwd_nationals", "pwd_refugees", "pwd_national_males",
                "pwd_refugee_males", "pwd_national_females", "pwd_refugee_females",
            )
        }),
        ("Enterprise", {
            "fields": ("enterprise_type", "no_of_enterprise", "value", "notes", "created_by")
        }),
    )
    readonly_fields = ("created_at", "slug")


admin.site.register(CoreProgram)
admin.site.register(Location)
