from django import forms
from .models import (
    BusinessContinuityPlan,
    EnvironmentalSocialRisk,
    KeyRiskIndicator,
    Risk,
    RiskControl,
    RiskIncident,
    RiskTreatment,
    Scenario,
    ThirdPartyRisk,
    WhistleblowerCase,
)


class RiskForm(forms.ModelForm):
    class Meta:
        model = Risk
        fields = [
            "event",
            "cause",
            "category",
            "likelihood",
            "impact",
            "risk_owner",
            "risk_type",
            "status",
            "mitigation_plan",
            "date_identified",
            "valid_from",
            "valid_to",
            "next_review_date",
            "program",
            "source",
            "business_unit",
            "is_fraud_related",
            "esg_area",
            "continuity_dependency",
        ]
        widgets = {
            "event": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "cause": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "likelihood": forms.Select(attrs={"class": "form-select"}),
            "impact": forms.Select(attrs={"class": "form-select"}),
            "risk_owner": forms.TextInput(attrs={"class": "form-control"}),
            "risk_type": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "mitigation_plan": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "date_identified": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valid_from": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valid_to": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "next_review_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "program": forms.TextInput(attrs={"class": "form-control"}),
            "source": forms.TextInput(attrs={"class": "form-control"}),
            "business_unit": forms.TextInput(attrs={"class": "form-control"}),
            "is_fraud_related": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "esg_area": forms.TextInput(attrs={"class": "form-control"}),
            "continuity_dependency": forms.TextInput(attrs={"class": "form-control"}),
        }


class RiskTreatmentForm(forms.ModelForm):
    class Meta:
        model = RiskTreatment
        fields = '__all__'
        exclude = ['risk']


class ScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenario
        fields = ['name', 'description', 'multiplier', 'risks']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'multiplier': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'risks': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }


class GARCISRiskFeatureForm(forms.ModelForm):
    date_fields = {
        "event_date",
        "last_measured",
        "last_tested",
        "next_test_due",
        "due_diligence_date",
        "next_review_date",
        "reported_date",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if name in self.date_fields:
                widget.input_type = "date"
                widget.attrs.setdefault("class", "form-control")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs.setdefault("rows", 3)
            else:
                widget.attrs.setdefault("class", "form-control")


class RiskIncidentForm(GARCISRiskFeatureForm):
    class Meta:
        model = RiskIncident
        fields = [
            "title", "incident_type", "related_risk", "description", "reported_by",
            "business_unit", "event_date", "status", "severity", "immediate_action",
            "investigation_notes", "confidential",
        ]


class KeyRiskIndicatorForm(GARCISRiskFeatureForm):
    class Meta:
        model = KeyRiskIndicator
        fields = [
            "name", "related_risk", "metric_owner", "current_value",
            "warning_threshold", "breach_threshold", "unit", "last_measured",
            "response_plan",
        ]


class RiskControlForm(GARCISRiskFeatureForm):
    class Meta:
        model = RiskControl
        fields = [
            "name", "related_risk", "control_type", "owner", "description",
            "effectiveness", "last_tested", "next_test_due", "evidence_reference",
        ]


class BusinessContinuityPlanForm(GARCISRiskFeatureForm):
    class Meta:
        model = BusinessContinuityPlan
        fields = [
            "name", "related_risk", "critical_process", "recovery_owner",
            "recovery_time_objective", "recovery_point_objective", "status",
            "last_tested", "next_test_due", "continuity_actions",
        ]


class ThirdPartyRiskForm(GARCISRiskFeatureForm):
    class Meta:
        model = ThirdPartyRisk
        fields = [
            "party_name", "service_category", "related_risk", "risk_rating",
            "compliance_status", "contract_owner", "due_diligence_date",
            "next_review_date", "status", "mitigation_requirements",
        ]


class EnvironmentalSocialRiskForm(GARCISRiskFeatureForm):
    class Meta:
        model = EnvironmentalSocialRisk
        fields = [
            "title", "related_risk", "esg_area", "donor_standard",
            "affected_stakeholders", "rating", "status", "mitigation_plan",
            "next_review_date",
        ]


class WhistleblowerCaseForm(GARCISRiskFeatureForm):
    class Meta:
        model = WhistleblowerCase
        fields = [
            "allegation", "related_risk", "reporter_contact", "anonymous",
            "reported_date", "status", "assigned_investigator", "summary",
            "outcome", "donor_report_required",
        ]
