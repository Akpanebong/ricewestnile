from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from notification.models import Notification, NotificationRecipient
from notification.utils import notify
from risk_apps.governance.models import Control, Policy, StakeholderEngagement
from risk_apps.governance.utils import governance_reviewers


class Command(BaseCommand):
    REMINDER_DAYS = (30, 20, 10, 7, 1)
    help = "Send governance review/test/follow-up reminders at 30, 20, 10, 7, and 1 day(s)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        recipients = governance_reviewers()
        recipient_list = list(recipients)
        emails = list(dict.fromkeys(u.email for u in recipient_list if u.email))
        sent = 0

        reminders = [
            (Policy, "next_review_date", "Policy review", "next review date", "policy_detail"),
            (Control, "next_test_date", "Control test", "next test date", "control_detail"),
            (StakeholderEngagement, "follow_up_date", "Stakeholder follow-up", "follow-up date", "stakeholder_detail"),
        ]

        for model, date_field, kind, date_label, url_name in reminders:
            for days_until in self.REMINDER_DAYS:
                target_date = today + timedelta(days=days_until)
                for document in model.objects.filter(**{date_field: target_date}):
                    document_url = reverse(url_name, kwargs={"pk": document.pk})
                    absolute_url = self._absolute_url(document_url)
                    title = f"{kind} due in {days_until} day{'s' if days_until != 1 else ''}: {document}"
                    message = f"{document} has a {date_label} of {target_date:%d %B %Y}. Open the document: {document_url}"

                    # Keep the in-app link relative so it preserves the current host/session.
                    # The email receives the fully qualified URL instead.
                    if Notification.objects.filter(
                        title=title,
                        action_url=document_url,
                        created_at__date=today,
                    ).exists():
                        continue

                    notify(
                        title=title,
                        message=message,
                        users=recipient_list,
                        category=Notification.Category.WARNING,
                        source_app=Notification.Source.GOVERNANCE,
                        action_url=document_url,
                    )
                    if emails:
                        send_mail(
                            subject=title,
                            message=f"{message}\n\nAccess the document: {absolute_url}",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=emails,
                            fail_silently=False,
                        )
                        NotificationRecipient.objects.filter(
                            notification__title=title,
                            notification__action_url=document_url,
                        ).update(
                            email_sent=True,
                            email_sent_at=timezone.now(),
                        )
                    sent += 1

        self.stdout.write(self.style.SUCCESS(f"Created {sent} governance reminder(s)."))

    @staticmethod
    def _absolute_url(path):
        base_url = getattr(settings, "SITE_URL", "").rstrip("/")
        return f"{base_url}{path}" if base_url else path
