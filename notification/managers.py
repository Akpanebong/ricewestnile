from django.db import models


class NotificationManager(models.Manager):

    def active(self):
        return self.filter(is_deleted=False)

    def create_notification(self, recipients=None, **kwargs):
        """
        Creates a notification and recipient records.

        recipients may be:
            User instance
            list
            tuple
            queryset
        """

        notification = self.create(**kwargs)

        if not recipients:
            return notification

        if isinstance(recipients, models.QuerySet):
            recipients = list(recipients)

        if isinstance(recipients, (list, tuple, set)):

            NotificationRecipient = self.model.recipient_model()

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

        else:

            NotificationRecipient = self.model.recipient_model()

            NotificationRecipient.objects.get_or_create(
                notification=notification,
                recipient=recipients,
            )

        return notification