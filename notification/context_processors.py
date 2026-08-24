from django.contrib.auth.decorators import login_required

from .models import NotificationRecipient


# @login_required(login_url='login')
def notifications(request):

    if not request.user.is_authenticated:

        return {}

    unread = NotificationRecipient.objects.filter(
        recipient=request.user,
        is_deleted=False,
        is_read=False,
    )

    return {

        "notification_unread": unread,
        "notification_unread_count": unread.count(),

    }