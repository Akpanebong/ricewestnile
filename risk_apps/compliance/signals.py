from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from datetime import timedelta
from django.core.mail import send_mail
from notification.models import Notification
from notification.utils import notify
from .models import VendorDueDiligence, PartnerDueDiligence


@receiver(post_save, sender=VendorDueDiligence)
def update_vendor_status(sender, instance, **kwargs):
    if instance.end_date:
        today = now().date()
        reminder_date = instance.end_date - timedelta(days=90)

        group = Group.objects.get(name="GARCIS")
        users = group.user_set.all()

        # 3 months before
        if reminder_date <= today < instance.end_date:
            if instance.performance_status != "due_for_renewal":
                instance.performance_status = "due_for_renewal"
                instance.save(update_fields=["performance_status"])

                emails = [u.email for u in users if u.email]
                # Email notification
                send_mail(
                    subject="Vendor Renewal Reminder",
                    message=f"{instance.vendor_name} is due for renewal.",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=emails,
                )
                notify(
                    title="Vendor Renewal Due",
                    message=f"{instance.vendor_name} requires renewal review",
                    users=users,
                    category=Notification.Category.INFO,
                    action_url=''
                )

        # End date reached
        if today >= instance.end_date:
            if instance.performance_status != "terminated":
                instance.performance_status = "terminated"
                instance.save(update_fields=["performance_status"])


@receiver(post_save, sender=PartnerDueDiligence)
def partner_due_diligence_alert(sender, instance, **kwargs):

    if not instance.end_date:
        return

    today = now().date()
    reminder_date = instance.end_date - timedelta(days=90)

    # Get GARCIS group users
    try:
        group = Group.objects.get(name="GARCIS")
        users = group.user_set.all()
    except Group.DoesNotExist:
        return

    emails = [u.email for u in users if u.email]

    # 🔔 3 MONTHS REMINDER
    if reminder_date <= today < instance.end_date:

        # EMAIL
        send_mail(
            subject="Partner Due Diligence Renewal Alert",
            message=f"{instance.partner_name} is approaching review/renewal period.",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=emails,
            fail_silently=True,
        )

        # IN-APP
        notify(
            title="Partner Renewal Alert",
            message=f"{instance.partner_name} requires due diligence review.",
            users=users,
            category=Notification.Category.WARNING,
            action_url=""
        )

    # ⛔ EXPIRED
    if today >= instance.end_date:
        notify(
            title="Partner Due Diligence Expired",
            message=f"{instance.partner_name} has reached end date.",
            users=users,
            category=Notification.Category.CRITICAL,
            action_url=""
        )
