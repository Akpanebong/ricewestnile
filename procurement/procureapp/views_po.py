from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils.html import strip_tags
from .models import RFQSendLog, PurchaseOrder, SupplierSpendReport
from .forms import PurchaseOrderForm
import os
from io import BytesIO
from xhtml2pdf import pisa


def create_purchase_order(request, send_log_id):
    send_log = get_object_or_404(RFQSendLog, id=send_log_id)
    supplier = send_log.supplier
    rfq = send_log.rfq
    requisition = rfq.req
    plan = requisition.procurement
    products = requisition.items.all()

    items_total = sum(item.line_total() for item in products)

        # RESTRICT MULTIPLE SUPPLIER AWARDS
    existing_po = PurchaseOrder.objects.filter(rfq=rfq, sent=True).first()

    if existing_po:

        if existing_po.send_log == send_log:
            messages.warning(request, f'LPO already sent to {supplier}.')
        else:
            messages.error(request,f'This RFQ has already been awarded to 'f'{existing_po.supplier}.')

        return redirect('log_rfq', send_log.rfq.reference_no)

    if request.method == 'POST':
        # LOGO_PATH = os.path.join(settings.BASE_DIR, "static/assets/images/ricewn.png")
        LOGO_PATH = os.path.join(settings.BASE_DIR, "static", "assets", "images", "ricewn.png")

        form = PurchaseOrderForm(request.POST, rfq=rfq, supplier=supplier)
        if form.is_valid():
            po = form.save(commit=False)
            po.send_log = send_log
            po.supplier = supplier
            po.rfq = rfq
            po.requisition = requisition
            po.procurement_plan = plan
            po.po_number = f"LPO-{rfq.id}-{send_log.supplier.id}-{send_log.id}"
            po.save()

            context = {
                'total_amount': form.cleaned_data['final_amount'],
                'po': po,
                'plan': plan,
                'products': products,
                'logo_url': LOGO_PATH
            }

            # === Render PDF ===
            html_pdf = render_to_string('po/purchase_order_pdf.html', context)
            pdf_buffer = BytesIO()
            pisa.CreatePDF(BytesIO(html_pdf.encode('utf-8')), dest=pdf_buffer)
            filename = f'purchase_order_{po.po_number}.pdf'
            po.pdf.save(filename, pdf_buffer)

            # === Render Email HTML ===
            email_html = render_to_string('po/purchase_order_email.html', {'po': po})
            email_text = strip_tags(email_html)  # Fallback plain text

            subject = f"Purchase Order {po.po_number} from {plan.department if hasattr(plan, 'department') else 'Procurement Department'}"
            recipient = [po.supplier.email]
            from_email = settings.EMAIL_HOST_USER

            # === Send Email ===
            email = EmailMultiAlternatives(subject, email_text, from_email, recipient,)
            email.attach_alternative(email_html, "text/html")
            email.attach(filename, pdf_buffer.getvalue(), 'application/pdf')
            email.send()
            messages.success(request, f'LPO with PO# ({po.po_number}) generated and sent to {supplier})')
            po.sent = True
            po.save()
            report, _ = SupplierSpendReport.objects.get_or_create(
                purchase_order=po,
                defaults={
                    'supplier': supplier,
                    'requisition': po.requisition,
                }
            )
            report.supplier = supplier
            report.requisition = po.requisition
            report.recompute()
            return redirect(po.get_absolute_url())

    else:
        form = PurchaseOrderForm(rfq=rfq, supplier=supplier, initial={'supplier': supplier})
        form.fields['supplier'].disabled = True

    return render(request, 'po/create_purchase_order.html', {'form': form,'products': products, 'send_log': send_log, 'items_total': items_total})


def purchase_order_list(request):
    po = PurchaseOrder.objects.select_related(
        'supplier',
        'requisition',
    ).prefetch_related('spend_reports').filter(sent=True)
    total_amount = po.aggregate(
        total=Sum('final_amount')
    )['total'] or 0
    total_po = po.count()

    active_po = po.filter(sent=True).count()

    cancelled_po = po.filter(sent=False).count()
    context = {
        'po': po,
        'total_amount': total_amount,
        'total_po': total_po,
        'active_po': active_po,
        'cancelled_po': cancelled_po,
    }
    return render(request, 'po/purchase_order_list.html', context)


def purchase_order_detail(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    return render(request, 'po/purchase_order_detail.html', {'po': po})


@login_required(login_url='login')
def po_cancel(request, slug):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'send_log__rfq'), slug=slug)

    if not po.sent:
        messages.info(request,
            f"Purchase Order {po.po_number or 'N/A'} is already cancelled.")
        return redirect('log_rfq', po.send_log.rfq.reference_no)

    if request.method == 'POST':

        # Preserve values before modification
        old_po_number = po.po_number
        issue_date = po.issue_date
        supplier = po.supplier

        try:

            # Send cancellation email FIRST
            if supplier and supplier.email:

                send_mail(
                    subject='Purchase Order Cancellation Notice',
                    message=(
                        f"Dear {supplier.full_name or supplier.title},\n\n"
                        f"We regret to inform you that the Purchase Order "
                        f"({old_po_number}) issued on {issue_date:%d %B %Y} "
                        f"has been officially cancelled.\n\n"
                        f"Please disregard any previous instructions "
                        f"relating to this Purchase Order.\n\n"
                        f"For clarification, kindly contact the "
                        f"Procurement Department.\n\n"
                        f"Regards,\n"
                        f"Procurement Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[supplier.email],
                    fail_silently=False,
                )

            # Delete supplier spend report if it exists
            SupplierSpendReport.objects.filter(purchase_order=po).delete()

            # Cancel PO
            po.sent = False
            po.po_number = None
            po.final_amount = None
            po.save(update_fields=['sent', 'po_number', 'final_amount'])

            messages.success(
                request,
                f"Purchase Order {old_po_number} was successfully cancelled."
            )

        except Exception as e:

            messages.error(
                request,
                f"Unable to complete cancellation. Error: {e}"
            )

        return redirect('log_rfq',po.send_log.rfq.reference_no)

    return render(request, 'po/po_cancel_confirm.html',{'po': po})
