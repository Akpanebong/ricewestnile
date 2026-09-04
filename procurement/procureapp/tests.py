from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from core.project_models import Project, ProjectBudget
from .models import ProcurementPlan, Supplier, Requisition, RFQ, RFQSendLog, PurchaseOrder


class ProcurementPlanBudgetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='project-head',
            password='test-pass-123',
        )
        self.project = Project.objects.create(name='Budgeted Project')
        self.budget = ProjectBudget.objects.create(
            project=self.project,
            fiscal_year='2026',
            period=ProjectBudget.FULL_YEAR,
            budget_amount=1000,
        )

    def make_plan(self, number, total):
        return ProcurementPlan.objects.create(
            number=number,
            requester=self.user,
            project=self.project,
            fiscal_year='2026',
            total_amount=total,
        )

    def test_plan_total_cannot_exceed_project_fiscal_year_budget(self):
        self.make_plan('PLAN-001', 700)
        plan = ProcurementPlan(
            number='PLAN-002',
            requester=self.user,
            project=self.project,
            fiscal_year='2026',
        )

        with self.assertRaises(ValidationError):
            plan.validate_budget_limit(400)

    def test_plan_total_can_use_remaining_project_fiscal_year_budget(self):
        self.make_plan('PLAN-001', 700)
        plan = ProcurementPlan(
            number='PLAN-002',
            requester=self.user,
            project=self.project,
            fiscal_year='2026',
        )

        self.assertEqual(plan.validate_budget_limit(300), self.budget)

    def test_project_budget_actual_amount_used_uses_sent_purchase_orders(self):
        plan = self.make_plan('PLAN-001', 700)
        requisition = Requisition.objects.create(
            number='REQ-001',
            procurement=plan,
            issued_by=self.user,
        )
        rfq = RFQ.objects.create(reference_no='RFQ-001', req=requisition)
        supplier = Supplier.objects.create(title='Awarded Supplier')
        send_log = RFQSendLog.objects.create(rfq=rfq, supplier=supplier)
        PurchaseOrder.objects.create(
            send_log=send_log,
            supplier=supplier,
            rfq=rfq,
            requisition=requisition,
            procurement_plan=plan,
            po_number='LPO-001',
            final_amount=650,
            sent=True,
        )
        PurchaseOrder.objects.create(
            send_log=send_log,
            supplier=supplier,
            rfq=rfq,
            requisition=requisition,
            procurement_plan=plan,
            po_number='LPO-002',
            final_amount=200,
            sent=False,
        )

        self.assertEqual(self.budget.actual_amount_used(), 650)
        self.assertEqual(self.budget.actual_amount_remaining(), 350)
