from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
import calendar


def first_tuesday_of_month(year, month):
    d = date(year, month, 1)
    wd = d.weekday()  # Monday=0
    offset = (1 - wd) % 7
    return d + timedelta(days=offset)


def can_submit_presentation(today: date):
    year = today.year
    month = today.month

    deadline = date(year, month, 28)
    meeting_day = first_tuesday_of_month(year, month)

    # Rule 1 — Can submit before 28th
    if today <= deadline:
        return True, ""

    # Rule 2 — After 28th, must wait until after meeting day
    if today <= meeting_day:
        return False, (
            f"You cannot submit this month because the deadline (28/{month}/{year}) has passed. "
            f"You may submit again only after the monthly meeting on {meeting_day}."
        )

    # Rule 3 — After meeting day, allow again
    return True, ""


def check_report_deadline(report_type, today: date):
    # if user:
    #     try:
    #         if user.groups.filter(name="REVIEW").exists() or getattr(user, 'can_review', False):
    #             return True, ""
    #     except Exception:
    #         pass

    if hasattr(today, 'date'):
        today = today.date()
    year = today.year
    month = today.month

    if report_type == 'MONTHLY':
        deadline = date(year, month, 28)
        if today <= deadline:
            return True, ""
        return False, f"Oops! Monthly reports must be submitted on or before {deadline}."

    if report_type == 'QUARTERLY':
        q = (month - 1)//3 + 1  # 1–4
        quarter_end_month = q * 3
        deadline = date(year, quarter_end_month, 5)
        if today <= deadline:
            return True, ""
        return False, f"Quarterly reports must be submitted on or before {deadline}."

    if report_type == 'BIANNUAL':
        deadline = date(year, 6, 15)
        if today <= deadline:
            return True, ""
        return False, f"Oops! Biannual reports must be submitted on or before {deadline}."

    if report_type == 'ANNUAL':
        deadline = date(year, 11, 15)
        if today <= deadline:
            return True, ""
        return False, f"Annual reports must be submitted on or before {deadline}."

    return True, ""


def send_notification_email(subject, message, recipient_email):
    """Wrapper around django.core.mail.send_mail; uses settings.EMAIL_* values."""
    if not recipient_email:
        return False
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings,'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
        recipient_list=[recipient_email],
        fail_silently=False,
    )
    return True


