from datetime import date, timedelta

from django.test import TestCase

from account.models import Profile
from risk_apps.audit.models import AuditEvidence, AuditFinding, AuditLog, ExternalAuditEngagement, ExternalAuditFinding
from risk_apps.risk.models import Impact, Likelihood, Risk, RiskCategory


class AuditModelTests(TestCase):
    def test_audit_finding_defaults_to_open(self):
        auditor = Profile.objects.create_user(username="audit", password="pass12345")
        audit = AuditLog.objects.create(
            title="Finance Internal Audit",
            audit_type="internal",
            scope="Finance and grant controls",
            lead_auditor=auditor,
            start_date=date.today(),
            status="planned",
        )
        finding = AuditFinding.objects.create(
            audit=audit,
            title="Missing vendor due diligence",
            issue="Vendors were onboarded without documented screening.",
            recommendation="Enforce due diligence checklist before onboarding.",
            severity="high",
            owner=auditor,
            due_date=date.today() + timedelta(days=14),
        )

        self.assertEqual(finding.status, "open")
        self.assertEqual(audit.findings.count(), 1)

    def test_external_audit_and_evidence_models_are_persisted(self):
        auditor = Profile.objects.create_user(username="external_audit", password="pass12345")
        audit = AuditLog.objects.create(
            title="Procurement Audit",
            audit_type="internal",
            scope="Supplier onboarding",
            lead_auditor=auditor,
            start_date=date.today(),
            status="planned",
        )
        evidence = AuditEvidence.objects.create(
            audit=audit,
            title="Vendor due diligence checklist",
            evidence_type="document",
            document_tag="PROC",
            reference_code="PROC-001",
            uploaded_by=auditor,
            is_finance_reconciled=True,
        )
        internal_finding = AuditFinding.objects.create(
            audit=audit,
            title="Supplier screening gap",
            issue="Evidence of due diligence was incomplete.",
            recommendation="Require documented onboarding review.",
            severity="high",
            owner=auditor,
            due_date=date.today() + timedelta(days=21),
        )
        category = RiskCategory.objects.create(name="Compliance", risk_owner="Compliance", status="active")
        likelihood = Likelihood.objects.create(rating=2, descriptor="Unlikely", definition="Unlikely event")
        impact = Impact.objects.create(rating=5, descriptor="Severe", definition="Severe impact")
        risk = Risk.objects.create(
            event="Non-compliant procurement",
            cause="Missing supplier screening",
            category=category,
            likelihood=likelihood,
            impact=impact,
            risk_owner="Compliance Lead",
            risk_type="Compliance",
            mitigation_plan="Enforce onboarding controls",
            status="IDENTIFIED",
            date_identified=date.today(),
            valid_from=date.today(),
            valid_to=date.today() + timedelta(days=60),
            next_review_date=date.today() + timedelta(days=14),
            program="Consortium Compliance",
            source="Audit",
            created_by=auditor,
        )
        engagement = ExternalAuditEngagement.objects.create(
            audit_log=audit,
            title="Donor Compliance Audit",
            audit_firm="ABC Assurance",
            scope="Grant compliance testing",
            shared_data_scope="Selected procurement and finance records",
            start_date=date.today(),
            status="in_progress",
        )
        external_finding = ExternalAuditFinding.objects.create(
            engagement=engagement,
            related_internal_finding=internal_finding,
            related_risk=risk,
            title="Procurement controls incomplete",
            recommendation="Tighten vendor screening",
            mapped_reference="TXN-44",
        )

        self.assertTrue(evidence.is_finance_reconciled)
        self.assertEqual(external_finding.related_risk, risk)
