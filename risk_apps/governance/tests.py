from datetime import date

from django.test import TestCase

from account.models import Profile
from risk_apps.governance.models import Control, DecisionRecord, Policy, StakeholderEngagement


class GovernanceModelTests(TestCase):
    def test_policy_and_control_are_persisted(self):
        owner = Profile.objects.create_user(username="gov", password="pass12345")
        policy = Policy.objects.create(
            policy_id="POL-001",
            title="Safeguarding Policy",
            owner=owner,
            summary="Sets safeguarding standards.",
            effective_date=date.today(),
            status="active",
            approval_status="approved",
        )
        control = Control.objects.create(
            control_id="CTRL-001",
            title="Quarterly safeguarding review",
            policy=policy,
            owner=owner,
            description="Review safeguarding compliance quarterly.",
            status="active",
            effectiveness="effective",
        )

        self.assertEqual(str(policy), "POL-001 - Safeguarding Policy")
        self.assertEqual(control.policy, policy)

    def test_decision_and_stakeholder_tables_are_available(self):
        owner = Profile.objects.create_user(username="governance", password="pass12345")
        decision = DecisionRecord.objects.create(
            title="Approve annual governance plan",
            meeting_date=date.today(),
            resolution="Approved annual workplan.",
            vote_summary="7-0",
            status="approved",
            owner=owner,
        )
        engagement = StakeholderEngagement.objects.create(
            stakeholder_name="Community Leaders Forum",
            source_area="Yumbe",
            channel="dialogue",
            subject="Project accountability",
            feedback="Need quarterly community scorecards.",
            status="reviewed",
            assigned_to=owner,
        )

        self.assertEqual(str(decision), "Approve annual governance plan")
        self.assertEqual(str(engagement), "Community Leaders Forum - Project accountability")
