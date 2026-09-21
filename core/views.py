from datetime import date, datetime, timedelta
from decimal import InvalidOperation
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from django.db.models.functions import TruncDay
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from account.templatetags.custom_tags import has_group
from account.utils import MealTeamAccessMixin, meal_team_required, superuser_required
from mne.monitoring.models import Indicator, Location, Output, Project, StrategicObjective

from .forms import LocationForm, ProjectForm, ResourceForm
from .models import CurrencyRate, OrganizationSettings, Resource, SystemActivity
from .services import (
    CURRENCY_LABELS,
    SUPPORTED_CURRENCIES,
    build_currency_matrix,
    get_base_currency,
    get_latest_usd_rates,
    normalize_currency,
    save_manual_usd_rates,
)


def _core_route(request, name):
    namespace = getattr(getattr(request, "resolver_match", None), "namespace", "") or "mne_core"
    if namespace not in {"mne_core", "procurement_core"}:
        namespace = "mne_core"
    return f"{namespace}:{name}"


def approve_object(request, model, pk):
    obj = get_object_or_404(model, pk=pk)
    if hasattr(obj, "approval_status"):
        obj.approval_status = "approved"
    if hasattr(obj, "status") and not getattr(obj, "status", None):
        obj.status = "Approved"
    if hasattr(obj, "approved_by"):
        obj.approved_by = request.user
    if hasattr(obj, "approved_at"):
        obj.approved_at = now()
    if hasattr(obj, "rejection_reason"):
        obj.rejection_reason = None
    if hasattr(obj, "approved"):
        obj.approved = True
    obj.save()
    messages.success(request, f"{obj} approved successfully.")
    return redirect(request.META.get("HTTP_REFERER") or "system_home")


def reject_object(request, model, pk):
    obj = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        if hasattr(obj, "approval_status"):
            obj.approval_status = "rejected"
        if hasattr(obj, "status"):
            obj.status = "Rejected"
        if hasattr(obj, "rejection_reason"):
            obj.rejection_reason = request.POST.get("reason")
        if hasattr(obj, "approved_by"):
            obj.approved_by = request.user
        if hasattr(obj, "approved_at"):
            obj.approved_at = now()
        if hasattr(obj, "approved"):
            obj.approved = False
        obj.save()
        messages.warning(request, f"{obj} rejected.")
        return redirect(request.META.get("HTTP_REFERER") or "system_home")
    return render(request, "governance/reject_modal.html", {"object": obj})


def can_manage_currency(user):
    return user.is_superuser or user.groups.filter(name__in=["Procurement", "Finance", "ED"]).exists()


@login_required
def currency_settings(request):
    if request.method == "POST":
        # Named "settings_action" rather than "action" — an <input name="action">
        # inside a <form> shadows the form element's own .action DOM property,
        # which can break any JS that legitimately reads it.
        action = request.POST.get("settings_action")
        if action == "display_currency":
            currency = normalize_currency(request.POST.get("currency"))
            # Persisted on the user's own profile so the preference survives
            # across sessions and devices, instead of living only in the
            # session (which is what "display_currency" used to mean).
            request.user.display_currency = currency
            request.user.save(update_fields=["display_currency"])
            request.session["display_currency"] = currency
            messages.success(request, "Display currency updated.")
            return redirect(reverse("currency_settings"))

        if action == "base_currency":
            if not request.user.is_superuser:
                messages.error(request, "Only a system administrator can change the organization's base currency.")
                return redirect(reverse("currency_settings"))

            org_settings = OrganizationSettings.load()
            if OrganizationSettings.has_existing_financial_data():
                messages.error(
                    request,
                    "The base currency can't be changed anymore — financial records already exist "
                    "against the current base currency, and changing it now would mix currencies in "
                    "every report. This is a one-time setup choice.",
                )
                return redirect(reverse("currency_settings"))

            new_currency = normalize_currency(request.POST.get("base_currency"))
            org_settings.base_currency = new_currency
            org_settings.updated_by = request.user
            org_settings.save()
            messages.success(request, f"Base currency set to {new_currency}.")
            return redirect(reverse("currency_settings"))

        if action == "manual_rates":
            if not can_manage_currency(request.user):
                messages.error(request, "You do not have permission to update exchange rates.")
                return redirect(reverse("currency_settings"))
            try:
                rate_date = request.POST.get("rate_date")
                rate_date = datetime.strptime(rate_date, "%Y-%m-%d").date() if rate_date else date.today()
                rate_values = {currency: request.POST.get(f"rate_{currency}") for currency in SUPPORTED_CURRENCIES}
                save_manual_usd_rates(rate_values, rate_date, request.user)
            except (ValueError, InvalidOperation, TypeError) as error:
                messages.error(request, f"Exchange rates were not saved: {error}")
            else:
                messages.success(request, f"Exchange rates saved for {rate_date:%Y-%m-%d}.")
            return redirect(reverse("currency_settings"))

    rates = get_latest_usd_rates()
    context = {
        "can_manage_currency": can_manage_currency(request.user),
        "currency_options": [{"code": currency, "label": CURRENCY_LABELS[currency]} for currency in SUPPORTED_CURRENCIES],
        "active_rates": [{"currency": currency, "label": CURRENCY_LABELS[currency], "rate": rates[currency]} for currency in SUPPORTED_CURRENCIES],
        "currency_matrix": build_currency_matrix(rates),
        "today": date.today(),
        "base_currency": get_base_currency(),
        "base_currency_locked": OrganizationSettings.has_existing_financial_data(),
    }
    return render(request, "core/currency_settings.html", context)


@login_required
def set_currency(request):
    if request.method == "POST":
        currency = normalize_currency(request.POST.get("currency"))
        request.user.display_currency = currency
        request.user.save(update_fields=["display_currency"])
        request.session["display_currency"] = currency
        messages.success(request, "Display currency changed.")
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("system_home"))


@login_required
def system_activity_log(request):
    """Daily system activity report available only to ED and superusers."""
    if not (request.user.is_superuser or has_group(request.user, "ED")):
        raise PermissionDenied("Only ED members and superusers may view the system activity log.")

    selected_date = timezone.localdate()
    date_value = request.GET.get("date")
    if date_value:
        try:
            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.localdate()

    activity_queryset = SystemActivity.objects.filter(
        created_at__date=selected_date,
    ).select_related("actor")
    page_obj = Paginator(activity_queryset, 100).get_page(request.GET.get("page"))

    return render(request, "core/system_activity_log.html", {
        "page_obj": page_obj,
        "selected_date": selected_date,
    })


class LocationListView(MealTeamAccessMixin, ListView):
    model = Location
    template_name = "indicators/location_list.html"
    paginate_by = 10
    context_object_name = "location_list"
    ordering = ["district"]


@superuser_required
def create_location(request):
    form = LocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Location created.")
        return redirect(_core_route(request, "location_list"))
    return render(request, "indicators/create_location.html", {"form": form})


@superuser_required
def location_update(request, sub_county, pk):
    location = get_object_or_404(Location, sub_county=sub_county, pk=pk)
    form = LocationForm(request.POST or None, instance=location)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Location updated.")
        return redirect(_core_route(request, "location_list"))
    return render(request, "indicators/create_location.html", {"form": form, "is_update": True, "location": location})


@superuser_required
def trash_location(request, pk, sub_county):
    location = get_object_or_404(Location, pk=pk, sub_county=sub_county)
    if request.method == "POST":
        location.delete()
        messages.success(request, "Location deleted.")
        return redirect(_core_route(request, "location_list"))
    return render(request, "delete_confirmation.html", {"delete": location, "cancel_url": reverse(_core_route(request, "location_list"))})


@meal_team_required()
def resource_list(request):
    resources = Resource.objects.all().order_by("-created_at")
    query = request.GET.get("q")
    resource_type = request.GET.get("type")
    if query:
        resources = resources.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    return render(request, "resources/resource_list.html", {"resources": resources})


@meal_team_required()
def download_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    resource.downloads += 1
    resource.save(update_fields=["downloads"])
    return redirect(resource.file.url)


@meal_team_required()
def resource_upload(request):
    form = ResourceForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        resource = form.save(commit=False)
        resource.uploaded_by = request.user
        resource.save()
        messages.success(request, "Resource uploaded successfully.")
        return redirect(_core_route(request, "resource_list"))
    return render(request, "resources/resource_form.html", {"form": form})


@superuser_required
def resource_delete(request, pk):
    get_object_or_404(Resource, pk=pk).delete()
    messages.success(request, "Resource deleted.")
    return redirect(_core_route(request, "resource_list"))
