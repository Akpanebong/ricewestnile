from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from account.models import Profile
from notification.utils import notify

from .models import StaffEvent, StaffEventInvitation


def communication_member(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return (user.groups.filter(name__iexact="communication").exists()
            or user.groups.filter(name__iexact="communications").exists()
            or user.groups.filter(name__iexact="Communications").exists()
            or user.groups.filter(name__iexact="Communication").exists())


def staff_recipients():
    """Return all eligible people who should receive staff event invitations."""
    return Profile.objects.filter(
        is_active=True,
        status__in=("Active", "Probation"),
        profile_type__in=("Staff", "Volunteer", "Intern", "Community Structure"),
    ).exclude(email="").order_by("email")


def first_tuesday(year, month):
    first = date(year, month, 1)
    return first + timedelta(days=(1 - first.weekday()) % 7)


def monthly_meeting_datetime(day):
    hour = getattr(settings, "STAFF_MONTHLY_MEETING_HOUR", 9)
    minute = getattr(settings, "STAFF_MONTHLY_MEETING_MINUTE", 0)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def ics_for_event(event):
    start = timezone.localtime(event.starts_at)
    end = timezone.localtime(event.ends_at)
    stamp = timezone.now().astimezone(dt_timezone.utc)
    description = (event.description or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,")
    location = (event.location or "").replace("\\", "\\\\").replace(",", "\\,")
    def fmt(value):
        return value.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RICE West Nile//Staff Events//EN",
        "CALSCALE:GREGORIAN", "METHOD:REQUEST", "BEGIN:VEVENT",
        f"UID:staff-event-{event.pk}@{getattr(settings, 'STAFF_EVENT_ICS_DOMAIN', 'rice-westnile.local')}",
        f"DTSTAMP:{fmt(stamp)}", f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
        f"SUMMARY:{event.title}", f"DESCRIPTION:{description}", f"LOCATION:{location}",
        "STATUS:CONFIRMED", "SEQUENCE:0", "END:VEVENT", "END:VCALENDAR", "",
    ]).encode("utf-8")


def invite_subject(event, kind):
    return ("Reminder: " if kind == StaffEventInvitation.Kind.REMINDER else "Invitation: ") + event.title


def invite_body(event, kind):
    when = timezone.localtime(event.starts_at).strftime("%A, %d %B %Y at %I:%M %p")
    text = f"You are invited to {event.title}.\n\nDate and time: {when}\n"
    if event.location:
        text += f"Location: {event.location}\n"
    if event.description:
        text += f"\n{event.description}\n"
    if kind == StaffEventInvitation.Kind.REMINDER:
        text += "\nThis is the scheduled one-week reminder. The attached calendar file can be added to your calendar."
    else:
        text += "\nThe attached calendar file can be added to your calendar."
    return text


def send_event_invitation(event, recipient, *, kind):
    invitation, _ = StaffEventInvitation.objects.get_or_create(event=event, recipient=recipient, kind=kind)
    if invitation.email_sent or not recipient.email:
        return invitation
    try:
        email = EmailMessage(
            subject=invite_subject(event, kind),
            body=invite_body(event, kind),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
        )
        email.attach("staff-event.ics", ics_for_event(event), "text/calendar; method=REQUEST; charset=UTF-8")
        email.send(fail_silently=False)
        invitation.email_sent = True
        invitation.sent_at = timezone.now()
        invitation.error_message = ""
        invitation.save(update_fields=("email_sent", "sent_at", "error_message"))
    except Exception as exc:
        invitation.error_message = str(exc)[:2000]
        invitation.save(update_fields=("error_message",))
    return invitation


def notify_event_recipients(event, *, kind, recipients):
    notify(
        title=invite_subject(event, kind), message=invite_body(event, kind), users=recipients,
        source_app="communication", action_url="/communication/events/",
    )
    for recipient in recipients:
        send_event_invitation(event, recipient, kind=kind)


@transaction.atomic
def create_event_and_invite(*, event, recipients):
    event.save()
    notify_event_recipients(event, kind=StaffEventInvitation.Kind.CREATED, recipients=recipients)
    return event
