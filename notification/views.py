from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
)
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import (
    NotificationCreateForm,
    NotificationUpdateForm,
)
from .helpers import filter_notifications
from .mixins import NotificationRecipientMixin
from .models import Notification, NotificationRecipient


class NotificationAdminMixin(UserPassesTestMixin):

    """
    Only superusers can create/update notifications.
    """

    def test_func(self):
        return self.request.user.is_superuser


class NotificationListView(NotificationRecipientMixin, ListView):

    model = NotificationRecipient

    template_name = "notifications/list.html"

    context_object_name = "notifications"

    paginate_by = 20

    def get_queryset(self):

        queryset = super().get_queryset()

        queryset = filter_notifications(
            queryset,
            self.request,
        )

        return queryset

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        queryset = self.get_queryset()

        context["unread_count"] = queryset.filter(
            is_read=False
        ).count()

        context["total_notifications"] = queryset.count()

        context["read_count"] = queryset.filter(
            is_read=True
        ).count()

        context["critical_count"] = queryset.filter(
            notification__category=Notification.Category.CRITICAL
        ).count()

        return context


class NotificationDetailView(NotificationRecipientMixin, DetailView):

    model = NotificationRecipient
    context_object_name = "notification"
    template_name = "notifications/detail.html"

    def get_object(self, queryset=None):
        queryset = self.get_queryset().filter(notification__pk=self.kwargs["pk"])
        obj = get_object_or_404(queryset)

        obj.mark_as_read()

        return obj


class NotificationCreateView(NotificationAdminMixin,LoginRequiredMixin,CreateView,):

    model = Notification

    form_class = NotificationCreateForm

    template_name = "notifications/form.html"

    success_url = reverse_lazy("notifications:list")

    def form_valid(self, form):

        form.save(
            created_by=self.request.user
        )

        messages.success(
            self.request,
            "Notification sent successfully."
        )

        return redirect(self.success_url)


class NotificationUpdateView(NotificationAdminMixin, LoginRequiredMixin, UpdateView,):
    model = Notification
    form_class = NotificationUpdateForm
    template_name = "notifications/update.html"
    success_url = reverse_lazy("notifications:list")

    def get_queryset(self):
        queryset = super().get_queryset()

        # Only allow the creator to access the object
        return queryset.filter(created_by=self.request.user)

    def form_valid(self, form):
        messages.success(
            self.request,
            "Notification updated successfully."
        )
        return super().form_valid(form)


def notification_delete(request, pk):

    if not request.user.is_superuser:

        messages.error(
            request,
            "Permission denied."
        )

        return redirect("notifications:list")

    notification = get_object_or_404(
        Notification,
        pk=pk,
        is_deleted=False,
    )

    notification.is_deleted = True

    notification.save(
        update_fields=["is_deleted"]
    )

    messages.success(
        request,
        "Notification deleted."
    )

    return redirect("notifications:list")


def mark_notification_read(request, pk):
    recipient = get_object_or_404(NotificationRecipient,notification__pk=pk,recipient=request.user,is_deleted=False,)
    recipient.mark_as_read()
    return redirect(recipient.notification.get_absolute_url())


def mark_all_as_read(request):
    NotificationRecipient.objects.filter(recipient=request.user, is_read=False, is_deleted=False,
                                         ).update(is_read=True,read_at=timezone.now(),)
    messages.success(request, "All notifications marked as read.")
    return redirect("notifications:list")


class NotificationDashboardView(LoginRequiredMixin, ListView):

    template_name = "notifications/dashboard.html"

    model = NotificationRecipient

    context_object_name = "notifications"

    paginate_by = 10

    def get_queryset(self):

        return (

            NotificationRecipient.objects

            .select_related("notification")

            .filter(

                recipient=self.request.user,

                is_deleted=False,

            )[:10]

        )

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        qs = NotificationRecipient.objects.filter(

            recipient=self.request.user,

            is_deleted=False,

        )

        context["total"] = qs.count()

        context["unread"] = qs.filter(

            is_read=False

        ).count()

        return context