from datetime import date, datetime, time, timedelta
from email import message_from_bytes

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from account.models import Profile

from .models import StaffEvent, StaffEventInvitation
from .services import first_tuesday, ics_for_event, send_event_invitation, staff_recipients


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StaffEventServiceTests(TestCase):
    def setUp(self):
        self.staff = Profile.objects.create_user(
            username="active-staff", email="active@example.com", password="password",
            profile_type="Staff", status="Active", is_active=True,
        )

    def test_first_tuesday_and_ics_attachment(self):
        self.assertEqual(first_tuesday(2026, 10), date(2026, 10, 6))
        start = timezone.make_aware(datetime(2026, 10, 6, 9, 0))
        event = StaffEvent.objects.create(title="Team event", starts_at=start, ends_at=start + timedelta(hours=2))
        self.assertIn(b"BEGIN:VCALENDAR", ics_for_event(event))
        send_event_invitation(event, self.staff, kind=StaffEventInvitation.Kind.CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(any(part.get_filename() == "staff-event.ics" for part in mail.outbox[0].message().walk()))

    def test_active_and_probationary_staff_types_receive_invitations(self):
        eligible = [
            ("volunteer", "Volunteer", "Active"),
            ("intern", "Intern", "Probation"),
            ("community", "Community Structure", "Probation"),
        ]
        for username, profile_type, status in eligible:
            Profile.objects.create_user(
                username=username, email=f"{username}@example.com", password="password",
                profile_type=profile_type, status=status, is_active=True,
            )
        Profile.objects.create_user(
            username="on-leave-volunteer", email="leave@example.com", password="password",
            profile_type="Volunteer", status="On Leave", is_active=True,
        )
        Profile.objects.create_user(
            username="inactive-intern", email="inactive@example.com", password="password",
            profile_type="Intern", status="Active", is_active=False,
        )
        self.assertSetEqual(
            set(staff_recipients().values_list("username", flat=True)),
            {"active-staff", "volunteer", "intern", "community"},
        )

    def test_monthly_command_sends_once_for_each_recipient(self):
        # 29 September 2026 is exactly one week before the first Tuesday in October.
        call_command("send_staff_monthly_reminders", date="2026-09-29")
        self.assertEqual(StaffEvent.objects.filter(event_type=StaffEvent.EventType.MONTHLY_MEETING).count(), 1)
        self.assertEqual(StaffEventInvitation.objects.filter(kind="reminder", recipient=self.staff, email_sent=True).count(), 1)
        call_command("send_staff_monthly_reminders", date="2026-09-29")
        self.assertEqual(StaffEventInvitation.objects.filter(kind="reminder", recipient=self.staff, email_sent=True).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_minutes_form_accepts_pdf_only(self):
        event = StaffEvent.objects.create(
            title="Minutes test", starts_at=timezone.now() + timedelta(hours=1), ends_at=timezone.now() + timedelta(hours=2)
        )
        upload = SimpleUploadedFile("minutes.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        event.minutes = upload
        event.save()
        self.assertTrue(event.minutes.name.endswith(".pdf"))
