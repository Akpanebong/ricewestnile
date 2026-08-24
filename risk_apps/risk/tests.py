from datetime import date, timedelta
import json

from django.test import TestCase
from django.urls import reverse

from account.models import Profile
from risk_apps.governance.models import Policy
from risk_apps.risk.models import Impact, Likelihood, Risk, RiskCategory


class RiskViewTests(TestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(username="risk", password="pass12345")
        self.client.force_login(self.user)
        self.category = RiskCategory.objects.create(name="Operational", risk_owner="Ops", status="active")
        self.likelihood = Likelihood.objects.create(rating=3, descriptor="Possible", definition="Possible event")
        self.impact = Impact.objects.create(rating=4, descriptor="Major", definition="Major impact")

    def test_create_and_update_views_share_bound_form_template(self):
        create_response = self.client.get(reverse("risk_create"))
        self.assertContains(create_response, "Capture Risk")
        self.assertContains(create_response, 'name="event"')

        risk = Risk.objects.create(
            event="Funding delay",
            cause="Late disbursement",
            category=self.category,
            likelihood=self.likelihood,
            impact=self.impact,
            risk_owner="PM",
            risk_type="Financial",
            mitigation_plan="Escalate with donor",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            program="West Nile Support",
            source="Staff",
            created_by=self.user,
        )

        update_response = self.client.get(reverse("risk_update", kwargs={"pk": risk.pk}))
        self.assertContains(update_response, "Update Risk")
        self.assertContains(update_response, "Funding delay")
        self.assertContains(update_response, 'value="West Nile Support"')

    def test_main_dashboard_uses_fresh_model_counts(self):
        Risk.objects.create(
            event="Initial supply delay",
            cause="Transport disruption",
            category=self.category,
            likelihood=self.likelihood,
            impact=self.impact,
            risk_owner="PM",
            risk_type="Operational",
            mitigation_plan="Use alternative carrier",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            program="West Nile Support",
            source="Staff",
            created_by=self.user,
        )

        first_response = self.client.get("/garcis/")
        self.assertEqual(first_response.context["total"], 1)
        self.assertEqual(first_response.context["policy_count"], 0)
        self.assertIn("no-cache", first_response.headers["Cache-Control"])

        Policy.objects.create(
            policy_id="POL-001",
            title="Safeguarding Policy",
            owner="Governance",
            summary="Sets safeguarding standards.",
            effective_date=date.today(),
            status="active",
            approval_status="approved",
        )
        Risk.objects.create(
            event="New compliance issue",
            cause="Late statutory return",
            category=self.category,
            likelihood=self.likelihood,
            impact=self.impact,
            risk_owner="Compliance",
            risk_type="Compliance",
            mitigation_plan="Submit return",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            program="West Nile Support",
            source="Staff",
            created_by=self.user,
        )

        second_response = self.client.get("/garcis/")
        self.assertEqual(second_response.context["total"], 2)
        self.assertEqual(second_response.context["policy_count"], 1)

    def test_dashboard_heatmap_colors_cells_by_score_band(self):
        low_likelihood = Likelihood.objects.create(
            rating=1,
            descriptor="Rare",
            definition="Rare event",
        )
        low_impact = Impact.objects.create(
            rating=1,
            descriptor="Minor",
            definition="Minor impact",
        )
        critical_likelihood = Likelihood.objects.create(
            rating=5,
            descriptor="Almost Certain",
            definition="Expected event",
        )
        critical_impact = Impact.objects.create(
            rating=5,
            descriptor="Severe",
            definition="Severe impact",
        )

        Risk.objects.create(
            event="Low exposure item",
            cause="Minor process issue",
            category=self.category,
            likelihood=low_likelihood,
            impact=low_impact,
            risk_owner="Operations",
            risk_type="Operational",
            mitigation_plan="Monitor",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            created_by=self.user,
        )
        Risk.objects.create(
            event="Critical exposure item",
            cause="Major disruption",
            category=self.category,
            likelihood=critical_likelihood,
            impact=critical_impact,
            risk_owner="Executive",
            risk_type="Strategic",
            mitigation_plan="Escalate",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            created_by=self.user,
        )

        response = self.client.get("/garcis/")
        cells = {
            (row["likelihood"], cell["impact"]): cell
            for row in response.context["heatmap_rows"]
            for cell in row["cells"]
        }

        self.assertEqual(cells[(1, 1)]["class"], "heat-very-low")
        self.assertEqual(cells[(1, 1)]["count"], 1)
        self.assertEqual(cells[(5, 5)]["class"], "heat-critical")
        self.assertEqual(cells[(5, 5)]["count"], 1)

    def test_dashboard_category_chart_uses_distinct_slice_colors(self):
        finance_category = RiskCategory.objects.create(
            name="Financial",
            risk_owner="Finance",
            status="active",
        )

        for category, event in (
            (self.category, "Operational issue"),
            (finance_category, "Financial issue"),
        ):
            Risk.objects.create(
                event=event,
                cause="Dashboard category chart test",
                category=category,
                likelihood=self.likelihood,
                impact=self.impact,
                risk_owner="PM",
                risk_type=category.name,
                mitigation_plan="Track",
                status="IDENTIFIED",
                date_identified=date.today(),
                valid_from=date.today(),
                valid_to=date.today() + timedelta(days=30),
                next_review_date=date.today() + timedelta(days=7),
                created_by=self.user,
            )

        response = self.client.get("/garcis/")
        labels = json.loads(response.context["category_labels_json"])
        colors = json.loads(response.context["category_colors_json"])

        self.assertEqual(len(colors), len(labels))
        self.assertEqual(len(set(colors)), len(colors))
        self.assertGreaterEqual(len(colors), 2)

    def test_dashboard_emerging_risks_include_unresolved_high_exposure_risks(self):
        critical_likelihood = Likelihood.objects.create(
            rating=5,
            descriptor="Almost Certain",
            definition="Expected event",
        )
        critical_impact = Impact.objects.create(
            rating=5,
            descriptor="Severe",
            definition="Severe impact",
        )

        Risk.objects.create(
            event="Critical unresolved risk",
            cause="Major disruption",
            category=self.category,
            likelihood=critical_likelihood,
            impact=critical_impact,
            risk_owner="Executive",
            risk_type="Strategic",
            mitigation_plan="Escalate",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            created_by=self.user,
        )
        Risk.objects.create(
            event="Critical resolved risk",
            cause="Resolved disruption",
            category=self.category,
            likelihood=critical_likelihood,
            impact=critical_impact,
            risk_owner="Executive",
            risk_type="Strategic",
            mitigation_plan="Closed",
            status="RESOLVED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=30),
            next_review_date=date.today() + timedelta(days=7),
            created_by=self.user,
        )

        response = self.client.get("/garcis/")
        emerging_names = [
            item["risk"]
            for item in response.context["emerging"]
        ]

        self.assertIn("Critical unresolved risk", emerging_names)
        self.assertNotIn("Critical resolved risk", emerging_names)

        unresolved = next(
            item
            for item in response.context["emerging"]
            if item["risk"] == "Critical unresolved risk"
        )
        self.assertEqual(unresolved["level"], "VERY HIGH")
        self.assertEqual(unresolved["score"], 25)
        self.assertFalse(unresolved["ai_used"])
        self.assertIsNone(unresolved["ai_confidence"])
