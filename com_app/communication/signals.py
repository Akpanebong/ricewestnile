from django.db.models.signals import post_save
from django.dispatch import receiver
from notification.models import Notification
from notification.utils import notify
from .models import Report
from django.contrib.auth import get_user_model
from .utils import send_notification_email
from django.urls import reverse
from django.conf import settings

User = get_user_model()


@receiver(post_save, sender=Report)
def report_post_save(sender, instance, created, **kwargs):
    # When a report is submitted, notify all REVIEW group members
    if created:
        # create notifications for all reviewers
        reviewers = User.objects.filter(groups__name='REVIEW').distinct()
        for r in reviewers:
            n = notify(
                title=f'New report: {instance.report_type}',
                message=f'A new {instance.report_type} report was submitted by {instance.sent_by}.',
                users=r,
                action_url=reverse('comm:report_detail', args=[instance.pk])
            )
            # attempt to send email to reviewer if they have an email configured
            try:
                send_notification_email(n.title + ' — Communication System', n.message + '\n\nOpen: ' + settings.SITE_URL + n.action_url, r.email)
            except Exception:
                # don't crash on email failure
                pass
