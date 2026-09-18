from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from account.models import Profile
from core.services import get_base_currency

from .models import (
    BankReconciliation,
    BankReconciliationItem,
    CashBook,
    CashBookEntry,
    CashRequisition,
    CashRequisitionItem,
    FinancialCategory,
)
from .permissions import can_manage_chart_of_accounts, is_finance_editor, is_finance_staff
from .utils.workflow import advance_workflow, user_can_approve


def make_user(username, groups=(), **kwargs):
    user = Profile.objects.create_user(username=username, password="pw", **kwargs)
    for group_name in groups:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


class CashBookModelTests(TestCase):
    def setUp(self):
        self.creator = make_user("cbowner")
        self.cash_book = CashBook.objects.create(
            name="Field Office Cash Book",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            opening_balance=Decimal("1000.00"),
            created_by=self.creator,
        )

    def test_totals_with_no_entries(self):
        self.assertEqual(self.cash_book.total_receipts, 0)
        self.assertEqual(self.cash_book.total_payments, 0)
        self.assertEqual(self.cash_book.closing_balance, Decimal("1000.00"))

    def test_closing_balance_reflects_receipts_and_payments(self):
        CashBookEntry.objects.create(
            cash_book=self.cash_book, description="Donor deposit",
            receipt=Decimal("500.00"), created_by=self.creator,
        )
        CashBookEntry.objects.create(
            cash_book=self.cash_book, description="Fuel purchase",
            payment=Decimal("200.00"), created_by=self.creator,
        )
        self.assertEqual(self.cash_book.total_receipts, Decimal("500.00"))
        self.assertEqual(self.cash_book.total_payments, Decimal("200.00"))
        self.assertEqual(self.cash_book.closing_balance, Decimal("1300.00"))

    def test_entry_running_balance_accumulates_in_date_order(self):
        first = CashBookEntry.objects.create(
            cash_book=self.cash_book, date=date(2026, 1, 5), description="First",
            receipt=Decimal("300.00"), created_by=self.creator,
        )
        second = CashBookEntry.objects.create(
            cash_book=self.cash_book, date=date(2026, 1, 6), description="Second",
            payment=Decimal("100.00"), created_by=self.creator,
        )
        self.assertEqual(first.running_balance, Decimal("1300.00"))
        self.assertEqual(second.running_balance, Decimal("1200.00"))

    def test_entry_running_balance_uses_id_as_tiebreaker_on_same_date(self):
        same_day = date(2026, 1, 10)
        first = CashBookEntry.objects.create(
            cash_book=self.cash_book, date=same_day, description="Earlier row",
            receipt=Decimal("100.00"), created_by=self.creator,
        )
        second = CashBookEntry.objects.create(
            cash_book=self.cash_book, date=same_day, description="Later row",
            receipt=Decimal("50.00"), created_by=self.creator,
        )
        self.assertEqual(first.running_balance, Decimal("1100.00"))
        self.assertEqual(second.running_balance, Decimal("1150.00"))


class BankReconciliationModelTests(TestCase):
    def setUp(self):
        self.creator = make_user("reconowner")
        self.cash_book = CashBook.objects.create(
            name="Reconciled Book", period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            opening_balance=Decimal("0.00"), created_by=self.creator,
        )
        self.reconciliation = BankReconciliation.objects.create(
            cash_book=self.cash_book, statement_balance=Decimal("1000.00"), prepared_by=self.creator,
        )

    def test_adjusted_balance_with_no_items_equals_statement_balance(self):
        self.assertEqual(self.reconciliation.adjusted_balance, Decimal("1000.00"))

    def test_adjusted_balance_accounts_for_unpresented_and_uncredited_items(self):
        BankReconciliationItem.objects.create(
            reconciliation=self.reconciliation, item_type="payment", amount=Decimal("150.00")
        )
        BankReconciliationItem.objects.create(
            reconciliation=self.reconciliation, item_type="receipt", amount=Decimal("50.00")
        )
        # statement 1000 - unpresented payments 150 + uncredited receipts 50
        self.assertEqual(self.reconciliation.adjusted_balance, Decimal("900.00"))

    def test_difference_is_zero_when_adjusted_matches_cash_book(self):
        self.cash_book.opening_balance = Decimal("1000.00")
        self.cash_book.save()
        self.assertEqual(self.reconciliation.difference, Decimal("0.00"))

    def test_difference_is_nonzero_when_books_disagree(self):
        self.cash_book.opening_balance = Decimal("1000.00")
        self.cash_book.save()
        BankReconciliationItem.objects.create(
            reconciliation=self.reconciliation, item_type="payment", amount=Decimal("100.00")
        )
        self.assertEqual(self.reconciliation.difference, Decimal("-100.00"))


class FinancialCategoryModelTests(TestCase):
    # The 0003_seed_chart_of_accounts migration already populates real
    # "1000"-style codes, so test categories use a TEST- prefix to avoid
    # colliding with the seeded chart of accounts.
    def test_balance_side_for_asset_is_debit(self):
        category = FinancialCategory.objects.create(
            code="TEST-ASSET-1", name="Test Cash at bank", category_type=FinancialCategory.CategoryType.ASSET,
        )
        self.assertEqual(category.balance_side, "Dr")

    def test_balance_side_for_liability_is_credit(self):
        category = FinancialCategory.objects.create(
            code="TEST-LIAB-1", name="Test Accounts payable", category_type=FinancialCategory.CategoryType.LIABILITY,
        )
        self.assertEqual(category.balance_side, "Cr")

    def test_balance_side_for_income_is_credit(self):
        category = FinancialCategory.objects.create(
            code="TEST-INCOME-1", name="Test Grant income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        self.assertEqual(category.balance_side, "Cr")

    def test_balance_side_for_expense_is_debit(self):
        category = FinancialCategory.objects.create(
            code="TEST-EXPENSE-1", name="Test Fuel expense", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.assertEqual(category.balance_side, "Dr")

    def test_str_includes_code_and_name(self):
        category = FinancialCategory.objects.create(
            code="TEST-ASSET-2", name="Test Cash at bank 2", category_type=FinancialCategory.CategoryType.ASSET,
        )
        self.assertEqual(str(category), "TEST-ASSET-2 - Test Cash at bank 2")


class CashRequisitionModelTests(TestCase):
    def setUp(self):
        self.creator = make_user("requester")
        self.requisition = CashRequisition.objects.create(
            donor_code="DONOR-1", to="Executive Director", purpose="Field travel",
            date=date(2026, 1, 15), created_by=self.creator,
        )

    def test_total_amount_with_no_items_is_zero(self):
        self.assertEqual(self.requisition.total_amount(), 0)

    def test_total_amount_sums_item_costs(self):
        CashRequisitionItem.objects.create(
            requisition=self.requisition, activity_code="A1", program_code="P1",
            particulars="Fuel", quantity=3, unit_cost=Decimal("50.00"),
        )
        CashRequisitionItem.objects.create(
            requisition=self.requisition, activity_code="A2", program_code="P1",
            particulars="Airtime", quantity=2, unit_cost=Decimal("10.00"),
        )
        self.assertEqual(self.requisition.total_amount(), Decimal("170.00"))

    def test_item_total_cost_multiplies_quantity_by_unit_cost(self):
        item = CashRequisitionItem.objects.create(
            requisition=self.requisition, activity_code="A1", program_code="P1",
            particulars="Fuel", quantity=4, unit_cost=Decimal("25.50"),
        )
        self.assertEqual(item.total_cost, Decimal("102.00"))

    def test_slug_is_auto_generated_and_unique(self):
        other = CashRequisition.objects.create(
            donor_code="DONOR-1", to="Executive Director", purpose="Another trip",
            date=date(2026, 1, 16), created_by=self.creator,
        )
        self.assertTrue(self.requisition.slug)
        self.assertTrue(other.slug)
        self.assertNotEqual(self.requisition.slug, other.slug)


class PermissionsHelperTests(TestCase):
    def test_is_finance_editor_true_for_superuser(self):
        admin = Profile.objects.create_superuser(username="admin", password="pw", email="a@example.com")
        self.assertTrue(is_finance_editor(admin))

    def test_is_finance_editor_true_for_finance_group(self):
        user = make_user("financer", groups=["Finance"])
        self.assertTrue(is_finance_editor(user))

    def test_is_finance_editor_false_for_unrelated_user(self):
        user = make_user("outsider")
        self.assertFalse(is_finance_editor(user))

    def test_is_finance_editor_false_for_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(is_finance_editor(AnonymousUser()))

    def test_is_finance_staff_true_for_operations_group(self):
        user = make_user("ops", groups=["Operations"])
        self.assertTrue(is_finance_staff(user))

    def test_can_manage_chart_of_accounts_false_for_operations_group(self):
        # Operations can see finance-wide data (is_finance_staff) but is not
        # allowed to edit the chart of accounts itself.
        user = make_user("ops2", groups=["Operations"])
        self.assertFalse(can_manage_chart_of_accounts(user))

    def test_can_manage_chart_of_accounts_true_for_finance_group(self):
        user = make_user("financer2", groups=["Finance"])
        self.assertTrue(can_manage_chart_of_accounts(user))


class ApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.creator = make_user("req_owner")
        self.requisition = CashRequisition.objects.create(
            donor_code="DONOR-1", to="Executive Director", purpose="Field travel",
            date=date(2026, 1, 15), created_by=self.creator, status="submitted",
        )

    def test_finance_group_can_approve_submitted_stage(self):
        finance_user = make_user("finance_reviewer", groups=["Finance"])
        self.assertTrue(user_can_approve(finance_user, self.requisition))

    def test_operations_group_cannot_approve_submitted_stage(self):
        ops_user = make_user("ops_reviewer", groups=["Operations"])
        self.assertFalse(user_can_approve(ops_user, self.requisition))

    def test_advance_workflow_moves_through_every_stage(self):
        finance_user = make_user("f", groups=["Finance"])
        ops_user = make_user("o", groups=["Operations"])
        ed_user = make_user("e", groups=["ED"])

        advance_workflow(self.requisition, finance_user)
        self.assertEqual(self.requisition.status, "finance_review")
        self.assertEqual(self.requisition.checked_by, finance_user)

        advance_workflow(self.requisition, ops_user)
        self.assertEqual(self.requisition.status, "operations_review")
        self.assertEqual(self.requisition.reviewed_by, ops_user)

        advance_workflow(self.requisition, ed_user)
        self.assertEqual(self.requisition.status, "approved")
        self.assertEqual(self.requisition.approved_by, ed_user)

    def test_user_can_approve_is_false_once_approved(self):
        self.requisition.status = "approved"
        self.requisition.save()
        finance_user = make_user("late_finance", groups=["Finance"])
        self.assertFalse(user_can_approve(finance_user, self.requisition))


class DashboardAndCashbookViewTests(TestCase):
    def setUp(self):
        self.finance_user = make_user("finance_view_user", groups=["Finance"])
        self.regular_user = make_user("plain_view_user")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("finance:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_renders_for_authenticated_user(self):
        self.client.login(username="plain_view_user", password="pw")
        response = self.client.get(reverse("finance:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_cashbook_list_requires_login(self):
        response = self.client.get(reverse("finance:cashbook_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashbook_list_renders_with_existing_cash_books(self):
        CashBook.objects.create(
            name="Visible Book", period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            created_by=self.finance_user,
        )
        self.client.login(username="plain_view_user", password="pw")
        response = self.client.get(reverse("finance:cashbook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Book")

    def test_cashbook_create_denied_for_non_finance_user(self):
        self.client.login(username="plain_view_user", password="pw")
        response = self.client.post(reverse("finance:cashbook_create"), {
            "name": "New Book", "period_start": "2026-01-01", "period_end": "2026-01-31",
            "opening_balance": "0",
        })
        self.assertRedirects(response, reverse("finance:dashboard"))
        self.assertFalse(CashBook.objects.filter(name="New Book").exists())

    def test_cashbook_create_succeeds_for_finance_user(self):
        self.client.login(username="finance_view_user", password="pw")
        response = self.client.post(reverse("finance:cashbook_create"), {
            "name": "New Book", "period_start": "2026-01-01", "period_end": "2026-01-31",
            "opening_balance": "0",
        })
        book = CashBook.objects.get(name="New Book")
        self.assertRedirects(response, reverse("finance:cashbook_detail", kwargs={"pk": book.pk}))
        self.assertEqual(book.created_by, self.finance_user)

    def test_cashbook_delete_denied_for_non_finance_user(self):
        book = CashBook.objects.create(
            name="Protected Book", period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            created_by=self.finance_user,
        )
        self.client.login(username="plain_view_user", password="pw")
        response = self.client.post(reverse("finance:cashbook_delete", kwargs={"pk": book.pk}))
        self.assertRedirects(response, reverse("finance:dashboard"))
        self.assertTrue(CashBook.objects.filter(pk=book.pk).exists())

    def test_cashbook_delete_succeeds_for_finance_user(self):
        book = CashBook.objects.create(
            name="Deletable Book", period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            created_by=self.finance_user,
        )
        self.client.login(username="finance_view_user", password="pw")
        response = self.client.post(reverse("finance:cashbook_delete", kwargs={"pk": book.pk}))
        self.assertRedirects(response, reverse("finance:cashbook_list"))
        self.assertFalse(CashBook.objects.filter(pk=book.pk).exists())


class CreateCashRequisitionViewTests(TestCase):
    def setUp(self):
        self.finance_user = make_user("cr_finance_user", groups=["Finance"])
        self.regular_user = make_user("cr_plain_user")

    def test_denied_for_non_finance_editor(self):
        self.client.login(username="cr_plain_user", password="pw")
        response = self.client.get(reverse("finance:create_cash_req"))
        self.assertRedirects(response, reverse("finance:dashboard"))

    def test_creates_requisition_with_items_for_finance_editor(self):
        self.client.login(username="cr_finance_user", password="pw")
        response = self.client.post(reverse("finance:create_cash_req"), {
            "donor_code": "DONOR-9",
            "purpose": "Workshop logistics",
            "date": "2026-02-01",
            "items[0][activity_code]": "A1",
            "items[0][program_code]": "P1",
            "items[0][particulars]": "Venue hire",
            "items[0][quantity]": "1",
            "items[0][unit_cost]": "500",
        })
        requisition = CashRequisition.objects.get(donor_code="DONOR-9")
        self.assertRedirects(
            response,
            reverse("finance:requisition_detail", kwargs={"pk": requisition.pk, "slug": requisition.slug}),
        )
        self.assertEqual(requisition.status, "draft")
        self.assertEqual(requisition.created_by, self.finance_user)
        self.assertEqual(requisition.items.count(), 1)
        self.assertEqual(requisition.items.first().quantity, 1)


class SubmitAndApproveRequisitionViewTests(TestCase):
    def setUp(self):
        self.owner = make_user("submit_owner", groups=["Finance"])
        self.other_finance_user = make_user("other_finance", groups=["Finance"])
        self.requisition = CashRequisition.objects.create(
            donor_code="DONOR-1", to="Executive Director", purpose="Field travel",
            date=date(2026, 1, 15), created_by=self.owner, status="draft",
        )

    def _submit_url(self):
        return reverse(
            "finance:submit_cash_req", kwargs={"pk": self.requisition.pk, "slug": self.requisition.slug}
        )

    def _approve_url(self):
        return reverse(
            "finance:approve_cash_req", kwargs={"pk": self.requisition.pk, "slug": self.requisition.slug}
        )

    def test_only_the_owner_can_submit_their_draft(self):
        self.client.login(username="other_finance", password="pw")
        response = self.client.post(self._submit_url())
        self.assertEqual(response.status_code, 404)
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, "draft")

    def test_owner_can_submit_their_own_draft(self):
        self.client.login(username="submit_owner", password="pw")
        response = self.client.post(self._submit_url())
        self.assertRedirects(
            response,
            reverse("finance:requisition_detail", kwargs={"pk": self.requisition.pk, "slug": self.requisition.slug}),
        )
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, "submitted")

    def test_submitting_twice_is_rejected(self):
        self.client.login(username="submit_owner", password="pw")
        self.client.post(self._submit_url())
        self.client.post(self._submit_url())
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, "submitted")

    def test_approve_denied_for_wrong_group_at_submitted_stage(self):
        self.requisition.status = "submitted"
        self.requisition.save()
        ops_user = make_user("wrong_group_ops", groups=["Operations"])
        self.client.login(username="wrong_group_ops", password="pw")
        self.client.post(self._approve_url())
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, "submitted")

    def test_approve_advances_status_for_correct_group(self):
        self.requisition.status = "submitted"
        self.requisition.save()
        self.client.login(username="other_finance", password="pw")
        self.client.post(self._approve_url())
        self.requisition.refresh_from_db()
        self.assertEqual(self.requisition.status, "finance_review")
        self.assertEqual(self.requisition.checked_by, self.other_finance_user)
