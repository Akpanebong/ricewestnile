from openpyxl import Workbook
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from account.models import Profile
from notification.models import Notification, NotificationRecipient
from notification.utils import notify


def export_assets_to_excel(queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Assets"

    headers = [
        'Asset No', 'Date', 'Category', 'Description',
        'Purchase Value', 'Place', 'Depreciation', 'Net Book Value'
    ]
    ws.append(headers)

    for asset in queryset:
        ws.append([
            asset.asset_no,
            asset.date_of_entry,
            asset.category,
            asset.description,
            asset.purchase_value,
            asset.place,
            asset.depreciation_accumulated,
            asset.net_book_value
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=assets.xlsx'
    wb.save(response)
    return response


def get_client_ip(request):
    """
    Retrieve the real client IP address from the request.
    Works with reverse proxies and load balancers.
    """

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # X-Forwarded-For may contain multiple IPs: client, proxy1, proxy2
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip


def procurement_recipients():
    """Resolve procurement staff by group or department, with an admin fallback."""
    recipients = Profile.objects.filter(is_active=True).filter(
        Q(groups__name__icontains="procure") |
        Q(department__name__icontains="procure")
    ).distinct()
    if not recipients.exists():
        recipients = Profile.objects.filter(is_active=True, is_staff=True)
    return recipients


def notify_procurement_of_disposal(request, disposal):
    """Create an in-app notification and attempt email delivery to procurement."""
    asset = disposal.asset
    title = "Asset declared for disposal"
    message = f"Asset {asset.asset_no} ({asset.description[:100]}) has been declared for disposal and requires review."
    action_url = "/procurement/asset-disposals/"
    recipients = procurement_recipients()
    notification = notify(
        users=recipients,
        title=title,
        message=message,
        request=request,
        source_app=Notification.Source.PROCUREMENT,
        category=Notification.Category.WARNING,
        action_url=action_url,
    )

    email_recipients = list(recipients.exclude(email=""))
    if email_recipients:
        for recipient in email_recipients:
            try:
                send_mail(
                    subject=title,
                    message=f"Dear {recipient.get_full_name() or recipient.username},\n\n{message}\n\nReview: {action_url}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    fail_silently=False,
                )
                NotificationRecipient.objects.filter(
                    notification=notification, recipient=recipient
                ).update(email_sent=True, email_sent_at=timezone.now())
            except Exception:
                # The in-app notification remains available if SMTP is unavailable.
                continue
    return notification, recipients.count()
