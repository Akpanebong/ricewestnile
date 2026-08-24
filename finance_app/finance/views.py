from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, ExpressionWrapper, F, DecimalField, Value
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from account.models import Department
from core.project_models import Project
from .models import CashRequisition, CashRequisitionItem, AccountingForm, ApprovalLog,\
    AccountingItem, AdminExpenseNote
from .utils.workflow import advance_workflow, user_can_approve
from .utils.pdf import render_to_pdf
from django.db.models.functions import Coalesce
from account.templatetags.custom_tags import has_group
from procurement.procureapp.models import Requisition, PurchaseOrder
from core.services import user_amount_to_ugx


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
            )

            index = 0
            while f"items[{index}][activity_code]" in request.POST:
                CashRequisitionItem.objects.create(
                    requisition=obj,
                    activity_code=request.POST.get(f"items[{index}][activity_code]"),
                    program_code=request.POST.get(f"items[{index}][program_code]"),
                    particulars=request.POST.get(f"items[{index}][particulars]"),
                    quantity=request.POST.get(f"items[{index}][quantity]") or 0,
                    unit_cost=user_amount_to_ugx(request.POST.get(f"items[{index}][unit_cost]") or 0, request)
                )
                index += 1

        return redirect(reverse("finance:requisition_detail", kwargs={'pk': obj.pk, 'slug': obj.slug}))

    return render(request, "finance/create_cash_requisition.html", {
        "procurement_requisitions": Requisition.objects.filter(status="Approved").order_by("-date")
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
