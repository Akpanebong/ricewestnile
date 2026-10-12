from datetime import date, timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from django.shortcuts import redirect


class GroupRequiredMixin:
    allowed_groups = set()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.groups.filter(name__in=self.allowed_groups).exists():
            return redirect('profile_update', pk=request.user.pk, slug=request.user.slug)
        return super().dispatch(request, *args, **kwargs)


def first_tuesday_of_month(year, month):
    d = date(year, month, 1)
    offset = (1 - d.weekday()) % 7  # Tuesday = 1
    return d + timedelta(days=offset)


def get_next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def get_previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def can_submit_presentation(today):
    year, month = today.year, today.month

    # 🔹 Deadlines
    current_deadline = date(year, month, 28)

    prev_year, prev_month = get_previous_month(year, month)
    prev_deadline = date(prev_year, prev_month, 28)

    # 🔹 Meeting days
    current_meeting = first_tuesday_of_month(year, month)
    next_year, next_month = get_next_month(year, month)
    next_meeting = first_tuesday_of_month(next_year, next_month)

    # 🔒 RULE 1: Previous month lock (FIXED)
    if prev_deadline < today <= current_meeting:
        return False, {
            "reason": "Locked until after meeting day",
            "deadline": prev_deadline,
            "meeting_day": current_meeting,
            "unlock_date": current_meeting + timedelta(days=1),
        }

    # 🔒 RULE 2: Current month lock after 28th (FIXED)
    if current_deadline < today <= next_meeting:
        return False, {
            "reason": "Post-deadline lock until next meeting passes",
            "deadline": current_deadline,
            "meeting_day": next_meeting,
            "unlock_date": next_meeting + timedelta(days=1),
        }

    return True, {}


# ==============================
# REPORT DEADLINE CONFIGURATION
# ==============================
REPORT_RULES = {
    "MONTHLY": lambda y, m: date(y, m, 28),  # ✅ fixed to 6th
    "QUARTERLY": lambda y, m: date(y, ((m - 1)//3 + 1) * 3, 5),
    "BIANNUAL": lambda y, m: date(y, 6, 15),
    "ANNUAL": lambda y, m: date(y, 11, 15),
}


def check_report_deadline(report_type: str, today=None):
    today = today or timezone.now().date()

    if hasattr(today, "date"):
        today = today.date()

    report_type = (report_type or "").upper()

    if report_type not in REPORT_RULES:
        return False, f"Invalid report type: {report_type}"

    year, month = today.year, today.month

    # 🔹 Deadline
    deadline = REPORT_RULES[report_type](year, month)

    # 🔹 Meeting logic (same as presentation)
    meeting_day = first_tuesday_of_month(year, month)

    next_year, next_month = get_next_month(year, month)
    next_meeting = first_tuesday_of_month(next_year, next_month)

    # 🔒 RULE 1: Block AFTER deadline until meeting passes
    if deadline < today <= next_meeting:
        return False, (
            f"{report_type.capitalize()} submission locked after deadline. "
            f"Reopens on {(next_meeting + timedelta(days=1)).strftime('%Y-%m-%d')}."
        )

    # 🔒 RULE 2: Block BEFORE meeting (carry-over lock)
    if today <= meeting_day and today > deadline.replace(day=1):
        return False, (
            f"{report_type.capitalize()} submission locked until after meeting day "
            f"({meeting_day.strftime('%Y-%m-%d')})."
        )

    # ✅ Allowed
    return True, ""


def send_notification_email(subject, message, recipient_email, fail_silently=False):
    """
    Robust email sender with validation.
    """
    if not recipient_email:
        return False

    try:
        send_mail(
            subject=subject.strip(),
            message=message.strip(),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com"),
            recipient_list=[recipient_email],
            fail_silently=fail_silently,
        )
        return True
    except Exception as e:
        # In production, log this instead
        print(f"Email send failed: {e}")
        return False


class ReviewAccessMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user

        # ✅ Defensive checks
        if not user.is_authenticated:
            return False

        # Avoid crash if method doesn't exist
        if not hasattr(user, "can_access_review"):
            return False

        return user.can_access_review()
