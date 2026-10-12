import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, View

from .forms import MinutesUploadForm, StaffEventForm
from .models import StaffEvent
from .services import communication_member, create_event_and_invite, staff_recipients


class CommunicationRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return communication_member(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "Only Communication group members can manage staff events.")
        return redirect("comm:staff_events:list")


class StaffEventListView(LoginRequiredMixin, ListView):
    model = StaffEvent
    template_name = "staff_events/event_list.html"
    context_object_name = "events"

    def get_queryset(self):
        return StaffEvent.objects.all().order_by("starts_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        try:
            year, month = (int(value) for value in self.request.GET.get("month", "").split("-"))
            if not 1 <= month <= 12:
                raise ValueError
        except (TypeError, ValueError):
            year, month = today.year, today.month

        events_by_date = {}
        for event in context["events"]:
            event_date = timezone.localtime(event.starts_at).date()
            events_by_date.setdefault(event_date, []).append(event)

        calendar_months = []
        for offset in range(4):
            month_index = month - 1 + offset
            calendar_year = year + month_index // 12
            calendar_month = month_index % 12 + 1
            weeks = []
            for week in calendar.Calendar(firstweekday=6).monthdatescalendar(calendar_year, calendar_month):
                weeks.append([
                    {
                        "date": cell_date,
                        "events": events_by_date.get(cell_date, []),
                        "in_month": cell_date.month == calendar_month,
                        "status": "current" if cell_date == today else ("past" if cell_date < today else "future"),
                    }
                    for cell_date in week
                ])
            calendar_months.append({
                "title": date(calendar_year, calendar_month, 1).strftime("%B %Y"),
                "weeks": weeks,
            })

        previous_index = year * 12 + month - 1 - 4
        next_index = year * 12 + month - 1 + 4
        context.update({
            "calendar_months": calendar_months,
            "weekdays": ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
            "calendar_previous": f"{previous_index // 12:04d}-{previous_index % 12 + 1:02d}",
            "calendar_next": f"{next_index // 12:04d}-{next_index % 12 + 1:02d}",
            "calendar_today": today,
            "can_manage_events": communication_member(self.request.user),
        })
        return context


class StaffEventDetailView(LoginRequiredMixin, DetailView):
    model = StaffEvent
    template_name = "staff_events/event_detail.html"
    context_object_name = "event"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = MinutesUploadForm() if communication_member(self.request.user) else None
        context["can_manage_events"] = communication_member(self.request.user)
        return context


class StaffEventCreateView(LoginRequiredMixin, CommunicationRequiredMixin, CreateView):
    model = StaffEvent
    form_class = StaffEventForm
    template_name = "staff_events/event_form.html"
    success_url = reverse_lazy("comm:staff_events:list")

    def form_valid(self, form):
        event = form.save(commit=False)
        event.created_by = self.request.user
        create_event_and_invite(event=event, recipients=staff_recipients())
        messages.success(self.request, "Event created and calendar invitations sent to staff with email addresses.")
        return redirect("comm:staff_events:detail", pk=event.pk)


class StaffEventMinutesView(LoginRequiredMixin, CommunicationRequiredMixin, View):
    def post(self, request, pk):
        event = get_object_or_404(StaffEvent, pk=pk)
        form = MinutesUploadForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            event = form.save(commit=False)
            event.minutes_uploaded_at = timezone.now()
            event.save()
            messages.success(request, "Meeting minutes uploaded successfully.")
        else:
            messages.error(request, "; ".join(sum(form.errors.values(), [])))
        return redirect("comm:staff_events:detail", pk=pk)
