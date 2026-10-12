import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect

from django.contrib.auth.decorators import login_required

from .system_catalog import visible_systems

logger = logging.getLogger(__name__)

@login_required
def system_home(request):
    return render(request, "enterprise/system_home.html", {"systems": visible_systems(request.user)})


def custom_404_view(request, exception):
    return render(request, "404.html", status=404)


def custom_500_view(request):
    report_id = uuid.uuid4().hex
    report = getattr(request, "_error_report_context", None) or {
        "exception_type": "Unhandled server error",
        "exception_message": "No exception details were available.",
        "traceback": "No traceback was available.",
        "path": request.get_full_path(),
        "method": request.method,
        "user": "Anonymous",
        "ip": request.META.get("REMOTE_ADDR", "Unknown"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "Unknown")[:1000],
    }
    report.update(_request_details(request))
    cache.set(f"500-report:{report_id}", report, timeout=3600)
    return render(request, "500.html", {"report_id": report_id}, status=500)


def _request_details(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        user_details = f"{user.get_username()} (id={user.pk})"
    else:
        user_details = "Anonymous"

    return {
        "path": request.get_full_path(),
        "method": request.method,
        "user": user_details,
        "ip": request.META.get("REMOTE_ADDR", "Unknown"),
        "forwarded_for": request.META.get("HTTP_X_FORWARDED_FOR", "Not provided"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "Unknown")[:1000],
        "referer": request.META.get("HTTP_REFERER", "Not provided")[:1000],
    }


def _error_report_message(report_id, report):
    return (
        "A user reported an internal server error.\n\n"
        f"Report ID: {report_id}\n"
        f"Exception: {report['exception_type']}\n"
        f"Message: {report['exception_message']}\n"
        f"Request: {report['method']} {report['path']}\n"
        f"User: {report['user']}\n"
        f"IP: {report['ip']}\n"
        f"Forwarded for: {report.get('forwarded_for', 'Not provided')}\n"
        f"User agent: {report['user_agent']}\n"
        f"Referer: {report.get('referer', 'Not provided')}\n\n"
        f"Traceback:\n{report['traceback']}"
    )


@csrf_protect
def report_500_error(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    report_id = request.POST.get("report_id", "")
    report = cache.get(f"500-report:{report_id}")
    if not report:
        return render(request, "500.html", {
            "error_message": "This report has expired. Please try again if the problem continues.",
        }, status=410)

    recipient = settings.EMAIL_HOST_USER
    if not recipient:
        logger.error("Cannot send error report %s: EMAIL_HOST_USER is empty", report_id)
        return render(request, "500.html", {
            "error_message": "The report could not be sent. Please try again later.",
        }, status=503)

    try:
        send_mail(
            f"RICE WN 500 error report [{report_id[:12]}]",
            _error_report_message(report_id, report),
            settings.DEFAULT_FROM_EMAIL or recipient,
            [recipient],
            fail_silently=False,
        )

    except Exception:
        logger.exception("Could not send error report %s", report_id)
        return render(request, "500.html", {
            "error_message": "The report could not be sent. Please try again later.",
        }, status=503)

    cache.delete(f"500-report:{report_id}")
    return render(request, "500.html", {"report_sent": True}, status=200)


def custom_403_view(request, exception):
    return render(request, "403.html", status=403)


def custom_400_view(request, exception):
    return render(request, "400.html", status=400)
