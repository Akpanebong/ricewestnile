from datetime import date

from django.contrib.auth.models import Group
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


class GovernanceAccessTests(TestCase):
    def setUp(self):
        self.governance_group = Group.objects.create(name="Governance")
        self.ed_group = Group.objects.create(name="ED")
        self.governance_user = Profile.objects.create_user(username="governance-member", password="pass12345")
        self.governance_user.groups.add(self.governance_group)
        self.ed_user = Profile.objects.create_user(username="executive-director", password="pass12345")
        self.ed_user.groups.add(self.ed_group)
        self.policy = Policy.objects.create(
            policy_id="POL-ACCESS",
            title="Access Policy",
            summary="Access test policy.",
        )

    def test_governance_is_a_standalone_top_level_route(self):
        self.client.force_login(self.governance_user)
        response = self.client.get("/governance/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Governance Hub")
        self.assertEqual(self.client.get("/garcis/governance/").status_code, 404)

    def test_governance_member_can_create_but_cannot_manage(self):
        self.client.force_login(self.governance_user)
        self.assertEqual(self.client.get("/governance/policies/create/").status_code, 200)
        create_response = self.client.post("/governance/policies/create/", {
            "policy_id": "POL-NEW",
            "title": "New Governance Policy",
            "summary": "Created by the Governance group.",
            "category": "Operations",
            "owner": "Governance",
            "version": "1.0",
        })
        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(self.client.get(f"/governance/policies/{self.policy.pk}/edit/").status_code, 403)
        self.assertEqual(self.client.post(f"/governance/policies/{self.policy.pk}/delete/").status_code, 403)

    def test_ed_can_manage_governance_records(self):
        self.client.force_login(self.ed_user)
        self.assertEqual(self.client.get(f"/governance/policies/{self.policy.pk}/edit/").status_code, 200)

    def test_other_authenticated_users_are_denied(self):
        other = Profile.objects.create_user(username="other", password="pass12345")
        self.client.force_login(other)
        self.assertEqual(self.client.get("/governance/").status_code, 403)
