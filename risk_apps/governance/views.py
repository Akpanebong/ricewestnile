from django.db.models import Count
from django.views.generic import ListView, TemplateView, DetailView
from django.utils import timezone

from core.views import reject_object, approve_object
from .models import Control, DecisionRecord, Policy, StakeholderEngagement
from django.views.generic import CreateView, UpdateView
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .forms import *


def _is_governance_user(user):
    return bool(
        user and user.is_authenticated and (
            user.is_superuser
            or user.groups.filter(name__iexact="ED").exists()
            or user.groups.filter(name__iexact="Governance").exists()
        )
    )


def _is_governance_manager(user):
    return bool(
        user and user.is_authenticated and (
            user.is_superuser or user.groups.filter(name__iexact="ED").exists()
        )
    )


class GovernanceAccessMixin:
    """Governance is a standalone module for ED and Governance members."""
    def dispatch(self, request, *args, **kwargs):
        if not _is_governance_user(request.user):
            raise PermissionDenied("Only ED and Governance group members may access Governance.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["governance_can_manage"] = _is_governance_manager(self.request.user)
        context["governance_can_create"] = _is_governance_user(self.request.user)
        return context


class GovernanceCreateMixin(GovernanceAccessMixin):
    pass


class GovernanceManageMixin(GovernanceAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not _is_governance_manager(request.user):
            raise PermissionDenied("Only ED members and superusers may modify Governance records.")
        return super().dispatch(request, *args, **kwargs)


def manager_required(view):
    def wrapped(request, *args, **kwargs):
        if not _is_governance_manager(request.user):
            raise PermissionDenied("Only ED members and superusers may modify Governance records.")
        return view(request, *args, **kwargs)
    return wrapped


class GovernanceDashboardView(GovernanceAccessMixin, TemplateView):
    template_name = "governance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context.update({
            "policy_count": Policy.objects.count(),
            "active_policies": Policy.objects.filter(status__in=["active", "approved"]).count(),
            "pending_approvals": Policy.objects.filter(approval_status="pending").count(),
            "control_count": Control.objects.count(),
            "decision_count": DecisionRecord.objects.count(),
            "engagement_count": StakeholderEngagement.objects.count(),
            "weak_controls": Control.objects.filter(effectiveness__in=["needs_improvement", "ineffective"])[:10],
            "upcoming_reviews": Policy.objects.filter(next_review_date__gte=today).order_by("next_review_date")[:10],
            "recent_decisions": DecisionRecord.objects.all()[:5],
            "engagement_summary": StakeholderEngagement.objects.values("status").annotate(total=Count("id")).order_by("status"),
        })
        return context


class PolicyListView(GovernanceAccessMixin, ListView):
    model = Policy
    template_name = "governance/policy_list.html"
    context_object_name = "policies"
    paginate_by = 25


class PolicyDetail(GovernanceAccessMixin, DetailView):
    model = Policy
    template_name = "governance/policy_detail.html"
    # context_object_name = "risk"


class PolicyCreateView(GovernanceCreateMixin, CreateView):
    model = Policy
    form_class = PolicyForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("policy_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Policy created successfully")
        return super().form_valid(form)


class PolicyUpdateView(GovernanceManageMixin, UpdateView):
    model = Policy
    form_class = PolicyForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("policy_list")

    def form_valid(self, form):
        messages.success(self.request, "Policy updated successfully")
        return super().form_valid(form)


@manager_required
def policy_delete(request, pk):
    obj = get_object_or_404(Policy, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Policy deleted successfully")
        return redirect("policy_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("policy_detail", kwargs={'pk': obj.pk})
    })


class ControlListView(GovernanceAccessMixin, ListView):
    model = Control
    template_name = "governance/control_list.html"
    context_object_name = "controls"
    paginate_by = 25


class ControlDetail(GovernanceAccessMixin, DetailView):
    model = Control
    template_name = "governance/control_detail.html"


class ControlCreateView(GovernanceCreateMixin, CreateView):
    model = Control
    form_class = ControlForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("control_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Control created successfully")
        return super().form_valid(form)


class ControlUpdateView(GovernanceManageMixin, UpdateView):
    model = Control
    form_class = ControlForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("control_list")


@manager_required
def control_delete(request, pk):
    obj = get_object_or_404(Control, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Control deleted successfully")
        return redirect("control_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("control_detail", kwargs={'pk': obj.pk})
    })


class DecisionRecordListView(GovernanceAccessMixin, ListView):
    model = DecisionRecord
    template_name = "governance/decision_list.html"
    context_object_name = "decisions"
    paginate_by = 25


class DecisionRecordDetail(GovernanceAccessMixin, DetailView):
    model = DecisionRecord
    template_name = "governance/decision_detail.html"


class DecisionCreateView(GovernanceCreateMixin, CreateView):
    model = DecisionRecord
    form_class = DecisionRecordForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("decision_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Decision created successfully")
        return super().form_valid(form)


class DecisionUpdateView(GovernanceManageMixin, UpdateView):
    model = DecisionRecord
    form_class = DecisionRecordForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("decision_list")


@manager_required
def decision_delete(request, pk):
    obj = get_object_or_404(DecisionRecord, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Decision deleted successfully")
        return redirect("decision_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("decision_detail", kwargs={'pk': obj.pk})
    })


class StakeholderEngagementListView(GovernanceAccessMixin, ListView):
    model = StakeholderEngagement
    template_name = "governance/engagement_list.html"
    context_object_name = "engagements"
    paginate_by = 25


class StakeholderEngagementDetail(GovernanceAccessMixin, DetailView):
    model = StakeholderEngagement
    template_name = "governance/stakeholder_detail.html"


class StakeholderCreateView(GovernanceCreateMixin, CreateView):
    model = StakeholderEngagement
    form_class = StakeholderEngagementForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("engagement_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Stakeholder created successfully")
        return super().form_valid(form)


class StakeholderUpdateView(GovernanceManageMixin, UpdateView):
    model = StakeholderEngagement
    form_class = StakeholderEngagementForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("engagement_list")


@manager_required
def stakeholder_delete(request, pk):
    obj = get_object_or_404(StakeholderEngagement, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, "Record deleted successfully")
        return redirect("engagement_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("stakeholder_detail", kwargs={'pk': obj.pk})
    })


@manager_required
def approve_policy(request, pk):
    return approve_object(request, Policy, pk)


@manager_required
def reject_policy(request, pk):
    return reject_object(request, Policy, pk)


@manager_required
def approve_control(request, pk):
    return approve_object(request, Control, pk)


@manager_required
def reject_control(request, pk):
    return reject_object(request, Control, pk)


@manager_required
def approve_decision(request, pk):
    return approve_object(request, DecisionRecord, pk)


@manager_required
def reject_decision(request, pk):
    return reject_object(request, DecisionRecord, pk)
