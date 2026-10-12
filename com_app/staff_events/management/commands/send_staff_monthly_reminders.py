from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from com_app.staff_events.models import StaffEvent
from com_app.staff_events.services import (
    first_tuesday,
    monthly_meeting_datetime,
    notify_event_recipients,
    staff_recipients,
)


class Command(BaseCommand):
    help = "Create the upcoming staff monthly meeting and send its one-week calendar reminder."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Use YYYY-MM-DD instead of today (useful for operations/tests).")

    def handle(self, *args, **options):
        today = timezone.localdate()
        if options.get("date"):
            today = timezone.datetime.strptime(options["date"], "%Y-%m-%d").date()
        target = today + timedelta(days=7)
        meeting_day = first_tuesday(target.year, target.month)
        if meeting_day != target:
            self.stdout.write("No staff monthly meeting reminder is due today.")
            return

        meeting_start = monthly_meeting_datetime(meeting_day)
        meeting_end = meeting_start + timedelta(hours=getattr(settings, "STAFF_MONTHLY_MEETING_DURATION_HOURS", 2))
        event, created = StaffEvent.objects.get_or_create(
            meeting_month=meeting_day.replace(day=1),
            defaults={
                "title": getattr(settings, "STAFF_MONTHLY_MEETING_TITLE", "Staff Monthly Meeting"),
                "description": getattr(settings, "STAFF_MONTHLY_MEETING_DESCRIPTION", "Monthly staff meeting."),
                "location": getattr(settings, "STAFF_MONTHLY_MEETING_LOCATION", ""),
                "starts_at": meeting_start,
                "ends_at": meeting_end,
                "event_type": StaffEvent.EventType.MONTHLY_MEETING,
            },
        )
        recipients = staff_recipients()
        notify_event_recipients(event, kind="reminder", recipients=recipients)
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Found'} {event.title}; reminder processed for {recipients.count()} active staff."
        ))
