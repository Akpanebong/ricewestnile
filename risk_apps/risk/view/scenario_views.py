from django.views import View
from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView

from risk_apps.risk.models import Risk, Scenario
from risk_apps.risk.services.scenario_engine import analyze_scenario


class ScenarioAnalysisView(TemplateView):
    template_name = "risk/scenario_analysis.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        scenario_id = self.request.GET.get("scenario")

        context["scenarios"] = Scenario.objects.all()

        if scenario_id:
            scenario = get_object_or_404(Scenario, id=scenario_id)
            context["selected"] = scenario
            context["results"] = analyze_scenario(scenario)

        return context
