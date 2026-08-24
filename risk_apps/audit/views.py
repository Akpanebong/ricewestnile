from django.contrib import messages
from django.utils import timezone
from django.utils.timezone import now
from django.views.generic import ListView, TemplateView
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, DeleteView, DetailView
from django.shortcuts import redirect, render, get_object_or_404

from core.views import reject_object, approve_object
from .formsets_mixin import AuditFormsetMixin
from .models import *
from .forms import *


class AuditDashboardView(TemplateView):
    template_name = "audit/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context.update({
            "audit_count": AuditLog.objects.count(),
            "active_audits": AuditLog.objects.exclude(status="closed").count(),
            "open_findings": AuditFinding.objects.exclude(status="closed").count(),
            "evidence_count": AuditEvidence.objects.count(),
            "external_audit_count": ExternalAuditEngagement.objects.count(),
            "overdue_findings": AuditFinding.objects.filter(due_date__lt=today).exclude(status="closed"),
            "recent_audits": AuditLog.objects.all()[:10],
            "recent_external_audits": ExternalAuditEngagement.objects.all()[:5],
        })
        return context


class AuditLogListView(ListView):
    model = AuditLog
    template_name = "audit/audit_list.html"
    context_object_name = "audits"


class AuditLogCreateView(AuditFormsetMixin, CreateView):
    model = AuditLog
    form_class = AuditLogForm
    template_name = "audit/audit_form.html"
    success_url = reverse_lazy("audit_log_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            self.get_formsets(
                instance=None,
                post_data=self.request.POST if self.request.POST else None
            )
        )
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Successfully created an audit log')
        context = self.get_context_data()

        if not self.save_formsets(form, context):
            return self.form_invalid(form)

        return super().form_valid(form)   # ✅ ONLY RESPONSE RETURNED


class AuditLogUpdateView(AuditFormsetMixin, UpdateView):
    model = AuditLog
    form_class = AuditLogForm
    template_name = "audit/audit_form.html"
    # success_url = reverse_lazy("audit_log_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            self.get_formsets(
                instance=self.object,
                post_data=self.request.POST if self.request.POST else None
            )
        )
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Successfully updated an audit log')
        context = self.get_context_data()

        if not self.save_formsets(form, context):
            return self.form_invalid(form)

        return super().form_valid(form)   # ✅ CRITICAL FIX

    def get_success_url(self):
        return reverse_lazy("audit_log_detail", kwargs={'pk': self.object.pk})


class AuditLogDetailView(DetailView):
    model = AuditLog
    template_name = "audit/audit_detail.html"
    context_object_name = "audit"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = now().date()
        return context


def audit_log_delete(request, pk):
    obj = get_object_or_404(AuditLog, pk=pk)
    finding = AuditFinding.objects.filter(audit=obj)
    evidence = AuditEvidence.objects.filter(audit=obj)
    combine = list(finding) + list(evidence)

    if request.method == "POST":
        obj.delete()
        finding.delete()
        evidence.delete()
        messages.success(request, f"{obj} and its related objects are deleted successfully")
        return redirect("audit_log_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("audit_log_detail", kwargs={'pk': obj.pk}),
        "obj": combine
    })


def reject_auditlog(request, pk):
    return reject_object(request, AuditLog, pk)


def approve_auditlog(request, pk):
    return approve_object(request, AuditLog, pk)


class AuditFindingListView(ListView):
    model = AuditFinding
    template_name = "audit/finding_list.html"
    context_object_name = "findings"


class AuditFindingUpdateView(UpdateView):
    model = AuditFinding
    form_class = AuditFindingForm
    template_name = "audit/form.html"
    # success_url = reverse_lazy("audit_finding_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['delete_url'] = reverse_lazy("finding_delete", kwargs={'pk': self.object.pk})
        return context

    def get_success_url(self):
        return reverse_lazy("audit_finding_list")


def audit_finding_delete(request, pk):
    obj = get_object_or_404(AuditFinding, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("audit_finding_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("audit_log_detail", kwargs={'pk': obj.audit.pk})
    })


class AuditEvidenceListView(ListView):
    model = AuditEvidence
    template_name = "audit/evidence_list.html"
    context_object_name = "evidence_items"


class AuditEvidenceUpdateView(UpdateView):
    model = AuditEvidence
    form_class = AuditEvidenceForm
    template_name = "audit/form.html"
    # success_url = reverse_lazy("audit_evidence_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context['delete_url'] = reverse_lazy("evidence_delete", kwargs={'pk': self.object.pk})
        return context

    def get_success_url(self):
        return reverse_lazy("audit_evidence_list")


def audit_evidence_delete(request, pk):
    obj = get_object_or_404(AuditEvidence, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("audit_evidence_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("audit_log_detail", kwargs={'pk': obj.audit.pk})
    })


class ExternalAuditDashboardView(TemplateView):
    template_name = "audit/external_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "engagement_count": ExternalAuditEngagement.objects.count(),
            "open_external_findings": ExternalAuditFinding.objects.exclude(status="closed").count(),
            "mapped_findings": ExternalAuditFinding.objects.exclude(mapped_reference="").count(),
            "engagements": ExternalAuditEngagement.objects.all()[:10],
        })
        return context


class ExternalAuditEngagementListView(ListView):
    model = ExternalAuditEngagement
    template_name = "audit/external_engagement_list.html"
    context_object_name = "engagements"


class ExternalAuditEngagementDetailView(DetailView):
    model = ExternalAuditEngagement
    template_name = "audit/external_engagement_detail.html"
    context_object_name = "engagement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        engagement = self.object

        # Prefetch related findings
        context["findings"] = engagement.findings.select_related(
            "related_internal_finding", "related_risk"
        )

        # Metrics
        context["total_findings"] = context["findings"].count()
        context["open_findings"] = context["findings"].filter(status="open").count()
        context["closed_findings"] = context["findings"].filter(status="closed").count()

        return context


def reject_external_audit(request, pk):
    return reject_object(request, ExternalAuditEngagement, pk)


def approve_external_audit(request, pk):
    return approve_object(request, ExternalAuditEngagement, pk)


class ExternalAuditFindingListView(ListView):
    model = ExternalAuditFinding
    template_name = "audit/external_finding_list.html"
    context_object_name = "findings"


class ExternalAuditCreateView(CreateView):
    model = ExternalAuditEngagement
    form_class = ExternalAuditEngagementForm
    template_name = "audit/external_form.html"
    success_url = reverse_lazy("external_audit_engagement_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["formset"] = ExternalFindingFormSet(self.request.POST)
        else:
            context["formset"] = ExternalFindingFormSet()

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        # ✅ Set created_by for parent
        form.instance.created_by = self.request.user

        if formset.is_valid():
            self.object = form.save()

            formset.instance = self.object

            findings = formset.save(commit=False)

            for f in findings:
                f.created_by = self.request.user  # ✅ Set for formset
                f.engagement = self.object
                f.save()

            formset.save_m2m()

            messages.success(self.request, "External audit engagement created successfully")
            return redirect(self.success_url)

        return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))


class ExternalAuditUpdateView(UpdateView):
    model = ExternalAuditEngagement
    form_class = ExternalAuditEngagementForm
    template_name = "audit/external_form.html"
    # success_url = reverse_lazy("external_audit_detail")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["formset"] = ExternalFindingFormSet(
                self.request.POST,
                instance=self.object
            )
        else:
            context["formset"] = ExternalFindingFormSet(instance=self.object)

        context["is_update"] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]

        if formset.is_valid():
            self.object = form.save()

            findings = formset.save(commit=False)

            for f in findings:
                if not f.created_by:
                    f.created_by = self.request.user  # only set if new
                f.engagement = self.object
                f.save()

            # Handle deleted objects
            for obj in formset.deleted_objects:
                obj.delete()

            formset.save_m2m()

            messages.success(self.request, "External audit updated successfully")
            return redirect(reverse_lazy('external_audit_detail', kwargs={'pk': self.object.pk}))

        return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, f"Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))


def ext_audit_delete(request, pk):
    obj = get_object_or_404(ExternalAuditEngagement, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("external_audit_engagement_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("external_audit_detail", kwargs={'pk': obj.pk})
    })
