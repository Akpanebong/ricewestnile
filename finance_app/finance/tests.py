from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from account.models import Profile
from core.services import get_base_currency

from .forms import BudgetLineFormSet, FinanceBudgetLineForm
from .models import (
    BankReconciliation,
    BankReconciliationItem,
    CashBook,
    CashBookEntry,
    CashRequisition,
    CashRequisitionItem,
    FinanceBudget,
    FinanceBudgetLine,
    FinancialCategory,
    FinancialTransaction,
    JournalEntry,
    JournalEntryLine,
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
        # EditDeleteAuthorizationMiddleware now gates every *delete*/*trash*
        # URL site-wide to superusers + ED, raising PermissionDenied (403)
        # before the view's own @finance_editor_required ever runs.
        self.assertEqual(response.status_code, 403)
        self.assertTrue(CashBook.objects.filter(pk=book.pk).exists())

    def test_cashbook_delete_denied_for_finance_user_not_in_ed(self):
        # finance_view_user is Finance-only. cashbook_delete's own
        # @finance_editor_required would allow Finance staff to delete, but
        # EditDeleteAuthorizationMiddleware's can_delete_or_trash() only
        # allows superuser/ED, and the middleware runs first — so a
        # Finance-only user is now blocked from deleting cash books too.
        book = CashBook.objects.create(
            name="Protected Book 2", period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            created_by=self.finance_user,
        )
        self.client.login(username="finance_view_user", password="pw")
        response = self.client.post(reverse("finance:cashbook_delete", kwargs={"pk": book.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(CashBook.objects.filter(pk=book.pk).exists())

    def test_cashbook_delete_succeeds_for_ed_user(self):
        ed_user = make_user("cashbook_ed_user", groups=["ED"])
        book = CashBook.objects.create(
            name="Deletable Book", period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            created_by=self.finance_user,
        )
        self.client.login(username="cashbook_ed_user", password="pw")
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


class JournalEntryLinePostingTests(TestCase):
    """post() must classify the resulting FinancialTransaction by the
    posted account's category_type, since the Financial Ledger's Total
    Income/Expense/Transfer cards filter on that classification."""

    def setUp(self):
        self.user = make_user("journal_poster")
        self.income_account = FinancialCategory.objects.create(
            code="TEST-JE-INCOME", name="Test Donor Income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-JE-EXPENSE", name="Test Program Expense", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.asset_account = FinancialCategory.objects.create(
            code="TEST-JE-ASSET", name="Test Cash", category_type=FinancialCategory.CategoryType.ASSET,
        )
        self.entry = JournalEntry.objects.create(date=date(2026, 1, 1), created_by=self.user)

    def test_income_account_posts_as_income(self):
        line = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.income_account, debit=Decimal("0.00"), credit=Decimal("500.00"),
        )
        txn = line.post()
        self.assertEqual(txn.transaction_type, FinancialTransaction.TransactionType.INCOME)

    def test_expense_account_posts_as_expense(self):
        line = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.expense_account, debit=Decimal("500.00"), credit=Decimal("0.00"),
        )
        txn = line.post()
        self.assertEqual(txn.transaction_type, FinancialTransaction.TransactionType.EXPENSE)

    def test_asset_account_posts_as_transfer(self):
        line = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.asset_account, debit=Decimal("500.00"), credit=Decimal("0.00"),
        )
        txn = line.post()
        self.assertEqual(txn.transaction_type, FinancialTransaction.TransactionType.TRANSFER)

    def test_signed_amount_follows_natural_balance_side(self):
        # Asset is Dr-natured: a debit increases it, so the signed amount
        # posted should be positive.
        debit_line = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.asset_account, debit=Decimal("500.00"), credit=Decimal("0.00"),
        )
        self.assertEqual(debit_line.post().amount, Decimal("500.00"))

        # Income is Cr-natured: a debit (unusual, e.g. a correction) decreases
        # it, so the signed amount posted should be negative.
        debit_against_income = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.income_account, debit=Decimal("200.00"), credit=Decimal("0.00"),
        )
        self.assertEqual(debit_against_income.post().amount, Decimal("-200.00"))


class JournalEntryReversalTests(TestCase):
    def setUp(self):
        self.creator = make_user("je_owner")
        self.income_account = FinancialCategory.objects.create(
            code="TEST-REV-INCOME", name="Test Reversal Income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        self.asset_account = FinancialCategory.objects.create(
            code="TEST-REV-ASSET", name="Test Reversal Cash", category_type=FinancialCategory.CategoryType.ASSET,
        )
        self.entry = JournalEntry.objects.create(date=date(2026, 1, 1), created_by=self.creator, description="Original")
        self.debit_line = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.asset_account, debit=Decimal("300.00"), credit=Decimal("0.00"),
        )
        self.credit_line = JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.income_account, debit=Decimal("0.00"), credit=Decimal("300.00"),
        )
        self.debit_line.post()
        self.credit_line.post()

    def test_reverse_creates_linked_entry_with_swapped_amounts(self):
        reverser = make_user("je_reverser")
        reversal = self.entry.reverse(reverser)

        self.assertEqual(reversal.reversal_of, self.entry)
        self.assertEqual(reversal.created_by, reverser)

        reversed_asset_line = reversal.lines.get(category=self.asset_account)
        reversed_income_line = reversal.lines.get(category=self.income_account)
        self.assertEqual(reversed_asset_line.debit, Decimal("0.00"))
        self.assertEqual(reversed_asset_line.credit, Decimal("300.00"))
        self.assertEqual(reversed_income_line.debit, Decimal("300.00"))
        self.assertEqual(reversed_income_line.credit, Decimal("0.00"))

    def test_reverse_nets_to_zero_on_each_account(self):
        reversal = self.entry.reverse(self.creator)
        for line in reversal.lines.all():
            line.post()

        asset_total = FinancialTransaction.objects.filter(category=self.asset_account).aggregate(
            total=Sum("amount")
        )["total"]
        self.assertEqual(asset_total, Decimal("0.00"))

    def test_entry_is_marked_reversed(self):
        self.assertFalse(self.entry.is_reversed)
        reversal = self.entry.reverse(self.creator)
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.is_reversed)
        self.assertEqual(self.entry.reversed_by, reversal)

    def test_cannot_reverse_twice(self):
        self.entry.reverse(self.creator)
        with self.assertRaises(ValueError):
            self.entry.reverse(self.creator)

    def test_cannot_reverse_a_reversal(self):
        # Without this guard, a reversal entry could itself be reversed,
        # and that reversal reversed again, letting the same original
        # mistake flip back and forth indefinitely instead of being
        # corrected once with a new entry.
        reversal = self.entry.reverse(self.creator)
        with self.assertRaises(ValueError):
            reversal.reverse(self.creator)


class ReverseJournalEntryViewTests(TestCase):
    def setUp(self):
        self.finance_user = make_user("reverse_view_finance", groups=["Finance"])
        self.plain_user = make_user("reverse_view_plain")
        self.income_account = FinancialCategory.objects.create(
            code="TEST-RV-INCOME", name="Test RV Income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        self.asset_account = FinancialCategory.objects.create(
            code="TEST-RV-ASSET", name="Test RV Cash", category_type=FinancialCategory.CategoryType.ASSET,
        )
        self.entry = JournalEntry.objects.create(date=date(2026, 1, 1), created_by=self.finance_user)
        JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.asset_account, debit=Decimal("100.00"), credit=Decimal("0.00"),
        ).post()
        JournalEntryLine.objects.create(
            journal_entry=self.entry, category=self.income_account, debit=Decimal("0.00"), credit=Decimal("100.00"),
        ).post()

    def _reverse_url(self):
        return reverse("finance:reverse_journal_entry", args=[self.entry.pk])

    def test_denied_for_non_finance_user(self):
        self.client.login(username="reverse_view_plain", password="pw")
        self.client.post(self._reverse_url())
        self.entry.refresh_from_db()
        self.assertFalse(self.entry.is_reversed)

    def test_finance_user_can_reverse(self):
        self.client.login(username="reverse_view_finance", password="pw")
        response = self.client.post(self._reverse_url())
        self.entry.refresh_from_db()
        self.assertTrue(self.entry.is_reversed)
        self.assertRedirects(
            response, reverse("finance:journal_entry_detail", args=[self.entry.reversed_by.pk])
        )

    def test_get_request_does_not_reverse(self):
        self.client.login(username="reverse_view_finance", password="pw")
        self.client.get(self._reverse_url())
        self.entry.refresh_from_db()
        self.assertFalse(self.entry.is_reversed)

    def test_cannot_reverse_a_reversal_via_the_view(self):
        self.client.login(username="reverse_view_finance", password="pw")
        self.client.post(self._reverse_url())
        self.entry.refresh_from_db()
        reversal = self.entry.reversed_by

        response = self.client.post(reverse("finance:reverse_journal_entry", args=[reversal.pk]))
        reversal.refresh_from_db()
        self.assertFalse(reversal.is_reversed)
        self.assertRedirects(response, reverse("finance:journal_entry_detail", args=[reversal.pk]))


class FinanceBudgetLineIncomeSignTests(TestCase):
    """Income is entered as a negative (credit) figure, so its actual must
    be negated to match — otherwise a receipt would read as extra spend
    when summed with expense lines into a budget-wide total."""

    def setUp(self):
        self.creator = make_user("budget_income_sign_owner")
        self.income_account = FinancialCategory.objects.create(
            code="TEST-SIGN-INCOME", name="Test Sign Donor Income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-SIGN-EXPENSE", name="Test Sign Programme Costs", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.budget = FinanceBudget.objects.create(
            name="Test Sign Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.creator,
        )
        self.income_line = FinanceBudgetLine.objects.create(
            budget=self.budget, category=self.income_account, m01=Decimal("-1000.00"),
        )
        self.expense_line = FinanceBudgetLine.objects.create(
            budget=self.budget, category=self.expense_account, m01=Decimal("1000.00"),
        )

    def test_income_actual_is_negated_to_match_the_budgeted_convention(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.INCOME,
            category=self.income_account, amount=Decimal("300.00"), currency=get_base_currency(),
            date=date(2026, 1, 10), created_by=self.creator,
        )
        self.assertEqual(self.income_line.actual_for_month(2026, 1), Decimal("-300.00"))
        self.assertEqual(self.income_line.actual_total, Decimal("-300.00"))

    def test_expense_actual_is_unaffected(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("200.00"), currency=get_base_currency(),
            date=date(2026, 1, 15), created_by=self.creator,
        )
        self.assertEqual(self.expense_line.actual_total, Decimal("200.00"))

    def test_income_receipt_does_not_inflate_the_budget_wide_actual(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.INCOME,
            category=self.income_account, amount=Decimal("300.00"), currency=get_base_currency(),
            date=date(2026, 1, 10), created_by=self.creator,
        )
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("200.00"), currency=get_base_currency(),
            date=date(2026, 1, 15), created_by=self.creator,
        )
        # The budget-wide headline is a cost-tracking figure (Expense-type
        # lines only) — without that scoping this would read 500.00 (300
        # income + 200 expense blended together) or, with only the sign
        # flip and no scoping, -100.00 (300 income negated, netted against
        # 200 expense). Either way a receipt must never show up as spend.
        self.assertEqual(self.budget.actual_amount, Decimal("200.00"))
        self.assertEqual(self.budget.total_amount, Decimal("1000.00"))
        # The income line itself still correctly shows its own negative actual.
        self.assertEqual(self.income_line.actual_total, Decimal("-300.00"))


class FinanceBudgetPerformancePropertiesTests(TestCase):
    """FinanceBudget.actual_amount/variance_amount/utilization_percent — the
    figures the Budget performance page shows must come from the ledger."""

    def setUp(self):
        self.creator = make_user("budget_perf_owner")
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-PERF-EXPENSE", name="Test Perf Expense", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.budget = FinanceBudget.objects.create(
            name="Test Perf Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.creator,
        )
        FinanceBudgetLine.objects.create(
            budget=self.budget, category=self.expense_account,
            m01=Decimal("1000.00"), m02=Decimal("1000.00"),
        )

    def test_actual_amount_is_zero_with_no_transactions(self):
        self.assertEqual(self.budget.actual_amount, Decimal("0.00"))
        self.assertEqual(self.budget.utilization_percent, Decimal("0.00"))

    def test_actual_amount_reflects_real_ledger_activity(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("500.00"), currency=get_base_currency(),
            date=date(2026, 1, 15), created_by=self.creator,
        )
        self.assertEqual(self.budget.actual_amount, Decimal("500.00"))
        self.assertEqual(self.budget.variance_amount, Decimal("1500.00"))
        self.assertEqual(self.budget.utilization_percent, Decimal("25.00"))

    def test_utilization_percent_is_zero_for_a_budget_with_no_lines(self):
        empty_budget = FinanceBudget.objects.create(
            name="Test Empty Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.creator,
        )
        self.assertEqual(empty_budget.total_amount, Decimal("0.00"))
        self.assertEqual(empty_budget.utilization_percent, Decimal("0.00"))


class PerformanceListViewTests(TestCase):
    """The Budget performance page lists every budget with ledger-derived
    totals and links through to its transactions — it is not a form for
    typing in expenditure figures by hand."""

    def setUp(self):
        self.user = make_user("perf_view_user", groups=["Finance"])
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-PERF-VIEW", name="Test Perf View Expense", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.budget = FinanceBudget.objects.create(
            name="Test Perf View Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.user,
        )
        FinanceBudgetLine.objects.create(budget=self.budget, category=self.expense_account, m01=Decimal("1000.00"))

    def test_lists_budgets_with_ledger_derived_totals(self):
        self.client.login(username="perf_view_user", password="pw")
        response = self.client.get(reverse("finance:performance_list"))
        self.assertEqual(response.status_code, 200)
        rows = {row["budget"].pk: row for row in response.context["rows"]}
        self.assertEqual(rows[self.budget.pk]["total"], Decimal("1000.00"))
        self.assertEqual(rows[self.budget.pk]["actual"], Decimal("0.00"))

    def test_links_through_to_the_budget_transactions_drilldown(self):
        self.client.login(username="perf_view_user", password="pw")
        response = self.client.get(reverse("finance:performance_list"))
        self.assertContains(response, reverse("finance:budget_transactions", args=[self.budget.pk]))

    def test_no_add_entry_point_remains(self):
        self.client.login(username="perf_view_user", password="pw")
        response = self.client.get(reverse("finance:performance_list"))
        self.assertNotContains(response, "Add performance")

    def test_manual_performance_create_route_is_gone(self):
        from django.urls import NoReverseMatch
        with self.assertRaises(NoReverseMatch):
            reverse("finance:performance_create")


class BudgetTransactionsViewTests(TestCase):
    """Drilling into a budget from the Performance page must show the real
    ledger postings behind its "Actual" figure — scoped to exactly the same
    category/date/project filters FinanceBudgetLine.actual_total uses, so
    the list always foots to the totals shown elsewhere."""

    def setUp(self):
        self.user = make_user("txn_view_user", groups=["Finance"])
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-TXN-EXPENSE", name="Test Txn Expense", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.other_account = FinancialCategory.objects.create(
            code="TEST-TXN-OTHER", name="Test Txn Unrelated Expense", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.budget = FinanceBudget.objects.create(
            name="Test Txn Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.user,
        )
        FinanceBudgetLine.objects.create(budget=self.budget, category=self.expense_account, m01=Decimal("1000.00"))

        self.in_scope_txn = FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("250.00"), currency=get_base_currency(),
            date=date(2026, 1, 20), created_by=self.user,
        )
        # Different account entirely — not budgeted here, must not appear.
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.other_account, amount=Decimal("999.00"), currency=get_base_currency(),
            date=date(2026, 1, 20), created_by=self.user,
        )
        # Same account, but outside the budget's period — must not appear.
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("777.00"), currency=get_base_currency(),
            date=date(2027, 1, 5), created_by=self.user,
        )

    def test_lists_only_transactions_for_this_budgets_accounts_and_period(self):
        self.client.login(username="txn_view_user", password="pw")
        response = self.client.get(reverse("finance:budget_transactions", args=[self.budget.pk]))
        self.assertEqual(response.status_code, 200)
        transactions = list(response.context["transactions"])
        self.assertEqual(transactions, [self.in_scope_txn])

    def test_totals_match_the_performance_page_figures(self):
        self.client.login(username="txn_view_user", password="pw")
        response = self.client.get(reverse("finance:budget_transactions", args=[self.budget.pk]))
        self.assertEqual(response.context["budgeted_total"], self.budget.total_amount)
        self.assertEqual(response.context["actual_total"], self.budget.actual_amount)
        self.assertEqual(response.context["actual_total"], Decimal("250.00"))


class FinanceBudgetLineLedgerLinkTests(TestCase):
    """FinanceBudgetLine.total/actual_for_month/actual_total — the whole
    point of linking a budget line to a real ledger account: "actual" must
    come from FinancialTransaction, never a hand-typed figure."""

    def setUp(self):
        self.creator = make_user("budget_owner")
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-BUD-EXPENSE", name="Test Payroll", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.budget = FinanceBudget.objects.create(
            name="Test Annual Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.creator,
        )
        self.line = FinanceBudgetLine.objects.create(
            budget=self.budget, category=self.expense_account,
            m01=Decimal("1000.00"), m02=Decimal("1000.00"), m03=Decimal("1000.00"),
        )

    def test_total_sums_all_twelve_months(self):
        self.assertEqual(self.line.total, Decimal("3000.00"))

    def test_actual_for_month_is_zero_with_no_transactions(self):
        self.assertEqual(self.line.actual_for_month(2026, 1), 0)

    def test_actual_for_month_reflects_real_ledger_activity(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("450.00"), currency=get_base_currency(),
            date=date(2026, 1, 15), created_by=self.creator,
        )
        # A transaction in a different month must not bleed into January's figure.
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("999.00"), currency=get_base_currency(),
            date=date(2026, 2, 1), created_by=self.creator,
        )
        self.assertEqual(self.line.actual_for_month(2026, 1), Decimal("450.00"))
        self.assertEqual(self.line.actual_for_month(2026, 2), Decimal("999.00"))

    def test_actual_total_sums_the_whole_budget_period(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("300.00"), currency=get_base_currency(),
            date=date(2026, 1, 10), created_by=self.creator,
        )
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("200.00"), currency=get_base_currency(),
            date=date(2026, 3, 20), created_by=self.creator,
        )
        self.assertEqual(self.line.actual_total, Decimal("500.00"))

    def test_actual_scoped_to_project_when_budget_has_one(self):
        from core.project_models import Project
        own_project = Project.objects.create(name="Budget's Own Project")
        other_project = Project.objects.create(name="A Different Project")
        self.budget.project = own_project
        self.budget.save()

        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("150.00"), currency=get_base_currency(),
            date=date(2026, 1, 5), created_by=self.creator, project=own_project,
        )
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("9999.00"), currency=get_base_currency(),
            date=date(2026, 1, 6), created_by=self.creator, project=other_project,
        )
        self.assertEqual(self.line.actual_for_month(2026, 1), Decimal("150.00"))

    def test_variance_total_is_budget_minus_actual(self):
        FinancialTransaction.objects.create(
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            category=self.expense_account, amount=Decimal("1200.00"), currency=get_base_currency(),
            date=date(2026, 1, 1), created_by=self.creator,
        )
        self.assertEqual(self.line.variance_total, Decimal("3000.00") - Decimal("1200.00"))


class FinanceBudgetLineFormTests(TestCase):
    def setUp(self):
        self.leaf_account = FinancialCategory.objects.create(
            code="TEST-BUD-FORM", name="Test Form Account", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.group_account = FinancialCategory.objects.create(
            code="TEST-BUD-GROUP", name="Test Form Group", category_type=FinancialCategory.CategoryType.EXPENSE,
            is_group=True,
        )

    def test_category_is_required(self):
        form = FinanceBudgetLineForm(data={"m01": "100.00"})
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_category_queryset_excludes_groups(self):
        form = FinanceBudgetLineForm()
        queryset = form.fields["category"].queryset
        self.assertIn(self.leaf_account, queryset)
        self.assertNotIn(self.group_account, queryset)

    def test_valid_with_a_leaf_account(self):
        form = FinanceBudgetLineForm(data={"category": self.leaf_account.pk, "m01": "100.00"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_positive_amount_on_an_income_account_is_rejected(self):
        income_account = FinancialCategory.objects.create(
            code="TEST-BUD-FORM-INCOME", name="Test Form Income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        form = FinanceBudgetLineForm(data={"category": income_account.pk, "m01": "100.00"})
        self.assertFalse(form.is_valid())
        self.assertIn("m01", form.errors)

    def test_negative_amount_on_an_income_account_is_valid(self):
        income_account = FinancialCategory.objects.create(
            code="TEST-BUD-FORM-INCOME-2", name="Test Form Income 2", category_type=FinancialCategory.CategoryType.INCOME,
        )
        form = FinanceBudgetLineForm(data={"category": income_account.pk, "m01": "-100.00"})
        self.assertTrue(form.is_valid(), form.errors)


class BudgetLineFormSetBalanceTests(TestCase):
    """A budget must not save unless total expected income equals total
    expected costs — checked across Income- and Expense-type accounts only."""

    def setUp(self):
        self.creator = make_user("budget_balance_owner")
        self.income_account = FinancialCategory.objects.create(
            code="TEST-BAL-INCOME", name="Test Grant Income", category_type=FinancialCategory.CategoryType.INCOME,
        )
        self.expense_account = FinancialCategory.objects.create(
            code="TEST-BAL-EXPENSE", name="Test Programme Costs", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        self.budget = FinanceBudget.objects.create(
            name="Test Balance Budget", period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            created_by=self.creator,
        )

    def _management_form_data(self, total_forms):
        return {
            "lines-TOTAL_FORMS": str(total_forms),
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
        }

    def _line_data(self, index, category, m01="0.00"):
        data = {f"lines-{index}-category": category.pk, f"lines-{index}-m01": m01}
        for field in FinanceBudgetLine.MONTH_FIELDS[1:]:
            data[f"lines-{index}-{field}"] = "0.00"
        return data

    def test_mismatched_income_and_expense_rejected(self):
        data = self._management_form_data(2)
        data.update(self._line_data(0, self.income_account, m01="-1000.00"))
        data.update(self._line_data(1, self.expense_account, m01="500.00"))
        formset = BudgetLineFormSet(data=data, instance=self.budget)
        self.assertFalse(formset.is_valid())
        self.assertTrue(any("doesn't balance" in error for error in formset.non_form_errors()))

    def test_balanced_income_and_expense_accepted(self):
        data = self._management_form_data(2)
        data.update(self._line_data(0, self.income_account, m01="-1000.00"))
        data.update(self._line_data(1, self.expense_account, m01="1000.00"))
        formset = BudgetLineFormSet(data=data, instance=self.budget)
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_deleted_line_excluded_from_balance_check(self):
        extra_expense_account = FinancialCategory.objects.create(
            code="TEST-BAL-EXPENSE-2", name="Test Office Costs", category_type=FinancialCategory.CategoryType.EXPENSE,
        )
        data = self._management_form_data(3)
        data.update(self._line_data(0, self.income_account, m01="-1000.00"))
        data.update(self._line_data(1, self.expense_account, m01="1000.00"))
        data.update(self._line_data(2, extra_expense_account, m01="500.00"))
        data["lines-2-DELETE"] = "on"
        formset = BudgetLineFormSet(data=data, instance=self.budget)
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_negative_income_entered_as_credit_still_balances(self):
        data = self._management_form_data(2)
        data.update(self._line_data(0, self.income_account, m01="-1000.00"))
        data.update(self._line_data(1, self.expense_account, m01="1000.00"))
        formset = BudgetLineFormSet(data=data, instance=self.budget)
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_asset_lines_excluded_from_balance_check(self):
        asset_account = FinancialCategory.objects.create(
            code="TEST-BAL-ASSET", name="Test Equipment", category_type=FinancialCategory.CategoryType.ASSET,
        )
        data = self._management_form_data(3)
        data.update(self._line_data(0, self.income_account, m01="-1000.00"))
        data.update(self._line_data(1, self.expense_account, m01="1000.00"))
        data.update(self._line_data(2, asset_account, m01="99999.00"))
        formset = BudgetLineFormSet(data=data, instance=self.budget)
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_positive_income_amount_is_rejected(self):
        data = self._management_form_data(2)
        data.update(self._line_data(0, self.income_account, m01="1000.00"))
        data.update(self._line_data(1, self.expense_account, m01="1000.00"))
        formset = BudgetLineFormSet(data=data, instance=self.budget)
        self.assertFalse(formset.is_valid())
        self.assertIn("m01", formset.forms[0].errors)
