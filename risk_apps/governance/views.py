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
from .forms import *


class GovernanceDashboardView(TemplateView):
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


class PolicyListView(ListView):
    model = Policy
    template_name = "governance/policy_list.html"
    context_object_name = "policies"


class PolicyDetail(DetailView):
    model = Policy
    template_name = "governance/policy_detail.html"
    # context_object_name = "risk"


class PolicyCreateView(CreateView):
    model = Policy
    form_class = PolicyForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("policy_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Policy created successfully")
        return super().form_valid(form)


class PolicyUpdateView(UpdateView):
    model = Policy
    form_class = PolicyForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("policy_list")

    def form_valid(self, form):
        messages.success(self.request, "Policy updated successfully")
        return super().form_valid(form)


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


class ControlListView(ListView):
    model = Control
    template_name = "governance/control_list.html"
    context_object_name = "controls"


class ControlDetail(DetailView):
    model = Control
    template_name = "governance/control_detail.html"


class ControlCreateView(CreateView):
    model = Control
    form_class = ControlForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("control_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Control created successfully")
        return super().form_valid(form)


class ControlUpdateView(UpdateView):
    model = Control
    form_class = ControlForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("control_list")


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


class DecisionRecordListView(ListView):
    model = DecisionRecord
    template_name = "governance/decision_list.html"
    context_object_name = "decisions"


class DecisionRecordDetail(DetailView):
    model = DecisionRecord
    template_name = "governance/decision_detail.html"


class DecisionCreateView(CreateView):
    model = DecisionRecord
    form_class = DecisionRecordForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("decision_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Decision created successfully")
        return super().form_valid(form)


class DecisionUpdateView(UpdateView):
    model = DecisionRecord
    form_class = DecisionRecordForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("decision_list")


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


class StakeholderEngagementListView(ListView):
    model = StakeholderEngagement
    template_name = "governance/engagement_list.html"
    context_object_name = "engagements"


class StakeholderEngagementDetail(DetailView):
    model = StakeholderEngagement
    template_name = "governance/stakeholder_detail.html"


class StakeholderCreateView(CreateView):
    model = StakeholderEngagement
    form_class = StakeholderEngagementForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("engagement_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Stakeholder created successfully")
        return super().form_valid(form)


class StakeholderUpdateView(UpdateView):
    model = StakeholderEngagement
    form_class = StakeholderEngagementForm
    template_name = "governance/form.html"
    success_url = reverse_lazy("engagement_list")


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


def approve_policy(request, pk):
    return approve_object(request, Policy, pk)


def reject_policy(request, pk):
    return reject_object(request, Policy, pk)


def approve_control(request, pk):
    return approve_object(request, Control, pk)


def reject_control(request, pk):
    return reject_object(request, Control, pk)


def approve_decision(request, pk):
    return approve_object(request, DecisionRecord, pk)


def reject_decision(request, pk):
    return reject_object(request, DecisionRecord, pk)
