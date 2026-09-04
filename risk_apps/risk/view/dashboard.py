import json

from django.db.models import Avg, Count
from django.db.models.functions import TruncDay
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from core.models import SystemActivity
from risk_apps.audit.models import AuditFinding
from risk_apps.compliance.models import ComplianceAssessment, ComplianceTask
from risk_apps.governance.models import Control, Policy
from risk_apps.risk.models import (
    BusinessContinuityPlan,
    EnvironmentalSocialRisk,
    KeyRiskIndicator,
    Risk,
    RiskControl,
    RiskIncident,
    Scenario,
    ThirdPartyRisk,
    WhistleblowerCase,
)
from risk_apps.risk.services.scenario_engine import analyze_scenario







@method_decorator(never_cache, name="dispatch")
class Dashboard(TemplateView):
    template_name = "garcis/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        scenario_id = self.request.GET.get("scenario")

        # =========================================================
        # BASE QUERY
        # =========================================================

        risks = Risk.objects.select_related(
            "likelihood",
            "impact",
            "category",
        )

        levels = [
            "VERY LOW",
            "LOW",
            "MODERATE",
            "HIGH",
            "VERY HIGH",
        ]

        # =========================================================
        # RISK LEVEL DISTRIBUTION
        # =========================================================

        level_counts = {
            level: 0
            for level in levels
        }

        for row in (
            risks
            .values("risk_level")
            .annotate(total=Count("id"))
        ):
            level = row["risk_level"]

            if level in level_counts:
                level_counts[level] = row["total"]

        # =========================================================
        # CATEGORY DISTRIBUTION
        # =========================================================

        category_rows = (
            risks
            .values("category__name")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        category_labels = []
        category_counts = []
        category_palette = [
            "#003333",
            "#198754",
            "#f59f00",
            "#dc3545",
            "#6f42c1",
            "#20c997",
            "#fd7e14",
            "#0dcaf0",
            "#d63384",
            "#495057",
            "#2f9e44",
            "#e03131",
        ]

        for row in category_rows:
            category_labels.append(
                row["category__name"] or "Uncategorised"
            )
            category_counts.append(row["total"])

        category_colors = [
            category_palette[index % len(category_palette)]
            for index, _ in enumerate(category_labels)
        ]

        # =========================================================
        # SCENARIO
        # =========================================================

        if scenario_id:
            scenario = get_object_or_404(
                Scenario,
                pk=scenario_id
            )
        else:
            scenario = (
                Scenario.objects
                .order_by("id")
                .first()
            )

        comparison = {
            "labels": levels,
            "before": [
                level_counts[level]
                for level in levels
            ],
            "after": [
                0
                for _ in levels
            ],
        }

        if scenario:
            after = {
                level: 0
                for level in levels
            }

            for result in analyze_scenario(scenario):
                new_level = result.get("new_level")

                if new_level in after:
                    after[new_level] += 1

            comparison["after"] = [
                after[level]
                for level in levels
            ]

        # =========================================================
        # 30-DAY TREND
        # =========================================================

        last_30_days = (
            timezone.now()
            - timezone.timedelta(days=30)
        )

        trend_rows = (
            risks
            .filter(created_at__gte=last_30_days)
            .annotate(day=TruncDay("created_at"))
            .values("day")
            .annotate(total=Count("id"))
            .order_by("day")
        )

        trend_labels = []
        trend_values = []

        for row in trend_rows:
            trend_labels.append(
                row["day"].strftime("%d %b")
            )
            trend_values.append(row["total"])

        # =========================================================
        # RISK HEATMAP
        # =========================================================
        #
        # Matrix key:
        # likelihood,impact
        #
        # Example:
        # "5,5"
        # "4,5"
        # "3,3"
        #
        # Adjust the fields below if your Risk model uses
        # different numeric fields.
        # =========================================================

        matrix = {
            f"{likelihood},{impact}": 0
            for likelihood in range(1, 6)
            for impact in range(1, 6)
        }

        heatmap_counts = (
            risks
            .values(
                "likelihood__rating",
                "impact__rating",
            )
            .annotate(total=Count("id"))
        )

        for row in heatmap_counts:

            likelihood = row["likelihood__rating"]
            impact = row["impact__rating"]

            if likelihood and impact:
                key = f"{likelihood},{impact}"

                if key in matrix:
                    matrix[key] = row["total"]

        heatmap_rows = []

        for likelihood in range(5, 0, -1):
            cells = []

            for impact in range(1, 6):
                key = f"{likelihood},{impact}"
                count = matrix[key]
                score = likelihood * impact

                if count == 0:
                    heat_class = "heat-empty"
                    level = "None"
                elif score >= 20:
                    heat_class = "heat-critical"
                    level = "Critical"
                elif score >= 15:
                    heat_class = "heat-high"
                    level = "High"
                elif score >= 10:
                    heat_class = "heat-moderate"
                    level = "Moderate"
                elif score >= 5:
                    heat_class = "heat-low"
                    level = "Low"
                else:
                    heat_class = "heat-very-low"
                    level = "Very Low"

                cells.append({
                    "impact": impact,
                    "count": count,
                    "score": score,
                    "class": heat_class,
                    "level": level,
                })

            heatmap_rows.append({
                "likelihood": likelihood,
                "cells": cells,
            })

        # =========================================================
        # KPI DATA
        # =========================================================

        total_risks = risks.count()

        high_risks = risks.filter(
            risk_level__in=[
                "HIGH",
                "VERY HIGH",
            ]
        ).count()

        open_risks = risks.filter(
            status="IDENTIFIED"
        ).count()

        emerging_risks = (
            risks
            .filter(
                risk_level__in=[
                    "HIGH",
                    "VERY HIGH",
                ]
            )
            .exclude(
                status__in=[
                    "CONTROLLED",
                    "RESOLVED",
                ]
            )
            .order_by(
                "-risk_score",
                "-created_at",
            )[:5]
        )

        emerging = [
            {
                "risk": risk.event,
                "level": risk.risk_level,
                "score": risk.risk_score,
                "risk_id": risk.risk_id,
                "ai_used": risk.ai_used,
                "ai_confidence": risk.ai_confidence,
            }
            for risk in emerging_risks
        ]

        avg_score = (
            risks.aggregate(
                avg=Avg("risk_score")
            )["avg"]
            or 0
        )

        policy_count = Policy.objects.count()
        control_count = Control.objects.count()

        open_findings = (
            AuditFinding.objects
            .exclude(status="closed")
            .count()
        )

        overdue_tasks = (
            ComplianceTask.objects
            .filter(status="overdue")
            .count()
        )

        avg_compliance = (
            ComplianceAssessment.objects
            .aggregate(avg=Avg("score"))["avg"]
            or 0
        )

        open_incidents = (
            RiskIncident.objects
            .exclude(status="closed")
            .count()
        )

        breached_kris = (
            KeyRiskIndicator.objects
            .filter(status="breached")
            .count()
        )

        weak_controls = (
            RiskControl.objects
            .filter(effectiveness__in=["needs_improvement", "weak"])
            .count()
        )

        continuity_due = (
            BusinessContinuityPlan.objects
            .filter(next_test_due__lte=timezone.now().date())
            .exclude(status="retired")
            .count()
        )

        high_third_party = (
            ThirdPartyRisk.objects
            .filter(risk_rating__in=["HIGH", "VERY HIGH"])
            .exclude(status="approved")
            .count()
        )

        active_esg = (
            EnvironmentalSocialRisk.objects
            .exclude(status="resolved")
            .count()
        )

        open_whistleblower_cases = (
            WhistleblowerCase.objects
            .exclude(status="closed")
            .count()
        )

        # =========================================================
        # SYSTEM HEALTH
        # =========================================================

        if avg_score > 15:
            system_health = "Critical"
            system_health_class = "danger"
        elif avg_score > 10:
            system_health = "Warning"
            system_health_class = "warning"
        else:
            system_health = "Stable"
            system_health_class = "success"

        # =========================================================
        # FINAL DATA
        # =========================================================

        data = {

            "total": total_risks,
            "high": high_risks,
            "open": open_risks,

            "avg_score": avg_score,

            "policy_count": policy_count,
            "control_count": control_count,

            "open_audit_findings": open_findings,
            "overdue_compliance_tasks": overdue_tasks,

            "avg_compliance_score": avg_compliance,

            "open_incidents": open_incidents,
            "breached_kris": breached_kris,
            "weak_controls": weak_controls,
            "continuity_due": continuity_due,
            "high_third_party": high_third_party,
            "active_esg": active_esg,
            "open_whistleblower_cases": open_whistleblower_cases,

            "system_health": system_health,
            "system_health_class": system_health_class,

            # Chart JSON
            "levels_json": json.dumps(levels),
            "level_counts_json": json.dumps(
                list(level_counts.values())
            ),

            "category_labels_json": json.dumps(
                category_labels
            ),
            "category_counts_json": json.dumps(
                category_counts
            ),
            "category_colors_json": json.dumps(
                category_colors
            ),

            "comparison_json": json.dumps(
                comparison
            ),

            "trend_labels_json": json.dumps(
                trend_labels
            ),

            "trend_values_json": json.dumps(
                trend_values
            ),

            "matrix_json": json.dumps(
                matrix
            ),

            # Other dashboard data
            "matrix": matrix,
            "heatmap_rows": heatmap_rows,

            "emerging": emerging,

            "scenarios": (
                Scenario.objects
                .order_by("name")
            ),

            "recent_activities": (
                SystemActivity.objects
                .select_related("actor")
                .order_by("-created_at")[:10]
            ),

            "selected_scenario": scenario,
        }

        context.update(data)

        return context
