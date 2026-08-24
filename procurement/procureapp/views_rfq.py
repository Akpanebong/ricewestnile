import hashlib
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
import re
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.mail import get_connection, EmailMessage
from django.conf import settings
from xhtml2pdf import pisa
from procurement.procureapp.forms import RFQForm
from procurement.procureapp.models import Requisition, RFQ, RFQSendLog, ProcurementPlan, PurchaseOrder
from procurement.procureapp.utils import render_pdf, head_of_procurement_required

connection = get_connection()

@login_required(login_url='login')
# @head_of_procurement_required
def create_rfq(request, pk):
    requisition = get_object_or_404(Requisition, pk=pk, status='Approved')
    plan = requisition.procurement

    if not plan or plan.status != 'Approved':
        messages.error(request, "Related procurement plan is not approved.")
        return redirect('rfq_list')

    reference_no = (
        f"RICE-WN-{plan.project}-RFQ-{timezone.now().year}-"
        f"{requisition.id:04d}-{requisition.number}"
    )

    rfq = RFQ.objects.filter(reference_no=reference_no).first()

    if rfq:
        messages.warning(request, "RFQ already exists.")
        return redirect(reverse_lazy("rfq_detail", kwargs={'slug': rfq.slug, 'reference_no': reference_no}))

    if request.method == 'POST':
        form = RFQForm(request.POST) #, instance=rfq

        if form.is_valid():
            rfq = form.save(commit=False)
            rfq.req = requisition
            rfq.plan = plan
            rfq.created_by = request.user
            rfq.reference_no = reference_no
            rfq.deadline = form.cleaned_data['deadline']
            rfq.save()

            form.save_m2m()

            # Generate PDF
            context = {
                'rfq': rfq,
                'suppliers': rfq.supplier.all(),
                'plan': plan,
                'requisition': requisition,
                'items': requisition.items.all(),
                'organization_name': 'RICE West Nile',
                'total_amount': requisition.total,
            }
            html_content = render_to_string('procurement/rfq_pdf.html', context)
            pdf_file = BytesIO()
            pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)
            if pisa_status.err:
                messages.error(request, "Error generating RFQ PDF.")
                return redirect('rfq_list')

            # Sanitize filename to avoid invalid path characters
            safe_ref = re.sub(r'[^a-zA-Z0-9_-]', '_', rfq.reference_no)
            filename = f"rfq-{safe_ref}.pdf"
            rfq.file.save(filename, ContentFile(pdf_file.getvalue()), save=True)

            messages.success(request, f"RFQ created successfully for Requisition {requisition.number}.")
            return redirect('rfq_list')
    else:
        form = RFQForm(instance=rfq)

    return render(request, 'procurement/rfq_create.html', {'form': form, 'plan': plan, 'requisition': requisition})


@login_required(login_url='login')
# @head_of_procurement_required
def send_rfq_to_supplier(request, reference_no):

    rfq = get_object_or_404(
        RFQ.objects.prefetch_related('supplier'),
        reference_no=reference_no
    )

    plan = rfq.req.procurement

    request_id = hashlib.sha256(
        f"rfq-{reference_no}".encode()
    ).hexdigest()

    if RFQSendLog.objects.filter(request_id=request_id, rfq=rfq
                                 ).exists() and rfq.status == "Sent":
        messages.warning(request, "RFQ already sent.")
        return redirect(
            "rfq_detail",
            slug=rfq.slug,
            reference_no=reference_no
        )

    if not rfq.file:
        messages.warning(request,"Generate the RFQ PDF before sending.")
        return redirect("rfq_detail", slug=rfq.slug, reference_no=reference_no)

    amount = (Requisition.objects.filter(procurement=plan
                                         ).aggregate(total=Sum("total"))
              .get("total")or 0)

    rfq.file.open("rb")
    pdf_content = rfq.file.read()
    rfq.file.close()

    sent_to = []
    errors = []

    connection = get_connection()

    try:
        connection.open()

        with transaction.atomic():

            for supplier in rfq.supplier.all():

                if not supplier.email:
                    errors.append(f"{supplier} has no email address.")
                    continue
                try:

                    email = EmailMessage(
                        subject=f"RFQ: {rfq.reference_no}",
                        body=f"""
                        Dear {supplier.full_name or supplier.title},
                        
                        Please find attached the Request for Quotation (RFQ).
                        
                        Kindly review and submit your quotation before the deadline.
                        
                        Please copy:
                        ricearua@yahoo.com
                        ricewn@gmail.com
                        
                        Deadline:
                        {rfq.deadline.strftime('%d %B %Y') if rfq.deadline else 'Not specified'}
                        
                        Regards,
                        RICE West Nile Procurement Team
                        """,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[supplier.email],
                        connection=connection,
                    )

                    email.attach(
                        f"{rfq.reference_no}.pdf",
                        pdf_content,
                        "application/pdf"
                    )

                    email.send()

                    RFQSendLog.objects.update_or_create(
                        rfq=rfq,
                        supplier=supplier,
                        request_id=request_id,
                        defaults={
                            "amount": amount,
                            "date_sent": timezone.now(),
                        },
                    )

                    sent_to.append(
                        f"{supplier} ({supplier.email})"
                    )

                except Exception as e:
                    errors.append(
                        f"{supplier} ({supplier.email}): {str(e)}"
                    )

    finally:
        connection.close()

    if sent_to:
        rfq.status = "Sent"
        rfq.save(update_fields=["status"])

        messages.success(
            request,
            f"RFQ {rfq.reference_no} sent successfully to "
            f"{len(sent_to)} supplier(s)."
        )

    if errors:
        messages.warning(
            request,
            "Some emails failed: " + "; ".join(errors)
        )

    if not sent_to:
        messages.error(
            request,
            "No emails were sent."
        )

    return redirect("rfq_list")


@login_required(login_url='login')
def rfq_list(request):

    rfq = (
        RFQ.objects
        .select_related(
            'req',
            'req__procurement',
            'req__procurement__project'
        )
        .prefetch_related('supplier')
        .order_by('-created_at')
    )

    # SEARCH
    search = request.GET.get('search')

    if search:
        rfq = rfq.filter(
            Q(reference_no__icontains=search) |
            Q(req__number__icontains=search) |
            Q(req__procurement__department__name__icontains=search) |
            Q(req__procurement__project__name__icontains=search) |
            Q(status__icontains=search)
        )

    # STATUS FILTER
    status = request.GET.get('status')

    if status:
        rfq = rfq.filter(status=status)

    # ANALYTICS
    total_rfqs = rfq.count()

    sent_count = rfq.filter(
        status='Sent'
    ).count()

    responded_count = rfq.filter(
        status='Responded'
    ).count()

    total_value = (
        rfq.aggregate(
            total=Sum('req__total')
        )['total'] or 0
    )

    context = {
        'rfq': rfq,
        'total_rfqs': total_rfqs,
        'sent_count': sent_count,
        'responded_count': responded_count,
        'total_value': total_value,
        'search_query': search or '',
        'status_filter': status or '',
    }

    return render(
        request,
        'procurement/rfq_list.html',
        context
    )


@login_required
def rfq_detail(request, slug, reference_no):
    rfq = get_object_or_404(
        RFQ.objects.select_related(
            'req',
            'req__procurement'
        ).prefetch_related(
            'supplier',
            'send_logs__supplier',
            'send_logs__purchase_orders',
            'req__items'
        ),
        slug=slug,
        reference_no=reference_no
    )

    plan = rfq.req.procurement
    items = rfq.req.items.all()

    send_logs = rfq.send_logs.prefetch_related(
        'purchase_orders'
    ).select_related(
        'supplier'
    )

    awarded_po = (
        PurchaseOrder.objects
        .filter(rfq=rfq, sent=True)
        .select_related('supplier')
        .first()
    )

    # Attach awarded amount directly to each log
    for log in send_logs:
        po = log.purchase_orders.filter(sent=True).first()

        log.po = po
        log.awarded_amount = (
            po.final_amount
            if po and po.final_amount
            else None
        )

    context = {
        "rfq": rfq,
        "plan": plan,
        "items": items,
        "send_logs": send_logs,
        "awarded_po": awarded_po,
    }

    if request.GET.get("format") == "pdf":
        return render_pdf(
            "procurement/rfq_pdf.html",
            context,
            f"{rfq.reference_no}.pdf",
        )

    return render(
        request,
        "procurement/rfq_detail.html",
        context
    )


def trash_rfq(request, pk, slug):
    rfq = get_object_or_404(RFQ, pk=pk, slug=slug)
    if request.method == 'POST':
        messages.success(request, f"RFQ {rfq} has been trashed successfully.")
        rfq.delete()
        return redirect('rfq_list')
    return render(request, 'delete_confirmation.html',
                  {'delete': rfq, "cancel_url": reverse('rfq_list')})


def log_rfq(request, reference_no):
    rfq = get_object_or_404(RFQ, reference_no=reference_no)
    rfq_log = RFQSendLog.objects.filter(rfq=rfq)
    po = PurchaseOrder.objects.filter(rfq=rfq).first()
    return render(request, 'procurement/rfq_log.html', {
        'rfq_log': rfq_log,'rfq': rfq, 'po': po})
