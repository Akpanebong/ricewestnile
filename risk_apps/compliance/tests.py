from datetime import date, timedelta

from django.test import TestCase

from risk_apps.compliance.models import (
    ComplianceFramework,
    ComplianceRequirement,
    ComplianceTask,
    PartnerDueDiligence,
    VendorDueDiligence,
)
from risk_apps.compliance.utils import update_task_status


class ComplianceTests(TestCase):
    def test_requirement_code_is_generated_and_task_warning_status_is_supported(self):
        framework = ComplianceFramework.objects.create(name="NGO Act")
        requirement = ComplianceRequirement.objects.create(
            framework=framework,
            title="Submit annual statutory return",
            description="File annual regulatory return.",
            level="program",
            evidence_required="Signed copy",
        )
        task = ComplianceTask.objects.create(
            requirement=requirement,
            due_date=date.today() + timedelta(days=1),
            responsible="Compliance Lead",
        )

        update_task_status(task)
        task.refresh_from_db()

        self.assertTrue(requirement.code.startswith("REQ-"))
        self.assertEqual(task.status, "warning")

    def test_partner_and_vendor_due_diligence_models_are_available(self):
        partner = PartnerDueDiligence.objects.create(
            partner_name="Consortium Partner A",
            governance_score=78,
            financial_capacity_score=81,
            compliance_score=74,
            risk_rating="medium",
            status="reviewed",
        )
        vendor = VendorDueDiligence.objects.create(
            vendor_name="West Nile Supplies",
            service_category="Logistics",
            legal_compliance_status="verified",
            financial_stability_score=72,
            ethical_screening_passed=True,
            risk_rating="low",
            performance_status="on_track",
            contract_ready=True,
        )

        self.assertEqual(str(partner), "Consortium Partner A")
        self.assertEqual(str(vendor), "West Nile Supplies")
