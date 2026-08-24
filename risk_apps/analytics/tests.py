from datetime import date

from django.test import TestCase

from risk_apps.analytics.models import ProgramMetric


class AnalyticsModelTests(TestCase):
    def test_program_metric_table_is_available(self):
        metric = ProgramMetric.objects.create(
            program_name="Refugee Response",
            project_name="Livelihoods",
            metric_date=date.today(),
            budget_utilization=82.5,
            outcome_score=74.2,
            inclusion_score=88.0,
            sustainability_score=69.4,
            risk_index=41.5,
            compliance_index=90.0,
        )

        self.assertEqual(str(metric), f"Refugee Response - {date.today()}")
