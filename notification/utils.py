# from django.db import transaction
#
# from account.models import Profile
#
# from .models import Notification, NotificationRecipient
#
#
# @transaction.atomic
# def notify(*, title, message, request=None,users=None, group_name=None,broadcast=False,category=Notification.Category.INFO,
#            source_app=Notification.Source.CORE,attachment=None,action_url="",):
#     """
#     Enterprise notification wrapper.
#
#     Priority
#
#     1. Explicit users
#     2. Group
#     3. Broadcast
#     4. Empty queryset
#
#     Examples
#
#     notify(users=request.user,...)
#
#     notify(users=[u1,u2],...)
#
#     notify(group_name="HR",...)
#
#     notify(broadcast=True,...)
#     """
#
#     if users is None:
#
#         if group_name:
#
#             users = Profile.objects.filter(
#
#                 groups__name=group_name,
#
#                 is_active=True,
#
#             ).distinct()
#
#         elif broadcast:
#
#             users = Profile.objects.filter(
#
#                 is_active=True
#
#             )
#
#         else:
#
#             users = Profile.objects.none()
#
#     return send_notification(
#
#         users=users,
#
#         request=request,
#
#         title=title,
#
#         message=message,
#
#         category=category,
#
#         source_app=source_app,
#
#         attachment=attachment,
#
#         action_url=action_url,
#
#     )
#
#
# #
# #
# # def notify(*,title, message, category="info", source_app="core", request=None,
# #            users=None, group_name=None, attachment=None,url=""):
# #     """
# #     Send a notification to specific users or to all members of a group.
# #
# #     Priority:
# #         1. Explicit users
# #         2. Group members
# #         3. No recipients
# #     """
# #
# #     if users is None:
# #
# #         if group_name:
# #
# #             group = Group.objects.filter(name=group_name).first()
# #
# #             users = (
# #                 Profile.objects.filter(groups=group)
# #                 if group
# #                 else Profile.objects.none()
# #             )
# #
# #         else:
# #
# #             users = Profile.objects.none()
# #
# #     return send_notification(
# #         users=users,
# #         title=title,
# #         message=message,
# #         category=category,
# #         source_app=source_app,
# #         attachment=attachment,
# #         url=url,
# #         request=request,
# #     )
# #
# #
# # @transaction.atomic
# # def send_notification(*, users, title, message, category=Notification.INFO, source_app="core",
# #                       attachment=None, url="", created_by=None, request=None,):
# #
# #     # Remove duplicates while preserving order
# #     users = list(dict.fromkeys(users))
# #
# #     if not users:
# #         return None
# #
# #     notification = Notification.objects.create(
# #         title=title,
# #         message=message,
# #         category=category,
# #         source_app=source_app,
# #         attachment=attachment,
# #         url=url,
# #         created_by=created_by,
# #     )
# #
# #     recipient_objects = [
# #         NotificationRecipient(
# #             notification=notification,
# #             recipient=user,
# #         )
# #         for user in users
# #     ]
# #
# #     NotificationRecipient.objects.bulk_create(recipient_objects)
# #
# #     if request:
# #
# #         scheme = "https" if request.is_secure() else "http"
# #
# #         full_url = (
# #             f"{scheme}://"
# #             f"{get_current_site(request).domain}"
# #             f"{notification.get_absolute_url()}"
# #         )
# #
# #     else:
# #
# #         full_url = url or notification.get_absolute_url()
# #
# #     emailed = []
# #
# #     for recipient in recipient_objects:
# #
# #         user = recipient.recipient
# #
# #         if not user.email:
# #             continue
# #
# #         try:
# #
# #             send_mail(
# #                 subject=title,
# #                 message=f"{message}\n\nView Notification:\n{full_url}",
# #                 from_email=settings.DEFAULT_FROM_EMAIL,
# #                 recipient_list=[user.email],
# #                 fail_silently=False,
# #             )
# #
# #             recipient.email_sent = True
# #             recipient.email_sent_at = timezone.now()
# #
# #             emailed.append(recipient)
# #
# #         except Exception:
# #             # Optionally log the exception here
# #             pass
# #
# #     if emailed:
# #
# #         NotificationRecipient.objects.bulk_update(
# #             emailed,
# #             [
# #                 "email_sent",
# #                 "email_sent_at",
# #             ],
# #         )
# #
# #     return notification
#
#
#
#
# @transaction.atomic
# def send_notification(*, users, title,message, request=None, category=Notification.Category.INFO,
#                       source_app=Notification.Source.CORE, attachment=None, action_url="",):
#     """
#     Creates notification and recipient records.
#
#     This function performs no recipient lookup.
#
#     It assumes users have already been resolved.
#     """
#
#     created_by = None
#
#     if request and request.user.is_authenticated:
#         created_by = request.user
#
#     if users is None:
#         users = []
#
#     elif isinstance(users, Profile):
#         users = [users]
#
#     else:
#         users = list(users)
#
#     notification = Notification.objects.create(
#
#         title=title,
#
#         message=message,
#
#         created_by=created_by,
#
#         category=category,
#
#         source_app=source_app,
#
#         attachment=attachment,
#
#         action_url=action_url,
#
#     )
#
#     NotificationRecipient.objects.bulk_create(
#
#         [
#
#             NotificationRecipient(
#
#                 notification=notification,
#
#                 recipient=user,
#
#             )
#
#             for user in users
#
#         ],
#
#         ignore_conflicts=True,
#
#     )
#
#     return notification
#
#
# @transaction.atomic
# def send_notification(
#     *,
#     title,
#     message,
#     recipients=None,
#     created_by=None,
#     category=Notification.Category.INFO,
#     source_app=Notification.Source.CORE,
#     action_url="",
#     attachment=None,
# ):
#     """
#     Send notification to one or many users.
#
#     recipients:
#         Profile instance
#         list
#         tuple
#         queryset
#     """
#
#     notification = Notification.objects.create(
#         title=title,
#         message=message,
#         created_by=created_by,
#         category=category,
#         source_app=source_app,
#         action_url=action_url,
#         attachment=attachment,
#     )
#
#     if recipients is None:
#         return notification
#
#     if isinstance(recipients, Profile):
#         recipients = [recipients]
#
#     NotificationRecipient.objects.bulk_create(
#
#         [
#
#             NotificationRecipient(
#                 notification=notification,
#                 recipient=user,
#             )
#
#             for user in recipients
#
#         ],
#
#         ignore_conflicts=True,
#
#     )
#
#     return notification
#
#
# def broadcast_notification(
#     *,
#     title,
#     message,
#     created_by=None,
#     category=Notification.Category.INFO,
#     source_app=Notification.Source.CORE,
#     action_url="",
#     attachment=None,
# ):
#
#     recipients = Profile.objects.filter(
#         is_active=True
#     )
#
#     return send_notification(
#
#         title=title,
#
#         message=message,
#
#         recipients=recipients,
#
#         created_by=created_by,
#
#         category=category,
#
#         source_app=source_app,
#
#         action_url=action_url,
#
#         attachment=attachment,
#
#     )
#
#
#
# from django.contrib.auth.models import Group
#
#
# def notify_group(
#
#     group_name,
#
#     **kwargs,
#
# ):
#
#     users = Profile.objects.filter(
#
#         groups__name=group_name,
#
#         is_active=True,
#
#     ).distinct()
#
#     kwargs["recipients"] = users
#
#     return send_notification(**kwargs)
#
#
#
# def notify_staff(**kwargs):
#
#     users = Profile.objects.filter(
#
#         user_profile_type="staff",
#
#         is_active=True,
#
#     )
#
#     kwargs["recipients"] = users
#
#     return send_notification(**kwargs)
#
#
#
# def notify_managers(**kwargs):
#
#     users = Profile.objects.filter(
#
#         is_manager=True,
#
#         is_active=True,
#
#     )
#
#     kwargs["recipients"] = users
#
#     return send_notification(**kwargs)
from email.mime.image import MIMEImage
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from hr_apps.HRapp.utils import logo_path
# from urllib3.contrib.emscripten import request
from account.models import Profile
from .models import Notification, NotificationRecipient

logger = logging.getLogger(__name__)

def _send_html_email(*, subject, to, template, context):
    html = render_to_string(template, context)
    text = strip_tags(html)

    email = EmailMultiAlternatives(subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=to,)

    email.attach_alternative(html, "text/html")

    with open(logo_path, "rb") as f:
        logo = MIMEImage(f.read())

    logo.add_header("Content-ID", "<company_logo>")
    logo.add_header("Content-Disposition", "inline", filename="ricewn.png")

    email.attach(logo)



    try:
        email.send(fail_silently=False)
        logger.info("Email sent successfully to %s", to)
    except Exception:
        logger.exception("Failed to send email to %s", to)
        raise


def _normalize_recipients(recipients):
    """
    Normalize recipients into a unique list of Profile instances.
    """

    if recipients is None:
        return []

    if isinstance(recipients, Profile):
        recipients = [recipients]

    # Evaluate QuerySets / tuples / generators
    recipients = list(recipients)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(recipients))


@transaction.atomic
def send_notification(
    *,
    title,
    message,
    recipients=None,
    created_by=None,
    category=Notification.Category.INFO,
    source_app=Notification.Source.CORE,
    action_url="",
    attachment=None,
):
    """
    Low-level notification creator.

    This function ONLY creates notifications.
    It assumes recipients have already been resolved.
    """

    recipients = _normalize_recipients(recipients)

    notification = Notification.objects.create(
        title=title,
        message=message,
        created_by=created_by,
        category=category,
        source_app=source_app,
        action_url=action_url,
        attachment=attachment,
    )

    if recipients:

        NotificationRecipient.objects.bulk_create(
            [
                NotificationRecipient(
                    notification=notification,
                    recipient=user,
                )
                for user in recipients
            ],
            ignore_conflicts=True,
        )

    return notification


def notify(
    *,
    title,
    message,
    request=None,
    users=None,
    group_name=None,
    broadcast=False,
    category=Notification.Category.INFO,
    source_app=Notification.Source.CORE,
    attachment=None,
    action_url="",
):

    created_by = None

    if request and request.user.is_authenticated:
        created_by = request.user

    if users is not None:

        recipients = users

    elif group_name:

        recipients = Profile.objects.filter(
            groups__name=group_name,
            is_active=True,
        ).distinct()

    elif broadcast:

        recipients = Profile.objects.filter(
            is_active=True
        )

    else:

        recipients = Profile.objects.none()

    return send_notification(
        title=title,
        message=message,
        recipients=recipients,
        created_by=created_by,
        category=category,
        source_app=source_app,
        attachment=attachment,
        action_url=action_url,
    )


def broadcast_notification(**kwargs):

    return notify(
        broadcast=True,
        **kwargs,
    )


def notify_group(group_name, **kwargs):

    return notify(
        group_name=group_name,
        **kwargs,
    )


def notify_staff(**kwargs):

    users = Profile.objects.filter(
        user_profile_type="staff",
        is_active=True,
    )

    return notify(
        users=users,
        **kwargs,
    )


def notify_managers(**kwargs):

    users = Profile.objects.filter(
        is_manager=True,
        is_active=True,
    )

    return notify(
        users=users,
        **kwargs,
    )
