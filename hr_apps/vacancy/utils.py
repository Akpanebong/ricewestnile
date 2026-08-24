from django.core.mail import send_mail
from django.conf import settings


def notify_ed_published(request_obj):
    send_mail(
        subject="Recruitment Published",
        message=f"The recruitment request '{request_obj.title}' has been published.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request_obj.requested_by.email],
        fail_silently=True
    )
