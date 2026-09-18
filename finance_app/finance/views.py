from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
import json

import pandas as pd
from django.db.models import Q, Count, ProtectedError
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, ExpressionWrapper, F, DecimalField, Value
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from account.models import Department
from assets.assetapp.models import AssetMaintenance, Asset
from core.project_models import Project, ProjectBudget
from finance_app.finance.models import AccountingForm, AdminExpenseNote, CashRequisition, CashRequisitionItem, ApprovalLog, AccountingItem
from openpyxl import Workbook
from .utils.workflow import advance_workflow, user_can_approve
from .utils.pdf import render_to_pdf
from .permissions import is_finance_staff as _is_finance_staff, can_manage_chart_of_accounts as _can_manage_chart_of_accounts
from django.db.models.functions import Coalesce
from account.templatetags.custom_tags import has_group
from procurement.procureapp.models import Requisition, PurchaseOrder
from core.services import user_amount_to_ugx, CURRENCY_LABELS, normalize_currency, get_latest_usd_rates
from .forms import FinanceBudgetForm, BudgetLineFormSet, BudgetPerformanceForm, CashBookForm, CashBookEntryForm, BankReconciliationForm, BankReconciliationItemFormSet
from .models import (
    FinanceBudget, BudgetPerformance, CashBook, BankReconciliation,
    FinancialCategory, FinancialTransaction, JournalEntry, JournalEntryLine,
)
from core.services import SUPPORTED_CURRENCIES, get_base_currency, convert_amount
from .permissions import finance_editor_required, is_finance_editor as _can_manage_chart_of_accounts
from .exports import budget_xlsx, performance_xlsx, cashbook_xlsx, reconciliation_xlsx


@login_required(login_url="login")
def dashboard(request):
    admin_expenses_qs = AdminExpenseNote.objects.select_related('department', 'project')

    is_manager = has_group(request.user, "Operations") or has_group(request.user, "Finance")

    # ✅ Base Querysets
    if is_manager:
        pending_requisitions = CashRequisition.objects.exclude(status="approved")
        approved_requisitions = CashRequisition.objects.filter(status="approved")
        admin_expenses = admin_expenses_qs.all()
        accountings = AccountingForm.objects.all()  # ✅ FIXED consistency
    else:
        pending_requisitions = CashRequisition.objects.filter(
            created_by=request.user
        ).exclude(status="approved")

        approved_requisitions = CashRequisition.objects.filter(
            created_by=request.user,
            status="approved"
        )

        admin_expenses = admin_expenses_qs.filter(created_by=request.user)
        accountings = AccountingForm.objects.filter(created_by=request.user)

    # ✅ PERFORMANCE: Always prefetch
    pending_requisitions = pending_requisitions.prefetch_related("items")
    approved_requisitions = approved_requisitions.prefetch_related("items")

    # ✅ KPI Aggregation (clean + safe)
    total_pending_amount = CashRequisition.get_total_amount(pending_requisitions)
    total_approved_amount = CashRequisition.get_total_amount(approved_requisitions)

    total_admin_expenses = admin_expenses.aggregate(
        total=Coalesce(
            Sum("proposed_budget"),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )["total"]

    accounting_totals = AccountingItem.objects.filter(
        form__in=accountings
    ).aggregate(
        total_received=Coalesce(
            Sum('amount_received'),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
        ),
        total_spent=Coalesce(
            Sum('amount_spent'),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )

    context = {
        "pending_requisitions": pending_requisitions,
        "approved_requisitions": approved_requisitions,
        "admin_expenses": admin_expenses,
        "accountings": accountings,
        "total_pending_amount": total_pending_amount,
        "total_approved_amount": total_approved_amount,
        "total_admin_expenses": total_admin_expenses,
        "total_received": accounting_totals["total_received"],
        "total_spent": accounting_totals["total_spent"],
        "finance_budgets": FinanceBudget.objects.select_related("project").all()[:8],
        "cash_books": CashBook.objects.select_related("project").all()[:8],
    }

    return render(request, "finance/dashboard.html", context)


@login_required(login_url="login")
def budget_list(request):
    return render(request, "finance/budget_list.html", {"budgets": FinanceBudget.objects.select_related("project", "created_by").all()})


@login_required(login_url="login")
def budget_detail(request, pk):
    budget = get_object_or_404(FinanceBudget.objects.select_related("project").prefetch_related("lines", "performance_records__line"), pk=pk)
    return render(request, "finance/budget_detail.html", {"budget": budget})


@login_required(login_url="login")
@finance_editor_required
def budget_create(request, pk=None):
    instance = get_object_or_404(FinanceBudget, pk=pk) if pk else None
    form = FinanceBudgetForm(request.POST or None, instance=instance)
    formset = BudgetLineFormSet(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        budget = form.save(commit=False)
        if not budget.pk:
            budget.created_by = request.user
        budget.save()
        formset.instance = budget
        formset.save()
        messages.success(request, "Budget saved successfully.")
        return redirect("finance:budget_detail", pk=budget.pk)
    return render(request, "finance/budget_form.html", {"form": form, "formset": formset, "budget": instance})


@login_required(login_url="login")
@finance_editor_required
def budget_delete(request, pk):
    budget = get_object_or_404(FinanceBudget, pk=pk)
    if request.method == "POST":
        budget.delete(); messages.success(request, "Budget deleted."); return redirect("finance:budget_list")
    return render(request, "finance/confirm_delete.html", {"object": budget, "cancel_url": reverse("finance:budget_detail", args=[budget.pk])})


@login_required(login_url="login")
def performance_list(request):
    records = BudgetPerformance.objects.select_related("budget", "line").all()
    return render(request, "finance/budget_performance_list.html", {"records": records})


@login_required(login_url="login")
@finance_editor_required
def performance_create(request):
    form = BudgetPerformanceForm(request.POST or None)
    if form.is_valid():
        record = form.save(commit=False); record.created_by = request.user; record.save(); messages.success(request, "Budget performance record saved."); return redirect("finance:performance_list")
    return render(request, "finance/budget_performance_form.html", {"form": form})


@login_required(login_url="login")
def cashbook_list(request):
    return render(request, "finance/cashbook_list.html", {"cash_books": CashBook.objects.select_related("project", "created_by").all()})


@login_required(login_url="login")
def cashbook_detail(request, pk):
    cash_book = get_object_or_404(CashBook.objects.select_related("project").prefetch_related("entries", "bank_reconciliation"), pk=pk)
    form = CashBookEntryForm()
    if request.method == "POST":
        form = CashBookEntryForm(request.POST)
        if not (request.user.is_superuser or request.user.groups.filter(name__iexact="Finance").exists()):
            messages.error(request, "Only Finance staff or a superuser can add cash book entries.")
        elif form.is_valid():
            entry = form.save(commit=False); entry.cash_book = cash_book; entry.created_by = request.user; entry.save(); messages.success(request, "Cash book entry added."); return redirect("finance:cashbook_detail", pk=pk)
    return render(request, "finance/cashbook_detail.html", {"cash_book": cash_book, "form": form})


@login_required(login_url="login")
@finance_editor_required
def cashbook_create(request):
    form = CashBookForm(request.POST or None)
    if form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save(); messages.success(request, "Cash book created."); return redirect("finance:cashbook_detail", pk=obj.pk)
    return render(request, "finance/cashbook_form.html", {"form": form})


@login_required(login_url="login")
@finance_editor_required
def cashbook_delete(request, pk):
    obj = get_object_or_404(CashBook, pk=pk)
    if request.method == "POST":
        obj.delete(); messages.success(request, "Cash book deleted."); return redirect("finance:cashbook_list")
    return render(request, "finance/confirm_delete.html", {"object": obj, "cancel_url": reverse("finance:cashbook_detail", args=[obj.pk])})


@login_required(login_url="login")
@finance_editor_required
def reconciliation_create(request, cash_book_pk):
    cash_book = get_object_or_404(CashBook, pk=cash_book_pk)
    reconciliation = getattr(cash_book, "bank_reconciliation", None)
    form = BankReconciliationForm(request.POST or None, instance=reconciliation)
    formset = BankReconciliationItemFormSet(request.POST or None, instance=reconciliation)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        obj = form.save(commit=False); obj.cash_book = cash_book; obj.prepared_by = request.user; obj.save(); formset.instance = obj; formset.save(); messages.success(request, "Bank reconciliation saved."); return redirect("finance:reconciliation_detail", pk=obj.pk)
    return render(request, "finance/reconciliation_form.html", {"form": form, "formset": formset, "cash_book": cash_book})


@login_required(login_url="login")
def reconciliation_detail(request, pk):
    obj = get_object_or_404(BankReconciliation.objects.select_related("cash_book").prefetch_related("items"), pk=pk)
    return render(request, "finance/reconciliation_detail.html", {"reconciliation": obj})


@login_required(login_url="login")
def export_budget(request, pk): return budget_xlsx(get_object_or_404(FinanceBudget, pk=pk), request=request)


@login_required(login_url="login")
def export_performance(request, pk): return performance_xlsx(get_object_or_404(FinanceBudget, pk=pk), request=request)


@login_required(login_url="login")
def export_cashbook(request, pk): return cashbook_xlsx(get_object_or_404(CashBook.objects.prefetch_related("entries"), pk=pk), request=request)


@login_required(login_url="login")
def export_reconciliation(request, pk): return reconciliation_xlsx(get_object_or_404(BankReconciliation.objects.select_related("cash_book").prefetch_related("items"), pk=pk), request=request)


@login_required(login_url="login")
@finance_editor_required
def create_cash_requisition(request):
    if request.method == "POST":
        with transaction.atomic():
            currency = normalize_currency(request.POST.get("currency") or get_base_currency())
            procurement_requisition_id = request.POST.get("procurement_requisition") or None
            purchase_order_id = request.POST.get("purchase_order") or None
            purchase_order = None

            if purchase_order_id:
                purchase_order_filters = {"pk": purchase_order_id}
                if procurement_requisition_id:
                    purchase_order_filters["requisition_id"] = procurement_requisition_id

                purchase_order = get_object_or_404(PurchaseOrder, **purchase_order_filters)
                procurement_requisition_id = procurement_requisition_id or purchase_order.requisition_id
            elif procurement_requisition_id:
                purchase_order = PurchaseOrder.objects.filter(
                    requisition_id=procurement_requisition_id
                ).order_by("-sent", "-issue_date", "-created_at", "-pk").first()

            obj = CashRequisition.objects.create(
                procurement_requisition_id=procurement_requisition_id,
                purchase_order=purchase_order,
                donor_code=request.POST.get("donor_code"),
                purpose=request.POST.get("purpose"),
                created_by=request.user,
                status="draft",
                date=request.POST.get("date"),
                to="Executive Director",
                currency=currency,
                attachment=request.FILES.get("attachment"),
            )

            index = 0
            while f"items[{index}][activity_code]" in request.POST:
                original_unit_cost = request.POST.get(f"items[{index}][unit_cost]") or 0
                CashRequisitionItem.objects.create(
                    requisition=obj,
                    activity_code=request.POST.get(f"items[{index}][activity_code]"),
                    program_code=request.POST.get(f"items[{index}][program_code]"),
                    particulars=request.POST.get(f"items[{index}][particulars]"),
                    quantity=request.POST.get(f"items[{index}][quantity]") or 0,
                    unit_cost=convert_amount(original_unit_cost, currency, get_base_currency()),
                    original_unit_cost=original_unit_cost,
                )
                index += 1

        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    return render(request, "finance/create_cash_requisition.html", {
        "procurement_requisitions": Requisition.objects.filter(status="Approved").order_by("-date"),
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
    })


@login_required(login_url="login")
@finance_editor_required
def create_cash_requisition_from_procurement(request, req_pk):
    procurement_req = get_object_or_404(Requisition, pk=req_pk, status="Approved")
    purchase_order = get_object_or_404(
        PurchaseOrder.objects.order_by("-sent", "-issue_date", "-created_at", "-pk"),
        requisition=procurement_req,
    )

    # Check whether a cash requisition already exists
    cash_req = CashRequisition.objects.filter(procurement_requisition=procurement_req).first()
    if cash_req:
        messages.info(request, f"Cash request for {procurement_req} has already been created.")
        return redirect(reverse("finance:requisition_detail", kwargs={'pk':cash_req.pk, 'slug':cash_req.slug}))

    initial_items = procurement_req.items.all()

    return render(request, "finance/create_cash_requisition.html",
        {
            "procurement_req": procurement_req,
            "po": purchase_order,
            "initial_items": initial_items,
            "procurement_requisitions": Requisition.objects.filter(status="Approved").order_by("-date"),
            "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        },
    )


@login_required(login_url="login")
def requisition_list(request):
    qs = CashRequisition.objects.all().order_by("-created_at")
    return render(request, "finance/req_list.html", {"objects": qs})


@login_required(login_url="login")
def requisition_detail(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk, slug=slug)

    return render(request, "finance/req_detail.html", {
        "obj": obj,
        "items": obj.items.all(),
        "accounting": obj.accountings if hasattr(obj, "accountings") else "",
        "admin_expense": obj.admin_concept if hasattr(obj, "admin_concept") else "",
    })


@login_required(login_url="login")
@finance_editor_required
def submit_requisition(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk,  slug=slug, created_by=request.user)

    if obj.status != "draft":
        messages.error(request, "Already submitted")
        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    obj.status = "submitted"
    obj.save()

    return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))


@login_required(login_url="login")
@finance_editor_required
def approve_requisition(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk,  slug=slug)

    if user_can_approve(request.user, obj):
        advance_workflow(obj, request.user)

    else:
        messages.warning(request, "Unauthorized action")
        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    obj.save()

    # AUDIT LOG
    ApprovalLog.objects.create(
        user=request.user,
        action=f"Approved {obj.status}",
        form_type="CashRequisition",
        object_id=obj.id
    )

    return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))


@login_required(login_url="login")
def requisition_pdf(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk, slug=slug)

    if obj.status != "approved":
        return HttpResponse("Not authorized", status=403)
    context = {
        "obj": obj,
        "request": request,
    }

    pdf = render_to_pdf("finance/requisition_pdf.html", context)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="fund_requisition_{obj.id}.pdf"'

    return response


@login_required(login_url="login")
@finance_editor_required
def reject_requisition(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk,  slug=slug)

    if request.method == "POST":
        reason = request.POST.get("reason")

        if not reason:
            messages.error(request, "Rejection reason is required.")
            return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

        obj.status = "rejected"
        obj.reason_for_rejection = reason
        obj.save()

        ApprovalLog.objects.create(
            user=request.user,
            action=f"Rejected: {reason}",
            form_type="CashRequisition",
            object_id=obj.id
        )

    return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))


@login_required(login_url="login")
@transaction.atomic
@finance_editor_required
def save_accounting(request, slug=None, pk=None, req_slug=None, req_pk=None):

    obj = None
    requisition = None

    # UPDATE MODE
    if slug and pk:
        obj = get_object_or_404(AccountingForm, slug=slug, pk=pk)

        if obj.created_by != request.user or obj.status != "submitted":
            messages.warning(request, "You cannot edit this record.")
            return redirect("finance:accounting_detail", pk=obj.pk, slug=obj.slug)

    # CREATE MODE
    if req_slug and req_pk:
        requisition = get_object_or_404(CashRequisition, slug=req_slug, pk=req_pk)

    if request.method == "POST":
        description = request.POST.get("description")
        date_of_return = request.POST.get("date_of_return")

        if not obj:
            obj = AccountingForm.objects.create(
                requisition=requisition,
                created_by=request.user,
                donor_code=requisition.donor_code,
                description=description,
                date_of_return=date_of_return,
                status="submitted"
            )
        else:
            obj.description = description
            obj.date_of_return = date_of_return
            obj.save()
            obj.items.all().delete()

        # Extract arrays
        activities = request.POST.getlist("activity_code[]")
        programs = request.POST.getlist("program_code[]")
        details = request.POST.getlist("details[]")
        received = request.POST.getlist("received[]")
        spent = request.POST.getlist("spent[]")

        items = []
        for a, p, d, r, s in zip(activities, programs, details, received, spent):
            items.append(AccountingItem(
                form=obj,
                activity_code=a,
                program_code=p,
                details=d,
                amount_received=user_amount_to_ugx(r or 0, request),
                amount_spent=user_amount_to_ugx(s or 0, request),
            ))

        AccountingItem.objects.bulk_create(items)

        return redirect(reverse("finance:accounting_detail", kwargs={
            "pk": obj.pk,
            "slug": obj.slug
        }))

    return render(request, "finance/account_form.html", {
        "form_obj": obj,
        "requisition": requisition or getattr(obj, "requisition", None),
        "items": obj.items.all() if obj else []
    })


@login_required(login_url="login")
@finance_editor_required
def approve_account_form(request, pk, slug):
    obj = get_object_or_404(AccountingForm, pk=pk,  slug=slug)

    if user_can_approve(request.user, obj):
        advance_workflow(obj, request.user)

    else:
        messages.warning(request, "Unauthorized action")
        return redirect(reverse("finance:accounting_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    return redirect(reverse("finance:accounting_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))


@login_required(login_url="login")
def accounting_detail(request, pk, slug):
    obj = get_object_or_404(AccountingForm, pk=pk, slug=slug)

    items = obj.items.all()

    totals = items.aggregate(
        total_received=Sum('amount_received'),
        total_spent=Sum('amount_spent')
    )

    total_received = totals['total_received'] or 0
    total_spent = totals['total_spent'] or 0

    totals['balance'] = total_received - total_spent

    return render(request, "finance/account_detail.html", {
        "obj": obj,
        "items": items,
        "total_received": total_received,
        "total_spent": total_spent,
    })


@login_required(login_url="login")
def accounting_pdf(request, pk, slug):
    obj = get_object_or_404(AccountingForm, pk=pk,  slug=slug)

    items = obj.items.all()

    totals = items.aggregate(
        total_received=Sum('amount_received'),
        total_spent=Sum('amount_spent')
    )

    total_received = totals['total_received'] or 0
    total_spent = totals['total_spent'] or 0

    if obj.status != "approved":
        return HttpResponse("Not authorized", status=403)
    pdf = render_to_pdf("finance/accounting_pdf.html",
                        {"obj": obj,
                         "total_received": total_received,
                         "total_spent": total_spent, "request":request})

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="account_form_{obj.reference}.pdf"'

    return response


@login_required(login_url="login")
@finance_editor_required
def create_admin_expense(request, slug, pk):
    cash_req = get_object_or_404(CashRequisition, slug=slug, pk=pk)
    if request.method == "POST":
        obj = AdminExpenseNote.objects.create(
            cash_req=cash_req,
            department_id=request.POST.get("department"),
            purpose=request.POST.get("purpose"),
            project_id=request.POST.get("project"),
            timeframe_from=request.POST.get("timeframe_from"),
            timeframe_to=request.POST.get("timeframe_to"),
            location=request.POST.get("location"),
            objectives=request.POST.get("objectives"),
            expected_outputs=request.POST.get("expected_outputs"),
            proposed_budget=user_amount_to_ugx(request.POST.get("proposed_budget") or 0, request),
            service_providers=request.POST.get("service_providers"),
            created_by=request.user,
            status="draft",
        )
        return redirect(reverse("finance:admin_expense_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))

    return render(request, "finance/admin_expense/create.html",
                  {
                      "cash_req": cash_req,
                      "departments": Department.objects.all(),
                      "projects": Project.objects.all()}
                  )


@login_required(login_url="login")
def admin_expense_detail(request, pk, slug):
    obj = get_object_or_404(AdminExpenseNote, pk=pk,  slug=slug)

    return render(request, "finance/admin_expense/detail.html", {"obj": obj})


@login_required(login_url="login")
@finance_editor_required
def submit_admin_expense(request, pk, slug):
    obj = get_object_or_404(AdminExpenseNote, pk=pk,  slug=slug)

    if obj.created_by != request.user:
        return HttpResponseForbidden()

    obj.status = "submitted"
    obj.save()

    return redirect(reverse("finance:admin_expense_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))


@login_required(login_url="login")
@finance_editor_required
def approve_admin_expense(request, pk, slug):
    obj = get_object_or_404(AdminExpenseNote, pk=pk, slug=slug)

    user = request.user

    is_assets = has_group(user, 'Assets')
    is_operations = has_group(user, 'Operations')
    is_finance = has_group(user, 'Finance')

    if request.method == "POST":

        # STEP 1: Initial review (any department)
        if obj.status == "submitted":
            if is_assets or is_operations or is_finance:
                obj.status = "under_review"
                obj.checked_by = user
                obj.reviewed_by = user
                obj.save()
                messages.success(request, "Expense moved to review stage.")
            else:
                messages.error(request, "You are not authorized to review this expense.")

        # STEP 2: Final approval (Finance or Operations only)
        elif obj.status == "under_review" and obj.cash_req.checked_by == user:
            if is_finance or is_operations:
                obj.status = "approved"
                obj.approved_by = user
                obj.save()
                messages.success(request, "Expense approved successfully.")
            else:
                messages.error(request, "Only Finance or Operations can approve.")

        else:
            messages.warning(request, f"No action allowed at '{obj.status}' stage."
                                      f" Confirm you checked the linked requisition else won't be allowed to approve.")
    else:
        messages.error(request, "Invalid request method.")
        return redirect(reverse("finance:admin_expense_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))
    return redirect(reverse("finance:admin_expense_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))


@login_required(login_url="login")
def admin_expense_pdf(request, pk, slug):
    obj = get_object_or_404(AdminExpenseNote, pk=pk, slug=slug)

    if obj.status != "approved":
        return HttpResponse("Not authorized", status=403)
    pdf = render_to_pdf("finance/admin_expense_pdf.html", {"obj": obj, 'request':request})

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="admin_expense_note_{obj.id}.pdf"'

    return response


# ---------------------------------------------------------------------------
# Double-entry ledger and reporting views
# ---------------------------------------------------------------------------

DECIMAL_ZERO = DecimalField(max_digits=16, decimal_places=2)


def _filter_ledger(request):
    transactions = FinancialTransaction.objects.select_related(
        "category", "project", "department", "created_by"
    )

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    project_id = request.GET.get("project")
    department_id = request.GET.get("department")
    category_id = request.GET.get("category")
    transaction_type = request.GET.get("type")
    currency = request.GET.get("currency")

    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    if project_id:
        transactions = transactions.filter(project_id=project_id)
    if department_id:
        transactions = transactions.filter(department_id=department_id)
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if currency:
        transactions = transactions.filter(currency=currency)

    return transactions, project_id


@login_required(login_url="login")
def financial_ledger(request):
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can view the organization-wide ledger.")
        return redirect(reverse("finance:dashboard"))

    transactions, project_id = _filter_ledger(request)

    totals = transactions.aggregate(
        total_income=Coalesce(Sum("amount", filter=Q(transaction_type="income")), Value(0), output_field=DECIMAL_ZERO),
        total_expense=Coalesce(Sum("amount", filter=Q(transaction_type="expense")), Value(0), output_field=DECIMAL_ZERO),
        total_transfer=Coalesce(Sum("amount", filter=Q(transaction_type="transfer")), Value(0), output_field=DECIMAL_ZERO),
    )
    net_position = totals["total_income"] - totals["total_expense"]

    category_breakdown = transactions.values("category__name", "category__code").annotate(
        total=Sum("amount")
    ).order_by("-total")

    # Grouped by the currency the money actually moved in — donor reports
    # usually need the real USD/KES/etc figure, not just the UGX-blended
    # total, which mixing currencies into one Sum would silently misstate.
    currency_breakdown = transactions.values("currency").annotate(
        total_original=Coalesce(Sum("original_amount"), Value(0), output_field=DECIMAL_ZERO),
        total_ugx=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_ZERO),
        txn_count=Count("id"),
    ).order_by("-total_ugx")

    # Read-only cross-module snapshot — Procurement and Assets keep recording
    # their own spend independently; this surfaces it alongside the ledger
    # rather than duplicating it as ledger entries.
    po_qs = PurchaseOrder.objects.filter(sent=True)
    if project_id:
        po_qs = po_qs.filter(procurement_plan__project_id=project_id)
    procurement_total = po_qs.aggregate(
        total=Coalesce(Sum("final_amount"), Value(0), output_field=DECIMAL_ZERO)
    )["total"]

    asset_totals = Asset.objects.aggregate(
        purchase_value=Coalesce(Sum("purchase_value"), Value(0), output_field=DECIMAL_ZERO),
        depreciation_accumulated=Coalesce(Sum("depreciation_accumulated"), Value(0), output_field=DECIMAL_ZERO),
    )
    maintenance_total = AssetMaintenance.objects.aggregate(
        total=Coalesce(Sum("cost"), Value(0), output_field=DECIMAL_ZERO)
    )["total"]

    project_budget_total = None
    if project_id:
        project_budget_total = ProjectBudget.objects.filter(project_id=project_id).aggregate(
            total=Coalesce(Sum("budget_amount"), Value(0), output_field=DECIMAL_ZERO)
        )["total"]

    context = {
        "transactions": transactions[:200],
        "transaction_count": transactions.count(),
        "totals": totals,
        "net_position": net_position,
        "category_breakdown": category_breakdown,
        "currency_breakdown": currency_breakdown,
        "base_currency": get_base_currency(),
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "procurement_total": procurement_total,
        "asset_totals": asset_totals,
        "maintenance_total": maintenance_total,
        "project_budget_total": project_budget_total,
        "projects": Project.objects.all(),
        "departments": Department.objects.all(),
        "categories": FinancialCategory.objects.filter(is_group=False),
        "transaction_types": FinancialTransaction.TransactionType.choices,
        "filters": request.GET,
    }
    return render(request, "finance/ledger.html", context)


@login_required(login_url="login")
def financial_ledger_export(request):
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can export the organization-wide ledger.")
        return redirect(reverse("finance:dashboard"))

    transactions, _ = _filter_ledger(request)
    base_currency = get_base_currency()

    wb = Workbook()
    ws = wb.active
    ws.title = "Financial Ledger"

    ws.append([
        "Reference", "Date", "Type", "Category", "Project", "Department",
        "Donor Code", "Description", "Currency", "Original Amount",
        "Exchange Rate Used", f"Amount ({base_currency})",
    ])

    for txn in transactions:
        ws.append([
            txn.reference,
            txn.date.isoformat() if txn.date else "",
            txn.get_transaction_type_display(),
            txn.category.name,
            str(txn.project) if txn.project else "",
            str(txn.department) if txn.department else "",
            txn.donor_code,
            txn.description,
            txn.currency,
            float(txn.original_amount) if txn.original_amount is not None else float(txn.amount),
            float(txn.exchange_rate_used) if txn.exchange_rate_used is not None else 1.0,
            float(txn.amount),
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="financial_ledger.xlsx"'
    wb.save(response)
    return response


def _parse_opening_balance(raw):
    raw = (raw or "0").replace(",", "").strip()
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _is_descendant_or_self(candidate, node):
    """True if `candidate` is `node` itself or sits anywhere under it — used
    to block re-parenting a group underneath one of its own descendants,
    which would otherwise create a cycle in the tree."""
    while candidate is not None:
        if candidate.pk == node.pk:
            return True
        candidate = candidate.parent
    return False


def _build_account_tree(only_groups=False, as_of_date=None, report_currency=None, category_types=None, rates=None):
    """Fetch every FinancialCategory, annotate leaf accounts with their
    transaction count and closing balance (in the account's own currency),
    and wire them into an in-memory tree via `.tree_children`. Also computes
    `.rollup_base` on every node — its own (for leaves) or its descendants'
    (for groups) closing balance converted into report_currency (defaults
    to the org's base currency), so groups mixing accounts of different
    currencies still get one meaningful total. Returns (root_nodes,
    all_nodes_by_id).

    `as_of_date` restricts the balance to transactions up to and including
    that date (a point-in-time snapshot, e.g. for the Balance Sheet)
    instead of the account's all-time balance (the Chart of Accounts'
    default). `category_types` restricts to a subset of the 5 root types
    (e.g. just Assets, for the Balance Sheet's Assets section).
    """
    base_currency = get_base_currency()
    report_currency = report_currency or base_currency
    rates = rates or get_latest_usd_rates()
    qs = FinancialCategory.objects.select_related("parent")
    if category_types:
        qs = qs.filter(category_type__in=category_types)
    if only_groups:
        qs = qs.filter(is_group=True)
    else:
        txn_filter = Q(transactions__date__lte=as_of_date) if as_of_date else Q()
        qs = qs.annotate(
            transaction_count=Coalesce(Count("transactions", filter=txn_filter, distinct=True), Value(0)),
            total_amount=Coalesce(Sum("transactions__amount", filter=txn_filter), Value(0), output_field=DECIMAL_ZERO),
        )
    categories = list(qs.order_by("category_type", "code"))

    by_id = {c.pk: c for c in categories}
    for c in categories:
        c.tree_children = []
        if not c.is_group:
            # total_amount is already base-currency-equivalent (how
            # FinancialTransaction.amount is always recorded) — convert it
            # into this account's own currency to get its native balance.
            c.closing_balance = c.opening_balance + convert_amount(c.total_amount, base_currency, c.currency, rates=rates)

    roots = []
    for c in categories:
        parent = by_id.get(c.parent_id) if c.parent_id else None
        if parent is not None:
            parent.tree_children.append(c)
        else:
            roots.append(c)

    if not only_groups:
        def compute_rollup(node):
            if node.is_group:
                node.rollup_base = sum((compute_rollup(child) for child in node.tree_children), Decimal("0.00"))
            else:
                node.rollup_base = convert_amount(node.closing_balance, node.currency, report_currency, rates=rates)
            return node.rollup_base

        for root in roots:
            compute_rollup(root)

    return roots, by_id


@login_required(login_url="login")
def chart_of_accounts(request):
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can view the chart of accounts.")
        return redirect(reverse("finance:dashboard"))

    can_manage = _can_manage_chart_of_accounts(request.user)

    if request.method == "POST":
        if not can_manage:
            messages.error(request, "You do not have permission to manage the chart of accounts.")
            return redirect(reverse("finance:chart_of_accounts"))

        category = get_object_or_404(FinancialCategory, pk=request.POST.get("category_id"))
        name = (request.POST.get("name") or "").strip()
        alt_code = (request.POST.get("alt_code") or "").strip().upper()
        currency = normalize_currency(request.POST.get("currency"))
        opening_balance = _parse_opening_balance(request.POST.get("opening_balance"))
        parent_id = request.POST.get("parent_id")
        parent = FinancialCategory.objects.filter(pk=parent_id, is_group=True).first() if parent_id else None

        if not name:
            messages.error(request, "Name is required.")
        elif opening_balance is None:
            messages.error(request, "Enter a valid opening balance.")
        elif parent_id and parent is None:
            messages.error(request, "Choose a valid group.")
        elif parent is not None and _is_descendant_or_self(parent, category):
            messages.error(request, "A group can't be moved under itself or one of its own sub-groups.")
        else:
            category.name = name
            category.alt_code = alt_code
            category.opening_balance = opening_balance
            if not category.is_group:
                category.currency = currency
            if parent is not None:
                category.category_type = parent.category_type
                category.parent = parent
            category.save(update_fields=["name", "alt_code", "opening_balance", "currency", "category_type", "parent"])
            messages.success(request, f"Account '{category.code}' updated.")
        return redirect(reverse("finance:chart_of_accounts"))

    account_tree_roots, _ = _build_account_tree()
    group_tree_roots, _ = _build_account_tree(only_groups=True)

    context = {
        "account_tree_roots": account_tree_roots,
        "group_tree_roots": group_tree_roots,
        "can_manage": can_manage,
        "total_accounts": FinancialCategory.objects.filter(is_group=False).count(),
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "base_currency": get_base_currency(),
    }
    return render(request, "finance/chart_of_accounts.html", context)


@login_required(login_url="login")
def add_account(request):
    if not _can_manage_chart_of_accounts(request.user):
        messages.error(request, "Only Finance staff can add new accounts to the chart of accounts.")
        return redirect(reverse("finance:chart_of_accounts"))

    if request.method == "POST":
        code = (request.POST.get("code") or "").strip().upper()
        alt_code = (request.POST.get("alt_code") or "").strip().upper()
        name = (request.POST.get("name") or "").strip()
        is_group = request.POST.get("is_group") == "on"
        currency = normalize_currency(request.POST.get("currency"))
        opening_balance = _parse_opening_balance(request.POST.get("opening_balance"))
        parent = FinancialCategory.objects.filter(pk=request.POST.get("parent_id"), is_group=True).first()

        if not (code and name):
            messages.error(request, "Code and name are required.")
        elif parent is None:
            messages.error(request, "Choose the group this account/sub-group belongs under.")
        elif opening_balance is None:
            messages.error(request, "Enter a valid opening balance.")
        elif FinancialCategory.objects.filter(code=code).exists():
            messages.error(request, f"A category with code '{code}' already exists.")
        else:
            FinancialCategory.objects.create(
                code=code, alt_code=alt_code, name=name, parent=parent,
                category_type=parent.category_type, is_group=is_group,
                currency=currency, opening_balance=Decimal("0.00") if is_group else opening_balance,
            )
            messages.success(request, f"{'Group' if is_group else 'Account'} '{name}' added to the chart of accounts.")
            return redirect(reverse("finance:chart_of_accounts"))

    group_tree_roots, _ = _build_account_tree(only_groups=True)

    # A next-available-code suggestion per group, so picking a group in the
    # picker can pre-fill Code with a sensible number instead of leaving
    # Finance staff to invent one from scratch. The step between siblings
    # shrinks by a factor of 10 with each level of nesting — matching the
    # org's own numbering convention (1000 Assets -> 1100 Current Assets
    # children step by hundreds, 1600 Loans and Advances' children step by
    # tens, 1650 Securities and Deposits' children step by ones) — derived
    # from how many trailing zeros the PARENT's own code has, rather than
    # a flat +10 that would suggest 1661 for a new child of 1650 instead
    # of the correct 1652.
    all_categories = list(FinancialCategory.objects.values("pk", "parent_id", "code"))
    children_codes_by_parent = {}
    for c in all_categories:
        if c["parent_id"] is not None and c["code"].isdigit():
            children_codes_by_parent.setdefault(c["parent_id"], []).append(int(c["code"]))

    def numbering_step(code):
        if not code.isdigit():
            return 10
        stripped = code.rstrip("0")
        trailing_zeros = len(code) - len(stripped)
        return 10 ** (trailing_zeros - 1) if trailing_zeros else 1

    all_existing_codes = {c["code"] for c in all_categories}

    next_code_by_group_id = {}
    for group in FinancialCategory.objects.filter(is_group=True):
        base = int(group.code) if group.code.isdigit() else 0
        step = numbering_step(group.code)
        siblings = children_codes_by_parent.get(group.pk, [])
        candidate = max(siblings, default=base) + step
        # A sibling-based suggestion can still land on a code already used
        # elsewhere in the tree (e.g. a direct child of "1000 Assets" with
        # existing children up to 1900 would suggest 2000 — the next root's
        # own code). Keep stepping forward until it's actually free.
        while str(candidate) in all_existing_codes:
            candidate += step
        next_code_by_group_id[group.pk] = str(candidate)

    # "Add Child" on a group's row action toolbar links here with the
    # parent already known — skip making Finance staff re-pick it.
    preselected_parent = FinancialCategory.objects.filter(pk=request.GET.get("parent_id"), is_group=True).first()

    context = {
        "group_tree_roots": group_tree_roots,
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "base_currency": get_base_currency(),
        "default_is_group": request.GET.get("is_group") == "1",
        "next_code_by_group_id_json": json.dumps(next_code_by_group_id),
        "preselected_parent": preselected_parent,
    }
    return render(request, "finance/add_account.html", context)


@login_required(login_url="login")
def delete_account(request, pk):
    if not _can_manage_chart_of_accounts(request.user):
        messages.error(request, "Only Finance staff can delete accounts.")
        return redirect(reverse("finance:chart_of_accounts"))

    category = get_object_or_404(FinancialCategory, pk=pk)

    if request.method == "POST":
        if category.parent_id is None:
            messages.error(request, "Root account groups can't be deleted.")
        else:
            name = category.name
            try:
                category.delete()
                messages.success(request, f"'{name}' deleted from the chart of accounts.")
            except ProtectedError:
                # Mirrors the two PROTECT constraints on FinancialCategory:
                # a group can't be deleted while it still has children, and
                # a leaf can't be deleted while transactions reference it.
                if category.is_group:
                    messages.error(request, f"Can't delete '{name}' — it still has sub-accounts under it. Move or remove those first.")
                else:
                    messages.error(request, f"Can't delete '{name}' — it has transactions recorded against it.")

    return redirect(reverse("finance:chart_of_accounts"))


@login_required(login_url="login")
def reports_home(request):
    """
    Landing page for every Accounting report — the single place reports
    live instead of each one getting its own line in the sidebar. New
    report types get added here as cards, not as more sidebar entries.
    """
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    reports = [
        {
            "name": "General Ledger",
            "description": "Opening balance, every transaction, and the running balance for one or more accounts over a period.",
            "url": reverse("finance:general_ledger_report"),
            "icon": "fa-file-lines",
        },
        {
            "name": "Income Statement",
            "description": "Income and expenses for a period, grouped the same way as the Chart of Accounts, with the net result.",
            "url": reverse("finance:income_statement_report"),
            "icon": "fa-scale-unbalanced",
        },
        {
            "name": "Budget vs Actual",
            "description": "Each project's approved budget against what was actually spent, with variance and utilization.",
            "url": reverse("finance:budget_vs_actual_report"),
            "icon": "fa-chart-pie",
        },
        {
            "name": "Balance Sheet",
            "description": "Assets, Liabilities, and Equity as of a chosen date, grouped like the Chart of Accounts.",
            "url": reverse("finance:balance_sheet_report"),
            "icon": "fa-scale-balanced",
        },
    ]
    return render(request, "finance/reports_home.html", {"reports": reports})


def _decimal_sum(series):
    total = series.sum()
    return total if isinstance(total, Decimal) else Decimal("0.00")


def _general_ledger_filter_defaults(request):
    today = date.today()
    return {
        "start_date": request.GET.get("start_date") or date(today.year, 1, 1).isoformat(),
        "end_date": request.GET.get("end_date") or today.isoformat(),
        "department": request.GET.get("department") or "",
        "project": request.GET.get("project") or "",
        "currency": normalize_currency(request.GET.get("currency") or get_base_currency()),
    }


# The full set of optional columns the General Ledger report can show,
# picked before the report runs (not toggled after the fact) — persisted
# client-side (localStorage) so the choice sticks until the user changes
# it again, without needing a server-side preferences model.
GL_OPTIONAL_FIELDS = [
    ("debit_base", "Debit (Base Currency)"),
    ("credit_base", "Credit (Base Currency)"),
    ("balance_base", "Balance (Base Currency)"),
    ("debit_original", "Debit (Original Currency)"),
    ("credit_original", "Credit (Original Currency)"),
    ("balance_original", "Balance (Original Currency)"),
    ("project", "Project"),
    ("department", "Department"),
]
GL_DEFAULT_FIELDS = ["debit_base", "credit_base", "balance_base"]


@login_required(login_url="login")
def general_ledger_report(request):
    """
    The General Ledger report's filter form. Submitting it opens the
    actual report in its own full page (general_ledger_report_view) —
    this page only ever shows the filter controls, never the report
    itself, so it stays lightweight (no report computation here) and the
    report gets the whole screen instead of sharing it with a filter form.
    """
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    leaf_accounts = FinancialCategory.objects.filter(is_group=False).select_related("parent").order_by("category_type", "code")
    selected_account_ids = [v for v in request.GET.getlist("accounts") if v]

    context = {
        "all_accounts": leaf_accounts,
        "selected_account_ids": selected_account_ids,
        "departments": Department.objects.all(),
        "projects": Project.objects.all(),
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "filters": _general_ledger_filter_defaults(request),
        "optional_fields": GL_OPTIONAL_FIELDS,
        "selected_fields": request.GET.getlist("fields") or None,
        "default_fields": GL_DEFAULT_FIELDS,
    }
    return render(request, "finance/general_ledger_report.html", context)


@login_required(login_url="login")
def general_ledger_report_view(request):
    """
    The General Ledger report itself — a standalone full page (not the
    normal app chrome/sidebar) so the report gets the full screen and,
    just as importantly, printing it naturally prints only the report:
    there's no sidebar/header/breadcrumb in this template to suppress
    with print CSS in the first place.

    Per-account transaction statement with a running balance — pick one or
    more leaf accounts, a period, and optional Department/Project filters,
    and get an "opening balance -> each transaction -> closing balance"
    listing for each account, the way a classic general ledger report
    reads. Amounts are shown in one report-wide currency (converted from
    each transaction's base-currency-equivalent amount), not each
    account's own native currency, so multiple accounts stay comparable
    on one report.

    Every transaction posted to an account is shown as a Debit or Credit
    based on that ACCOUNT's natural balance side (FinancialCategory.
    balance_side) — the same additive-only convention the rest of the app
    already uses for closing balances (see FinancialCategory.
    NATURAL_BALANCE_SIDE). This app doesn't record independent debit/
    credit legs per transaction, so this is the one convention that keeps
    this report's running balance consistent with the balance shown
    everywhere else for the same account, rather than inventing a second,
    conflicting notion of "debit vs credit" just for this report.

    The per-account transaction processing (running balance, debit/credit
    split, period totals) is done with pandas rather than a hand-rolled
    Python loop — object-dtype Series keep every amount an exact Decimal
    (verified: no float precision loss), and cumsum()/sum() give the
    running balance and period totals in one vectorized pass instead of
    manually accumulating three separate counters per row. This is also
    the foundation future reports (Trial Balance, Income & Expenditure)
    can reuse — they're mostly a different groupby/pivot over the same
    per-transaction DataFrame.
    """
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    filters = _general_ledger_filter_defaults(request)
    start_date = filters["start_date"]
    end_date = filters["end_date"]
    department_id = filters["department"]
    project_id = filters["project"]
    report_currency = filters["currency"]
    selected_account_ids = [v for v in request.GET.getlist("accounts") if v]

    base_currency = get_base_currency()
    # Fetched once and reused for every conversion below — convert_amount()
    # would otherwise re-fetch/re-resolve exchange rates on every single
    # call, once per transaction, which adds up fast on a report spanning
    # many accounts.
    rates = get_latest_usd_rates()
    leaf_accounts = FinancialCategory.objects.filter(is_group=False).select_related("parent").order_by("category_type", "code")

    accounts = leaf_accounts.filter(pk__in=selected_account_ids) if selected_account_ids else leaf_accounts

    txn_filter = Q(date__gte=start_date, date__lte=end_date)
    if department_id:
        txn_filter &= Q(department_id=department_id)
    if project_id:
        txn_filter &= Q(project_id=project_id)

    report_rows = []
    grand_opening = Decimal("0.00")
    grand_movement = Decimal("0.00")

    for account in accounts:
        # Aggregate aliases deliberately avoid the literal field names
        # "amount"/"original_amount" — using one as its own aggregate's
        # alias makes Django resolve a later F("amount") in the same
        # .aggregate() call against that annotation instead of the raw
        # column ("Cannot compute Sum('amount'): 'amount' is an aggregate").
        prior = FinancialTransaction.objects.filter(category=account, date__lt=start_date).aggregate(
            prior_amount=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_ZERO),
            prior_original=Coalesce(Sum(Coalesce(F("original_amount"), F("amount"))), Value(0), output_field=DECIMAL_ZERO),
        )
        opening_balance = convert_amount(
            account.opening_balance, account.currency, report_currency, rates=rates
        ) + convert_amount(prior["prior_amount"], base_currency, report_currency, rates=rates)
        # "Original currency" balance stays in the account's own currency
        # throughout (no conversion) — meaningful because a ledger account
        # is expected to only ever be posted to in its own currency, the
        # same assumption a real bank-account ledger makes.
        opening_balance_original = account.opening_balance + prior["prior_original"]

        transactions = list(
            FinancialTransaction.objects.filter(txn_filter, category=account)
            .order_by("date", "pk")
            .values(
                "date", "reference", "description", "amount",
                "currency", "original_amount", "department__name", "project__name",
            )
        )

        is_debit = account.balance_side == "Dr"
        rows = []
        period_debit = Decimal("0.00")
        period_credit = Decimal("0.00")
        period_debit_original = Decimal("0.00")
        period_credit_original = Decimal("0.00")
        running_balance = opening_balance
        running_balance_original = opening_balance_original

        if transactions:
            df = pd.DataFrame(transactions)
            df = df.rename(columns={"department__name": "department", "project__name": "project"})
            # original_amount is only null for transactions recorded before
            # the multi-currency migration backfilled it — fall back to the
            # base-currency amount (paired with its own currency column
            # left as-is) so every row still has something to show, the
            # same fallback the Financial Ledger page already uses.
            df["original_amount"] = df["original_amount"].fillna(df["amount"])
            df["department"] = df["department"].fillna("—")
            df["project"] = df["project"].fillna("—")
            df["display_amount"] = df["amount"].apply(
                lambda amount: convert_amount(amount, base_currency, report_currency, rates=rates)
            )
            df["balance"] = opening_balance + df["display_amount"].cumsum()
            df["balance_original"] = opening_balance_original + df["original_amount"].cumsum()

            # A row's amount can be negative (a journal-entry line that
            # decreases this account) — which column it belongs in depends
            # on its own sign, not just the account's fixed natural side.
            # Every pre-journal-entry transaction is non-negative, so this
            # is a no-op for historical data: it always lands in the
            # account's natural column exactly as before.
            def split_debit_credit(amount):
                is_debit_row = (amount >= 0) == is_debit
                return (abs(amount), None) if is_debit_row else (None, abs(amount))

            base_split = df["display_amount"].apply(split_debit_credit)
            df["debit"] = base_split.apply(lambda pair: pair[0])
            df["credit"] = base_split.apply(lambda pair: pair[1])

            original_split = df["original_amount"].apply(split_debit_credit)
            df["debit_original"] = original_split.apply(lambda pair: pair[0])
            df["credit_original"] = original_split.apply(lambda pair: pair[1])

            period_debit = _decimal_sum(df["debit"])
            period_credit = _decimal_sum(df["credit"])
            period_debit_original = _decimal_sum(df["debit_original"])
            period_credit_original = _decimal_sum(df["credit_original"])
            running_balance = df["balance"].iloc[-1]
            running_balance_original = df["balance_original"].iloc[-1]
            rows = df.to_dict("records")

        report_rows.append({
            "account": account,
            "opening_balance": opening_balance,
            "opening_balance_original": opening_balance_original,
            "rows": rows,
            "closing_balance": running_balance,
            "closing_balance_original": running_balance_original,
            "period_debit": period_debit,
            "period_credit": period_credit,
            "period_debit_original": period_debit_original,
            "period_credit_original": period_credit_original,
        })
        grand_opening += opening_balance
        grand_movement += (running_balance - opening_balance)

    selected_fields = request.GET.getlist("fields") or GL_DEFAULT_FIELDS

    context = {
        "report_rows": report_rows,
        "grand_opening": grand_opening,
        "grand_closing": grand_opening + grand_movement,
        "filters": filters,
        "base_currency": base_currency,
        "selected_fields": selected_fields,
        "optional_fields": GL_OPTIONAL_FIELDS,
    }
    return render(request, "finance/general_ledger_report_view.html", context)


def _build_period_activity_tree(category_types, txn_filter, report_currency, rates, base_currency):
    """
    Roll up transaction activity WITHIN A PERIOD (not an all-time opening/
    closing balance) for every account under the given root category
    type(s), converted into report_currency. Used by the Income Statement,
    and written generically enough that Budget vs Actual (or any future
    period-based report) can reuse it instead of writing its own rollup.
    """
    categories = list(FinancialCategory.objects.filter(category_type__in=category_types).select_related("parent"))
    by_id = {c.pk: c for c in categories}
    for c in categories:
        c.tree_children = []
        if not c.is_group:
            total = FinancialTransaction.objects.filter(txn_filter, category=c).aggregate(
                total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_ZERO)
            )["total"]
            c.period_amount = convert_amount(total, base_currency, report_currency, rates=rates)

    roots = []
    for c in categories:
        parent = by_id.get(c.parent_id) if c.parent_id else None
        if parent is not None:
            parent.tree_children.append(c)
        else:
            roots.append(c)

    def rollup(node):
        if node.is_group:
            node.period_amount = sum((rollup(child) for child in node.tree_children), Decimal("0.00"))
        return node.period_amount

    for root in roots:
        rollup(root)

    return roots


@login_required(login_url="login")
def income_statement_report(request):
    """Filter form for the Income Statement — same period/dept/project/
    currency shape as the General Ledger's filter page, opening the actual
    report in its own full page on submit."""
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    context = {
        "departments": Department.objects.all(),
        "projects": Project.objects.all(),
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "filters": _general_ledger_filter_defaults(request),
    }
    return render(request, "finance/income_statement_report.html", context)


@login_required(login_url="login")
def income_statement_report_view(request):
    """
    Income and Expense accounts for a period, grouped the same way as the
    Chart of Accounts, with the net result (Income - Expenses). Unlike the
    General Ledger, this only needs period activity per account (a flow),
    not an opening/closing balance (a stock) — Income/Expense accounts are
    temporary accounts that measure what happened during the period, not a
    running position.
    """
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    filters = _general_ledger_filter_defaults(request)
    report_currency = filters["currency"]
    base_currency = get_base_currency()
    rates = get_latest_usd_rates()

    txn_filter = Q(date__gte=filters["start_date"], date__lte=filters["end_date"])
    if filters["department"]:
        txn_filter &= Q(department_id=filters["department"])
    if filters["project"]:
        txn_filter &= Q(project_id=filters["project"])

    income_roots = _build_period_activity_tree(
        [FinancialCategory.CategoryType.INCOME], txn_filter, report_currency, rates, base_currency
    )
    expense_roots = _build_period_activity_tree(
        [FinancialCategory.CategoryType.EXPENSE], txn_filter, report_currency, rates, base_currency
    )

    total_income = sum((r.period_amount for r in income_roots), Decimal("0.00"))
    total_expense = sum((r.period_amount for r in expense_roots), Decimal("0.00"))

    context = {
        "income_roots": income_roots,
        "expense_roots": expense_roots,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_result": total_income - total_expense,
        "filters": filters,
    }
    return render(request, "finance/income_statement_report_view.html", context)


@login_required(login_url="login")
def budget_vs_actual_report(request):
    """Filter form for Budget vs Actual — pick a fiscal year (matching
    ProjectBudget entries) and the period to measure actual spend against."""
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    fiscal_years = list(
        ProjectBudget.objects.order_by("-fiscal_year").values_list("fiscal_year", flat=True).distinct()
    )

    context = {
        "fiscal_years": fiscal_years,
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "filters": _general_ledger_filter_defaults(request),
        "selected_fiscal_year": request.GET.get("fiscal_year") or (fiscal_years[0] if fiscal_years else ""),
    }
    return render(request, "finance/budget_vs_actual_report.html", context)


@login_required(login_url="login")
def budget_vs_actual_report_view(request):
    """
    Each project's approved budget for a fiscal year against what was
    actually spent (summed FinancialTransaction activity for that project
    over the chosen date range), with variance and percentage utilized.

    ProjectBudget doesn't store its own start/end dates (just a fiscal_year
    label and an optional quarter), so "actual" spend is measured over the
    date range chosen in the filter — the org's own understanding of that
    fiscal year's calendar span — rather than one this view invents.
    Budget rows are summed per project regardless of period (Full Year vs.
    quarterly): correct as long as a project's budget was entered once
    (either as one Full Year row or as non-overlapping quarters), and
    reports a total including all their prior quarters, which is a
    reasonable summary as long as budgets are entered consistently.
    """
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    filters = _general_ledger_filter_defaults(request)
    report_currency = filters["currency"]
    base_currency = get_base_currency()
    rates = get_latest_usd_rates()
    fiscal_year = request.GET.get("fiscal_year") or ""

    budgets = ProjectBudget.objects.filter(fiscal_year=fiscal_year).values("project_id").annotate(
        total_budget=Coalesce(Sum("budget_amount"), Value(0), output_field=DECIMAL_ZERO)
    )
    budget_by_project = {row["project_id"]: row["total_budget"] for row in budgets}

    rows = []
    grand_budget = Decimal("0.00")
    grand_actual = Decimal("0.00")

    for project in Project.objects.filter(pk__in=budget_by_project.keys()):
        budget_amount = convert_amount(budget_by_project[project.pk], base_currency, report_currency, rates=rates)
        actual_amount_base = FinancialTransaction.objects.filter(
            project=project, date__gte=filters["start_date"], date__lte=filters["end_date"],
        ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_ZERO))["total"]
        actual_amount = convert_amount(actual_amount_base, base_currency, report_currency, rates=rates)
        variance = budget_amount - actual_amount
        percent_used = (actual_amount / budget_amount * 100) if budget_amount else None

        rows.append({
            "project": project,
            "budget": budget_amount,
            "actual": actual_amount,
            "variance": variance,
            "percent_used": percent_used,
        })
        grand_budget += budget_amount
        grand_actual += actual_amount

    rows.sort(key=lambda r: r["project"].name)

    context = {
        "rows": rows,
        "grand_budget": grand_budget,
        "grand_actual": grand_actual,
        "grand_variance": grand_budget - grand_actual,
        "fiscal_year": fiscal_year,
        "filters": filters,
    }
    return render(request, "finance/budget_vs_actual_report_view.html", context)


@login_required(login_url="login")
def balance_sheet_report(request):
    """Filter form for the Balance Sheet — a point-in-time snapshot, so it
    only needs an "as of" date and a currency, not a date range."""
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    context = {
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "as_of_date": request.GET.get("as_of_date") or date.today().isoformat(),
        "currency": normalize_currency(request.GET.get("currency") or get_base_currency()),
        "detail_level": request.GET.get("detail_level") or "full",
    }
    return render(request, "finance/balance_sheet_report.html", context)


def _flatten_to_leaves(node):
    """Collect every leaf (postable) descendant of a tree node, discarding
    the group/folder structure — used for the Balance Sheet's "accounts
    only" display mode."""
    if node.is_group:
        leaves = []
        for child in node.tree_children:
            leaves.extend(_flatten_to_leaves(child))
        return leaves
    return [node]


@login_required(login_url="login")
def balance_sheet_report_view(request):
    """
    Assets, Liabilities, and Equity balances as of a chosen date, grouped
    the same way as the Chart of Accounts.

    This app doesn't (yet) record true double-entry postings — an expense
    reduces an expense account's activity but isn't linked to which
    specific cash/bank account paid for it — so nothing here structurally
    guarantees Assets = Liabilities + Equity the way a real double-entry
    balance sheet would. To stay honest about that instead of silently
    presenting a number that happens to look balanced, this also computes
    Retained Earnings (cumulative Income minus Expenses up to the as-of
    date, the standard way undistributed net income closes into Equity)
    as its own labeled line, and shows the residual difference between
    Assets and (Liabilities + Equity + Retained Earnings) explicitly
    rather than hiding it. Once double-entry postings exist, that
    difference should read as zero; until then, it's a real, visible
    measure of how much financial activity isn't yet tied to a specific
    balance-sheet account.
    """
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can run financial reports.")
        return redirect(reverse("finance:dashboard"))

    as_of_date = request.GET.get("as_of_date") or date.today().isoformat()
    report_currency = normalize_currency(request.GET.get("currency") or get_base_currency())
    base_currency = get_base_currency()
    rates = get_latest_usd_rates()
    # "full": every group/sub-group folder shown, exactly like the Chart of
    # Accounts. "flat": no folders at all except the Assets/Liabilities/
    # Equity section headers themselves — every leaf account listed
    # directly under its section, sorted by code.
    detail_level = request.GET.get("detail_level") or "full"

    asset_roots, _ = _build_account_tree(
        as_of_date=as_of_date, report_currency=report_currency,
        category_types=[FinancialCategory.CategoryType.ASSET], rates=rates,
    )
    liability_roots, _ = _build_account_tree(
        as_of_date=as_of_date, report_currency=report_currency,
        category_types=[FinancialCategory.CategoryType.LIABILITY], rates=rates,
    )
    equity_roots, _ = _build_account_tree(
        as_of_date=as_of_date, report_currency=report_currency,
        category_types=[FinancialCategory.CategoryType.EQUITY], rates=rates,
    )

    asset_leaves = liability_leaves = equity_leaves = None
    if detail_level == "flat":
        asset_leaves = sorted(
            (leaf for root in asset_roots for leaf in _flatten_to_leaves(root)), key=lambda n: n.code
        )
        liability_leaves = sorted(
            (leaf for root in liability_roots for leaf in _flatten_to_leaves(root)), key=lambda n: n.code
        )
        equity_leaves = sorted(
            (leaf for root in equity_roots for leaf in _flatten_to_leaves(root)), key=lambda n: n.code
        )

    total_assets = sum((r.rollup_base for r in asset_roots), Decimal("0.00"))
    total_liabilities = sum((r.rollup_base for r in liability_roots), Decimal("0.00"))
    total_equity = sum((r.rollup_base for r in equity_roots), Decimal("0.00"))

    income_to_date = FinancialCategory.objects.filter(
        category_type=FinancialCategory.CategoryType.INCOME, is_group=False
    ).aggregate(
        total=Coalesce(Sum("transactions__amount", filter=Q(transactions__date__lte=as_of_date)), Value(0), output_field=DECIMAL_ZERO)
    )["total"]
    expense_to_date = FinancialCategory.objects.filter(
        category_type=FinancialCategory.CategoryType.EXPENSE, is_group=False
    ).aggregate(
        total=Coalesce(Sum("transactions__amount", filter=Q(transactions__date__lte=as_of_date)), Value(0), output_field=DECIMAL_ZERO)
    )["total"]
    retained_earnings = convert_amount(income_to_date - expense_to_date, base_currency, report_currency, rates=rates)

    total_liabilities_and_equity = total_liabilities + total_equity + retained_earnings
    difference = total_assets - total_liabilities_and_equity

    context = {
        "detail_level": detail_level,
        "asset_roots": asset_roots,
        "liability_roots": liability_roots,
        "equity_roots": equity_roots,
        "asset_leaves": asset_leaves,
        "liability_leaves": liability_leaves,
        "equity_leaves": equity_leaves,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "retained_earnings": retained_earnings,
        "total_liabilities_and_equity": total_liabilities_and_equity,
        "difference": difference,
        "as_of_date": as_of_date,
        "currency": report_currency,
    }
    return render(request, "finance/balance_sheet_report_view.html", context)


@login_required(login_url="login")
def journal_entry_list(request):
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can view journal entries.")
        return redirect(reverse("finance:dashboard"))

    entries = JournalEntry.objects.select_related("created_by").prefetch_related(
        "lines__category"
    ).order_by("-date", "-created_at")[:200]

    return render(request, "finance/journal_entry_list.html", {
        "entries": entries,
        "can_manage": _can_manage_chart_of_accounts(request.user),
    })


@login_required(login_url="login")
def journal_entry_detail(request, pk):
    is_finance = has_group(request.user, 'Finance')
    if not is_finance:
        messages.error(request, "Only Finance and Operations staff can view journal entries.")
        return redirect(reverse("finance:dashboard"))

    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related("lines__category", "lines__department", "lines__project"), pk=pk
    )
    return render(request, "finance/journal_entry_detail.html", {"entry": entry})


@login_required(login_url="login")
def journal_entry_create(request):
    """
    A proper double-entry posting: pick an account per line, put an amount
    in either Debit or Credit, and keep adding lines until Total Debit
    equals Total Credit. Gated behind the same "can manage the chart of
    accounts" permission as structural changes there, rather than the
    broader "Finance or Operations staff" check every other Finance view
    uses — a manual journal entry can move money in or out of any account
    directly, with no requisition/approval trail behind it, so it warrants
    the narrower permission.
    """
    if not _can_manage_chart_of_accounts(request.user):
        messages.error(request, "Only Finance staff can post journal entries.")
        return redirect(reverse("finance:journal_entry_list"))

    leaf_accounts = FinancialCategory.objects.filter(is_group=False).order_by("category_type", "code")

    if request.method == "POST":
        entry_date = request.POST.get("date") or ""
        header_description = (request.POST.get("description") or "").strip()

        category_ids = request.POST.getlist("line_category")
        debits = request.POST.getlist("line_debit")
        credits = request.POST.getlist("line_credit")
        line_descriptions = request.POST.getlist("line_description")
        line_departments = request.POST.getlist("line_department")
        line_projects = request.POST.getlist("line_project")

        errors = []
        lines_data = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for i, category_id in enumerate(category_ids):
            debit_raw = debits[i] if i < len(debits) else ""
            credit_raw = credits[i] if i < len(credits) else ""
            if not category_id and not debit_raw.strip() and not credit_raw.strip():
                continue  # a blank trailing row from "Add row" — skip silently

            category = FinancialCategory.objects.filter(pk=category_id, is_group=False).first()
            debit = _parse_opening_balance(debit_raw)
            credit = _parse_opening_balance(credit_raw)

            if category is None:
                errors.append(f"Row {i + 1}: choose an account.")
                continue
            if debit is None or credit is None:
                errors.append(f"Row {i + 1}: enter a valid Debit or Credit amount.")
                continue
            if debit and credit:
                errors.append(f"Row {i + 1} ({category.name}): enter either a Debit or a Credit, not both.")
                continue
            if not debit and not credit:
                errors.append(f"Row {i + 1} ({category.name}): enter a Debit or a Credit amount.")
                continue

            lines_data.append({
                "category": category,
                "debit": debit,
                "credit": credit,
                "description": (line_descriptions[i] if i < len(line_descriptions) else "").strip(),
                "department_id": (line_departments[i] if i < len(line_departments) else "") or None,
                "project_id": (line_projects[i] if i < len(line_projects) else "") or None,
            })
            total_debit += debit
            total_credit += credit

        if not entry_date:
            errors.append("Posting date is required.")
        if len(lines_data) < 2:
            errors.append("A journal entry needs at least two lines.")
        elif total_debit != total_credit:
            errors.append(
                f"This entry doesn't balance — Total Debit ({total_debit:,.2f}) must equal "
                f"Total Credit ({total_credit:,.2f})."
            )

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            with transaction.atomic():
                entry = JournalEntry.objects.create(
                    date=entry_date, description=header_description, created_by=request.user,
                )
                for line in lines_data:
                    journal_line = JournalEntryLine.objects.create(journal_entry=entry, **line)
                    journal_line.post()
            messages.success(request, f"Journal Entry {entry.reference} posted.")
            return redirect(reverse("finance:journal_entry_detail", args=[entry.pk]))

    context = {
        "leaf_accounts": leaf_accounts,
        "departments": Department.objects.all(),
        "projects": Project.objects.all(),
        "today": date.today().isoformat(),
    }
    return render(request, "finance/journal_entry_create.html", context)
