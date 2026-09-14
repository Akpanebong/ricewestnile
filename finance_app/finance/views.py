from decimal import Decimal, InvalidOperation
from openpyxl import Workbook
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, ExpressionWrapper, F, DecimalField, Value, Q, Count
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from account.models import Department
from core.project_models import Project, ProjectBudget
from finance_app.finance.models import (
    AccountingForm, AdminExpenseNote, CashRequisition, CashRequisitionItem,
    ApprovalLog, AccountingItem, FinancialTransaction, FinancialCategory,
)

from .utils.workflow import advance_workflow, user_can_approve
from .utils.pdf import render_to_pdf
from django.db.models.functions import Coalesce
from account.templatetags.custom_tags import has_group
from procurement.procureapp.models import Requisition, PurchaseOrder
from assets.assetapp.models import Asset, AssetMaintenance
from core.services import normalize_currency, get_base_currency, CURRENCY_LABELS, SUPPORTED_CURRENCIES


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
    }

    return render(request, "finance/dashboard.html", context)


@login_required(login_url="login")
def create_cash_requisition(request):
    if request.method == "POST":
        with transaction.atomic():
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

            # The currency this requisition is actually being raised in —
            # captured once for the whole form, rather than assumed from
            # the submitting user's own display-currency preference.
            currency = normalize_currency(request.POST.get("currency"))
            # rate_used only depends on `currency` (not the amount passed in),
            # so a placeholder amount is fine here — this just captures the
            # base-currency rate snapshot for the requisition as a whole.
            _, rate_used = FinancialTransaction.convert_to_base_currency(Decimal("0"), currency)

            obj = CashRequisition.objects.create(
                procurement_requisition_id=procurement_requisition_id,
                purchase_order=purchase_order,
                donor_code=request.POST.get("donor_code"),
                purpose=request.POST.get("purpose"),
                created_by=request.user,
                status="draft",
                date=request.POST.get("date"),
                to="Executive Director",
                attachment=request.FILES.get("attachment"),
                currency=currency,
                exchange_rate_used=rate_used,
            )

            index = 0
            while f"items[{index}][activity_code]" in request.POST:
                raw_unit_cost = (request.POST.get(f"items[{index}][unit_cost]") or "0").replace(",", "").strip()
                try:
                    original_unit_cost = Decimal(raw_unit_cost)
                except InvalidOperation:
                    original_unit_cost = Decimal("0")
                unit_cost, _ = FinancialTransaction.convert_to_base_currency(original_unit_cost, currency)
                CashRequisitionItem.objects.create(
                    requisition=obj,
                    activity_code=request.POST.get(f"items[{index}][activity_code]"),
                    program_code=request.POST.get(f"items[{index}][program_code]"),
                    particulars=request.POST.get(f"items[{index}][particulars]"),
                    quantity=request.POST.get(f"items[{index}][quantity]") or 0,
                    unit_cost=unit_cost,
                    original_unit_cost=original_unit_cost,
                )
                index += 1

        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    return render(request, "finance/create_cash_requisition.html", {
        "procurement_requisitions": Requisition.objects.filter(status="Approved").order_by("-date"),
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
    })


@login_required(login_url="login")
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
        },
    )


@login_required(login_url="login")
def requisition_list(request):
    qs = CashRequisition.objects.all().order_by("-created_at")
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "finance/req_list.html", {"objects": page_obj, "page_obj": page_obj})


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
def submit_requisition(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk,  slug=slug, created_by=request.user)

    if obj.status != "draft":
        messages.error(request, "Already submitted")
        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    obj.status = "submitted"
    obj.save()

    return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))


@login_required(login_url="login")
def approve_requisition(request, pk, slug):
    obj = get_object_or_404(CashRequisition, pk=pk,  slug=slug)

    if user_can_approve(request.user, obj):
        advance_workflow(obj, request.user)

    else:
        messages.warning(request, "Unauthorized action")
        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    obj.save()

    if obj.status == "approved":
        FinancialTransaction.record_cash_advance(obj, request.user)

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
        # The currency this retirement is actually being accounted in —
        # captured once for the whole form, rather than assumed from the
        # submitting user's own display-currency preference.
        currency = normalize_currency(request.POST.get("currency"))
        # rate_used only depends on `currency`, so a placeholder amount is
        # fine here — this just snapshots the base-currency rate for the form.
        _, rate_used = FinancialTransaction.convert_to_base_currency(Decimal("0"), currency)

        if not obj:
            obj = AccountingForm.objects.create(
                requisition=requisition,
                created_by=request.user,
                donor_code=requisition.donor_code,
                description=description,
                date_of_return=date_of_return,
                status="submitted",
                currency=currency,
                exchange_rate_used=rate_used,
            )
        else:
            obj.description = description
            obj.date_of_return = date_of_return
            obj.currency = currency
            obj.exchange_rate_used = rate_used
            obj.save()
            obj.items.all().delete()

        # Extract arrays
        activities = request.POST.getlist("activity_code[]")
        programs = request.POST.getlist("program_code[]")
        details = request.POST.getlist("details[]")
        received = request.POST.getlist("received[]")
        spent = request.POST.getlist("spent[]")

        def _to_decimal(raw):
            try:
                return Decimal(str(raw or "0").replace(",", "").strip())
            except InvalidOperation:
                return Decimal("0")

        items = []
        for a, p, d, r, s in zip(activities, programs, details, received, spent):
            original_amount_received = _to_decimal(r)
            original_amount_spent = _to_decimal(s)
            amount_received, _ = FinancialTransaction.convert_to_base_currency(original_amount_received, currency)
            amount_spent, _ = FinancialTransaction.convert_to_base_currency(original_amount_spent, currency)
            items.append(AccountingItem(
                form=obj,
                activity_code=a,
                program_code=p,
                details=d,
                amount_received=amount_received,
                amount_spent=amount_spent,
                original_amount_received=original_amount_received,
                original_amount_spent=original_amount_spent,
            ))

        AccountingItem.objects.bulk_create(items)

        return redirect(reverse("finance:accounting_detail", kwargs={
            "pk": obj.pk,
            "slug": obj.slug
        }))

    return render(request, "finance/account_form.html", {
        "form_obj": obj,
        "requisition": requisition or getattr(obj, "requisition", None),
        "items": obj.items.all() if obj else [],
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
    })


@login_required(login_url="login")
def approve_account_form(request, pk, slug):
    obj = get_object_or_404(AccountingForm, pk=pk,  slug=slug)

    if user_can_approve(request.user, obj):
        advance_workflow(obj, request.user)

    else:
        messages.warning(request, "Unauthorized action")
        return redirect(reverse("finance:accounting_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    if obj.status == "approved":
        FinancialTransaction.record_accounting_expense(obj, request.user)

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
def create_admin_expense(request, slug, pk):
    cash_req = get_object_or_404(CashRequisition, slug=slug, pk=pk)
    if request.method == "POST":
        currency = normalize_currency(request.POST.get("currency"))
        raw_budget = (request.POST.get("proposed_budget") or "0").replace(",", "").strip()
        try:
            original_proposed_budget = Decimal(raw_budget)
        except InvalidOperation:
            original_proposed_budget = Decimal("0")
        proposed_budget, rate_used = FinancialTransaction.convert_to_base_currency(original_proposed_budget, currency)

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
            proposed_budget=proposed_budget,
            currency=currency,
            original_proposed_budget=original_proposed_budget,
            exchange_rate_used=rate_used,
            service_providers=request.POST.get("service_providers"),
            created_by=request.user,
            status="draft",
        )
        return redirect(reverse("finance:admin_expense_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))

    return render(request, "finance/admin_expense/create.html",
                  {
                      "cash_req": cash_req,
                      "departments": Department.objects.all(),
                      "projects": Project.objects.all(),
                      "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
                  }
                  )


@login_required(login_url="login")
def admin_expense_detail(request, pk, slug):
    obj = get_object_or_404(AdminExpenseNote, pk=pk,  slug=slug)

    return render(request, "finance/admin_expense/detail.html", {"obj": obj})


@login_required(login_url="login")
def submit_admin_expense(request, pk, slug):
    obj = get_object_or_404(AdminExpenseNote, pk=pk,  slug=slug)

    if obj.created_by != request.user:
        return HttpResponseForbidden()

    obj.status = "submitted"
    obj.save()

    return redirect(reverse("finance:admin_expense_detail", kwargs={"pk": obj.pk, "slug": obj.slug}))


@login_required(login_url="login")
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
                FinancialTransaction.record_admin_expense(obj, user)
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
    if not _is_finance_staff(request.user):
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
        "categories": FinancialCategory.objects.all(),
        "transaction_types": FinancialTransaction.TransactionType.choices,
        "filters": request.GET,
    }
    return render(request, "finance/ledger.html", context)


@login_required(login_url="login")
def financial_ledger_export(request):
    if not _is_finance_staff(request.user):
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


@login_required(login_url="login")
def record_transaction(request):
    if not _is_finance_staff(request.user):
        messages.error(request, "Only Finance and Operations staff can record financial transactions.")
        return redirect(reverse("finance:dashboard"))

    if request.method == "POST":
        # The transaction's currency is a fact about the money itself, not
        # about the person recording it — deliberately NOT user_amount_to_ugx()
        # (which converts using the *viewer's* display-currency preference).
        currency = normalize_currency(request.POST.get("currency"))
        raw_amount = (request.POST.get("amount") or "0").replace(",", "").strip()
        try:
            original_amount = Decimal(raw_amount)
        except InvalidOperation:
            messages.error(request, "Enter a valid amount.")
            return redirect(reverse("finance:record_transaction"))

        category = get_object_or_404(FinancialCategory, pk=request.POST.get("category"))

        txn = FinancialTransaction.record_manual_transaction(
            transaction_type=request.POST.get("transaction_type"),
            category=category,
            currency=currency,
            original_amount=original_amount,
            date=request.POST.get("date"),
            description=request.POST.get("description", ""),
            donor_code=request.POST.get("donor_code", ""),
            project_id=request.POST.get("project") or None,
            department_id=request.POST.get("department") or None,
            purchase_order_id=request.POST.get("purchase_order") or None,
            asset_id=request.POST.get("asset") or None,
            asset_maintenance_id=request.POST.get("asset_maintenance") or None,
            created_by=request.user,
        )
        messages.success(
            request,
            f"Transaction {txn.reference} recorded — "
            f"{currency} {original_amount:,.2f} ({get_base_currency()} {txn.amount:,.2f} at rate {txn.exchange_rate_used}).",
        )
        return redirect(reverse("finance:ledger"))

    context = {
        "categories": FinancialCategory.objects.all(),
        "projects": Project.objects.all(),
        "departments": Department.objects.all(),
        "purchase_orders": PurchaseOrder.objects.filter(sent=True).order_by("-id")[:200],
        "assets": Asset.objects.all()[:200],
        "asset_maintenances": AssetMaintenance.objects.select_related("asset").order_by("-id")[:200],
        "transaction_types": FinancialTransaction.TransactionType.choices,
        "currency_options": [{"code": c, "label": CURRENCY_LABELS[c]} for c in SUPPORTED_CURRENCIES],
        "base_currency": get_base_currency(),
    }
    return render(request, "finance/record_transaction.html", context)


def _is_finance_staff(user):
    """
    Org-wide financial data (the ledger, the chart of accounts, ad-hoc
    transaction recording) is restricted to the same groups the Finance
    dashboard already treats as managers — everyone else only ever sees
    their own requisitions there. Views below previously only checked
    @login_required, which let any authenticated account view every
    donor's funding and record arbitrary transactions.
    """
    return user.is_superuser or has_group(user, "Finance") or has_group(user, "Operations")


def _can_manage_chart_of_accounts(user):
    return user.is_superuser or has_group(user, "Finance")


def _parse_opening_balance(raw):
    raw = (raw or "0").replace(",", "").strip()
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


@login_required(login_url="login")
def chart_of_accounts(request):
    if not _is_finance_staff(request.user):
        messages.error(request, "Only Finance and Operations staff can view the chart of accounts.")
        return redirect(reverse("finance:dashboard"))

    can_manage = _can_manage_chart_of_accounts(request.user)

    if request.method == "POST":
        if not can_manage:
            messages.error(request, "You do not have permission to manage the chart of accounts.")
            return redirect(reverse("finance:chart_of_accounts"))

        action = request.POST.get("action", "add")

        if action == "edit":
            category = get_object_or_404(FinancialCategory, pk=request.POST.get("category_id"))
            name = (request.POST.get("name") or "").strip()
            alt_code = (request.POST.get("alt_code") or "").strip().upper()
            opening_balance = _parse_opening_balance(request.POST.get("opening_balance"))

            if not name:
                messages.error(request, "Name is required.")
            elif opening_balance is None:
                messages.error(request, "Enter a valid opening balance.")
            else:
                category.name = name
                category.alt_code = alt_code
                category.opening_balance = opening_balance
                category.save(update_fields=["name", "alt_code", "opening_balance"])
                messages.success(request, f"Account '{category.code}' updated.")
            return redirect(reverse("finance:chart_of_accounts"))

        code = (request.POST.get("code") or "").strip().upper()
        alt_code = (request.POST.get("alt_code") or "").strip().upper()
        name = (request.POST.get("name") or "").strip()
        category_type = request.POST.get("category_type")
        opening_balance = _parse_opening_balance(request.POST.get("opening_balance"))

        if not (code and name and category_type):
            messages.error(request, "Code, name, and type are all required.")
        elif opening_balance is None:
            messages.error(request, "Enter a valid opening balance.")
        elif FinancialCategory.objects.filter(code=code).exists():
            messages.error(request, f"A category with code '{code}' already exists.")
        else:
            FinancialCategory.objects.create(
                code=code, alt_code=alt_code, name=name,
                category_type=category_type, opening_balance=opening_balance,
            )
            messages.success(request, f"Account '{name}' added to the chart of accounts.")
        return redirect(reverse("finance:chart_of_accounts"))

    categories = FinancialCategory.objects.annotate(
        transaction_count=Coalesce(Count("transactions", distinct=True), Value(0)),
        total_amount=Coalesce(Sum("transactions__amount"), Value(0), output_field=DECIMAL_ZERO),
    ).order_by("category_type", "code")

    by_type = {}
    for category in categories:
        category.closing_balance = category.opening_balance + category.total_amount
        by_type.setdefault(category.category_type, []).append(category)

    # Pre-grouped as (type_value, type_label, [categories], group_total,
    # balance_side) tuples so the template can do a plain nested loop
    # instead of a variable-keyed dict lookup, which Django's template
    # dot-notation can't express directly.
    grouped_categories = [
        (
            type_value, type_label, by_type.get(type_value, []),
            sum((c.closing_balance for c in by_type.get(type_value, [])), Decimal("0.00")),
            FinancialCategory.NATURAL_BALANCE_SIDE[type_value],
        )
        for type_value, type_label in FinancialCategory.CategoryType.choices
    ]

    context = {
        "grouped_categories": grouped_categories,
        "can_manage": can_manage,
        "total_accounts": categories.count(),
        "category_types": FinancialCategory.CategoryType.choices,
        "base_currency": get_base_currency(),
    }
    return render(request, "finance/chart_of_accounts.html", context)
