import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Avg, Count
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
from .services.scenario_engine import analyze_scenario
from .templatetags.risk_tags import risk_color
from .utils import generate_pdf
from .export import build_risk_register_workbook
from .forms import (
    BusinessContinuityPlanForm,
    EnvironmentalSocialRiskForm,
    KeyRiskIndicatorForm,
    RiskControlForm,
    RiskForm,
    RiskIncidentForm,
    RiskTreatmentForm,
    ScenarioForm,
    ThirdPartyRiskForm,
    WhistleblowerCaseForm,
)


FEATURE_CONFIGS = {
    "incidents": {
        "title": "Incident & Event Reporting",
        "subtitle": "Log incidents, near misses, fraud cases, and investigation status.",
        "create_label": "Report Incident",
        "columns": [("title", "Title"), ("incident_type", "Type"), ("severity", "Severity"), ("status", "Status"), ("event_date", "Event Date")],
    },
    "kris": {
        "title": "Key Risk Indicators",
        "subtitle": "Monitor thresholds and warning signals before risks escalate.",
        "create_label": "Add KRI",
        "columns": [("name", "Indicator"), ("metric_owner", "Owner"), ("current_value", "Current"), ("status", "Status"), ("last_measured", "Measured")],
    },
    "controls": {
        "title": "Risk Control Library",
        "subtitle": "Catalog internal controls, testing cycles, and evidence references.",
        "create_label": "Add Control",
        "columns": [("name", "Control"), ("control_type", "Type"), ("owner", "Owner"), ("effectiveness", "Effectiveness"), ("next_test_due", "Next Test")],
    },
    "continuity": {
        "title": "Business Continuity Plans",
        "subtitle": "Link critical processes, recovery targets, and continuity tests to risk records.",
        "create_label": "Add Plan",
        "columns": [("name", "Plan"), ("critical_process", "Process"), ("recovery_owner", "Owner"), ("status", "Status"), ("next_test_due", "Next Test")],
    },
    "third-party": {
        "title": "Third-Party Risk Management",
        "subtitle": "Assess vendor and partner exposures, compliance status, and review cycles.",
        "create_label": "Add Third Party",
        "columns": [("party_name", "Party"), ("service_category", "Category"), ("risk_rating", "Risk"), ("status", "Status"), ("next_review_date", "Review")],
    },
    "esg": {
        "title": "Environmental & Social Risk Tracking",
        "subtitle": "Monitor ESG and humanitarian risk alignment with donor standards.",
        "create_label": "Add ESG Record",
        "columns": [("title", "Record"), ("esg_area", "Area"), ("donor_standard", "Standard"), ("rating", "Rating"), ("status", "Status")],
    },
    "whistleblowing": {
        "title": "Whistleblower & Fraud Case Management",
        "subtitle": "Track secure reports, investigations, outcomes, and donor reporting needs.",
        "create_label": "Add Case",
        "columns": [("case_reference", "Reference"), ("allegation", "Allegation"), ("status", "Status"), ("reported_date", "Reported"), ("donor_report_required", "Donor Report")],
    },
}


class RiskFeatureMixin:
    template_name = "risk/feature_form.html"
    list_template_name = "risk/feature_list.html"
    detail_template_name = "risk/feature_detail.html"
    feature_key = None

    def get_feature_config(self):
        return FEATURE_CONFIGS[self.feature_key]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_feature_config())
        context["feature_key"] = self.feature_key
        context["list_url_name"] = self.list_url_name
        context["create_url_name"] = self.create_url_name
        context["update_url_name"] = self.update_url_name
        context["detail_url_name"] = self.detail_url_name
        return context


class RiskFeatureListView(RiskFeatureMixin, ListView):
    template_name = "risk/feature_list.html"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self.model, "related_risk"):
            queryset = queryset.select_related("related_risk")
        return queryset


class RiskFeatureDetailView(RiskFeatureMixin, DetailView):
    template_name = "risk/feature_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fields = []
        for field in self.object._meta.fields:
            if field.name in {"id", "created_by", "created_at", "updated_at"}:
                continue
            fields.append((field.verbose_name.title(), getattr(self.object, field.name)))
        context["fields"] = fields
        return context


class RiskFeatureCreateView(RiskFeatureMixin, CreateView):
    template_name = "risk/feature_form.html"

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        messages.success(self.request, f"{self.get_feature_config()['title']} record created.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(self.detail_url_name, kwargs={"pk": self.object.pk})


class RiskFeatureUpdateView(RiskFeatureMixin, UpdateView):
    template_name = "risk/feature_form.html"

    def form_valid(self, form):
        messages.success(self.request, f"{self.get_feature_config()['title']} record updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(self.detail_url_name, kwargs={"pk": self.object.pk})


class RiskListView(ListView):
    model = Risk
    template_name = "risk/list.html"
    paginate_by = 20

    def get_queryset(self):
        return Risk.objects.select_related('category', 'likelihood', 'impact')


class RiskDetailView(DetailView):
    model = Risk
    template_name = "risk/detail.html"
    context_object_name = "risk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        treatments = self.object.treatments.all()

        context["treatments"] = treatments
        context["progress_avg"] = treatments.aggregate(
            avg=Avg('progress_percent')
        )["avg"] or 0
        context["incidents"] = self.object.incidents.all()[:5]
        context["kris"] = self.object.kris.all()[:5]
        context["controls"] = self.object.controls.all()[:5]
        context["continuity_plans"] = self.object.continuity_plans.all()[:5]
        context["third_party_exposures"] = self.object.third_party_exposures.all()[:5]
        context["esg_records"] = self.object.esg_records.all()[:5]
        context["whistleblower_cases"] = self.object.whistleblower_cases.all()[:5]

        return context


class RiskCreateView(CreateView):
    model = Risk
    form_class = RiskForm
    template_name = "risk/form.html"

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        messages.success(self.request, "Risk created successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse('risk_detail', kwargs={'pk': self.object.pk})


class RiskUpdateView(UpdateView):
    model = Risk
    form_class = RiskForm
    template_name = "risk/form.html"

    def form_valid(self, form):
        messages.success(self.request, "Risk updated successfully")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('risk_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_update"] = True
        return context


def trash_risk(request, pk, risk_id):
    risk = get_object_or_404(Risk, pk=pk, risk_id=risk_id)
    if request.method == 'POST':
        messages.success(request, f"{risk} has been trashed successfully.")
        risk.delete()
        return redirect('risk_list')
    return render(request, 'delete_confirmation.html',
                  {'delete': risk, "cancel_url": reverse('risk_detail', kwargs={'pk': risk.pk})})


class RiskTreatmentListView(ListView):
    model = RiskTreatment
    template_name = "risk/treatment_list.html"

    def get_queryset(self):
        return RiskTreatment.objects.filter(risk_id=self.kwargs['pk'])


class RiskTreatmentCreateView(CreateView):
    model = RiskTreatment
    form_class = RiskTreatmentForm
    template_name = "risk/treatment_form.html"

    def form_valid(self, form):
        risk = get_object_or_404(Risk, pk=self.kwargs['pk'])
        form.instance.risk = risk
        messages.success(self.request, "Treatment plan created successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        print("FORM ERRORS:", form.errors)  # 🔥 DEBUG
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse('risk_detail', kwargs={'pk': self.kwargs['pk']})


class RiskMatrixView(TemplateView):
    template_name = "risk/matrix.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        risks = Risk.objects.select_related("likelihood", "impact")
        matrix = [[[] for _ in range(5)] for _ in range(5)]
        for r in risks:
            if not r.likelihood or not r.impact:
                continue
            i = r.impact.rating
            l = r.likelihood.rating
            matrix[i - 1][l - 1].append({
                "risk": r,
                "color": risk_color(r.risk_score)
            })
        matrix.reverse()
        context["matrix"] = matrix
        context["likelihood_range"] = [1,2,3,4,5]
        context["impact_range"] = [5,4,3,2,1]
        return context


class ExportRiskExcelView(View):
    def get(self, request, *args, **kwargs):
        risks = Risk.objects.select_related("category", "likelihood", "impact")
        wb = build_risk_register_workbook(risks)
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="Risk_Register.xlsx"'
        wb.save(response)
        return response


# -----------------------
# Export PDF
# -----------------------
class RiskPDFView(View):
    def get(self, request, *args, **kwargs):
        risks = Risk.objects.all()
        pdf = generate_pdf("risk/pdf.html", {"risks": risks})
        return HttpResponse(pdf, content_type='application/pdf')


# -----------------------
# Scenario Analysis
# -----------------------
class ScenarioListView(ListView):
    model = Scenario
    template_name = "risk/scenario_list.html"


class ScenarioCreateView(CreateView):
    model = Scenario
    form_class = ScenarioForm
    template_name = "risk/scenario_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Scenario created successfully")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('scenario_list')


class ScenarioDetailView(DetailView):
    model = Scenario
    template_name = "risk/scenario_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["analysis_preview"] = analyze_scenario(self.object)
        return context


class RiskIncidentConfig:
    model = RiskIncident
    feature_key = "incidents"
    list_url_name = "risk_incident_list"
    create_url_name = "risk_incident_create"
    detail_url_name = "risk_incident_detail"
    update_url_name = "risk_incident_update"


class RiskIncidentListView(RiskIncidentConfig, RiskFeatureListView):
    pass


class RiskIncidentDetailView(RiskIncidentConfig, RiskFeatureDetailView):
    pass


class RiskIncidentCreateView(RiskIncidentConfig, RiskFeatureCreateView):
    form_class = RiskIncidentForm


class RiskIncidentUpdateView(RiskIncidentConfig, RiskFeatureUpdateView):
    form_class = RiskIncidentForm


class KeyRiskIndicatorConfig:
    model = KeyRiskIndicator
    feature_key = "kris"
    list_url_name = "risk_kri_list"
    create_url_name = "risk_kri_create"
    detail_url_name = "risk_kri_detail"
    update_url_name = "risk_kri_update"


class KeyRiskIndicatorListView(KeyRiskIndicatorConfig, RiskFeatureListView):
    pass


class KeyRiskIndicatorDetailView(KeyRiskIndicatorConfig, RiskFeatureDetailView):
    pass


class KeyRiskIndicatorCreateView(KeyRiskIndicatorConfig, RiskFeatureCreateView):
    form_class = KeyRiskIndicatorForm


class KeyRiskIndicatorUpdateView(KeyRiskIndicatorConfig, RiskFeatureUpdateView):
    form_class = KeyRiskIndicatorForm


class RiskControlConfig:
    model = RiskControl
    feature_key = "controls"
    list_url_name = "risk_control_list"
    create_url_name = "risk_control_create"
    detail_url_name = "risk_control_detail"
    update_url_name = "risk_control_update"


class RiskControlListView(RiskControlConfig, RiskFeatureListView):
    pass


class RiskControlDetailView(RiskControlConfig, RiskFeatureDetailView):
    pass


class RiskControlCreateView(RiskControlConfig, RiskFeatureCreateView):
    form_class = RiskControlForm


class RiskControlUpdateView(RiskControlConfig, RiskFeatureUpdateView):
    form_class = RiskControlForm


class BusinessContinuityPlanConfig:
    model = BusinessContinuityPlan
    feature_key = "continuity"
    list_url_name = "risk_continuity_list"
    create_url_name = "risk_continuity_create"
    detail_url_name = "risk_continuity_detail"
    update_url_name = "risk_continuity_update"


class BusinessContinuityPlanListView(BusinessContinuityPlanConfig, RiskFeatureListView):
    pass


class BusinessContinuityPlanDetailView(BusinessContinuityPlanConfig, RiskFeatureDetailView):
    pass


class BusinessContinuityPlanCreateView(BusinessContinuityPlanConfig, RiskFeatureCreateView):
    form_class = BusinessContinuityPlanForm


class BusinessContinuityPlanUpdateView(BusinessContinuityPlanConfig, RiskFeatureUpdateView):
    form_class = BusinessContinuityPlanForm


class ThirdPartyRiskConfig:
    model = ThirdPartyRisk
    feature_key = "third-party"
    list_url_name = "risk_third_party_list"
    create_url_name = "risk_third_party_create"
    detail_url_name = "risk_third_party_detail"
    update_url_name = "risk_third_party_update"


class ThirdPartyRiskListView(ThirdPartyRiskConfig, RiskFeatureListView):
    pass


class ThirdPartyRiskDetailView(ThirdPartyRiskConfig, RiskFeatureDetailView):
    pass


class ThirdPartyRiskCreateView(ThirdPartyRiskConfig, RiskFeatureCreateView):
    form_class = ThirdPartyRiskForm


class ThirdPartyRiskUpdateView(ThirdPartyRiskConfig, RiskFeatureUpdateView):
    form_class = ThirdPartyRiskForm


class EnvironmentalSocialRiskConfig:
    model = EnvironmentalSocialRisk
    feature_key = "esg"
    list_url_name = "risk_esg_list"
    create_url_name = "risk_esg_create"
    detail_url_name = "risk_esg_detail"
    update_url_name = "risk_esg_update"


class EnvironmentalSocialRiskListView(EnvironmentalSocialRiskConfig, RiskFeatureListView):
    pass


class EnvironmentalSocialRiskDetailView(EnvironmentalSocialRiskConfig, RiskFeatureDetailView):
    pass


class EnvironmentalSocialRiskCreateView(EnvironmentalSocialRiskConfig, RiskFeatureCreateView):
    form_class = EnvironmentalSocialRiskForm


class EnvironmentalSocialRiskUpdateView(EnvironmentalSocialRiskConfig, RiskFeatureUpdateView):
    form_class = EnvironmentalSocialRiskForm


class WhistleblowerCaseConfig:
    model = WhistleblowerCase
    feature_key = "whistleblowing"
    list_url_name = "risk_whistleblower_list"
    create_url_name = "risk_whistleblower_create"
    detail_url_name = "risk_whistleblower_detail"
    update_url_name = "risk_whistleblower_update"


class WhistleblowerCaseListView(WhistleblowerCaseConfig, RiskFeatureListView):
    pass


class WhistleblowerCaseDetailView(WhistleblowerCaseConfig, RiskFeatureDetailView):
    pass


class WhistleblowerCaseCreateView(WhistleblowerCaseConfig, RiskFeatureCreateView):
    form_class = WhistleblowerCaseForm


class WhistleblowerCaseUpdateView(WhistleblowerCaseConfig, RiskFeatureUpdateView):
    form_class = WhistleblowerCaseForm
