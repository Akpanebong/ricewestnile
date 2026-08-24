from django.contrib import admin
from .models import (
    BusinessContinuityPlan,
    EnvironmentalSocialRisk,
    KeyRiskIndicator,
    RiskCategory,
    Risk,
    RiskControl,
    RiskIncident,
    RiskTreatment,
    Likelihood,
    Impact,
    Scenario,
    ThirdPartyRisk,
    WhistleblowerCase,
)


@admin.register(RiskCategory)
class RiskCategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class RiskTreatmentInline(admin.TabularInline):
    model = RiskTreatment
    extra = 1


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = (
        "event", "category", "likelihood", "risk_score",
        "risk_level", "risk_owner", "valid_from", "valid_to"
    )

    list_filter = (
        "risk_level", "category", "valid_from", "valid_to"
    )

    search_fields = (
        "event", "cause", "impact"
    )

    readonly_fields = ("risk_level",)

    date_hierarchy = "valid_from"

    ordering = ("-valid_from",)

    inlines = [RiskTreatmentInline]


@admin.register(Likelihood)
class LikelihoodAdmin(admin.ModelAdmin):
    list_display = (
        "rating", "descriptor", "definition"
    )


@admin.register(Impact)
class ImpactAdmin(admin.ModelAdmin):
    list_display = (
        "rating", "descriptor", "definition"
    )


@admin.register(RiskTreatment)
class RiskTreatmentAdmin(admin.ModelAdmin):
    list_display = ("risk", "owner", "status")
    list_filter = ("status",)
    search_fields = ("risk",)


admin.site.register(Scenario)


@admin.register(RiskIncident)
class RiskIncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "incident_type", "severity", "status", "event_date", "confidential")
    list_filter = ("incident_type", "severity", "status", "confidential")
    search_fields = ("title", "description", "reported_by", "business_unit")


@admin.register(KeyRiskIndicator)
class KeyRiskIndicatorAdmin(admin.ModelAdmin):
    list_display = ("name", "metric_owner", "current_value", "warning_threshold", "breach_threshold", "status")
    list_filter = ("status",)
    search_fields = ("name", "metric_owner")


@admin.register(RiskControl)
class RiskControlAdmin(admin.ModelAdmin):
    list_display = ("name", "control_type", "owner", "effectiveness", "next_test_due")
    list_filter = ("control_type", "effectiveness")
    search_fields = ("name", "owner", "description", "evidence_reference")


@admin.register(BusinessContinuityPlan)
class BusinessContinuityPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "critical_process", "recovery_owner", "status", "next_test_due")
    list_filter = ("status",)
    search_fields = ("name", "critical_process", "recovery_owner")


@admin.register(ThirdPartyRisk)
class ThirdPartyRiskAdmin(admin.ModelAdmin):
    list_display = ("party_name", "service_category", "risk_rating", "status", "next_review_date")
    list_filter = ("risk_rating", "status", "service_category")
    search_fields = ("party_name", "service_category", "contract_owner")


@admin.register(EnvironmentalSocialRisk)
class EnvironmentalSocialRiskAdmin(admin.ModelAdmin):
    list_display = ("title", "esg_area", "rating", "status", "next_review_date")
    list_filter = ("rating", "status", "esg_area")
    search_fields = ("title", "esg_area", "donor_standard")


@admin.register(WhistleblowerCase)
class WhistleblowerCaseAdmin(admin.ModelAdmin):
    list_display = ("case_reference", "allegation", "status", "reported_date", "anonymous", "donor_report_required")
    list_filter = ("status", "anonymous", "donor_report_required")
    search_fields = ("case_reference", "allegation", "assigned_investigator")
    readonly_fields = ("case_reference",)
