from django.contrib.auth.mixins import LoginRequiredMixin

from .models import NotificationRecipient


class NotificationRecipientMixin(LoginRequiredMixin):


    def get_queryset(self):

        queryset = (

            NotificationRecipient.objects

            .select_related(
                "notification",
                "recipient",
                "notification__created_by",
            )

            .filter(
                is_deleted=False,
                notification__is_deleted=False,
            )

        )

        if self.request.user.is_superuser:
            return queryset.filter(
            recipient=self.request.user
        )

        return queryset.filter(
            recipient=self.request.user
        )