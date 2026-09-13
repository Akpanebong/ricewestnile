from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.views.generic import TemplateView, ListView, DetailView, DeleteView, UpdateView, CreateView
from django.db.models import Avg
from datetime import datetime

from notification.utils import send_notification, notify
from .forms import ComplianceFrameworkForm, PartnerDueDiligenceForm, VendorDueDiligenceForm, ComplianceAssessmentForm, \
    ComplianceDocumentFormSet, ComplianceRequirementForm
from .models import *
from .utils import process_all_tasks, get_alerts, detect_compliance_gaps, compliance_score
from .forms import ComplianceTaskForm
from risk_apps.risk.utils import generate_pdf
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction


class SuccessMessageMixin:
    success_message = ""

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class ComplianceDashboardView(TemplateView):
    template_name = "compliance/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        alerts = get_alerts()
        gaps = detect_compliance_gaps()

        avg_score = ComplianceAssessment.objects.aggregate(
            avg=Avg('score')
        )["avg"] or 0

        context.update({
            "total_requirements": ComplianceRequirement.objects.count(),
            "total_tasks": ComplianceTask.objects.count(),
            "partner_count": PartnerDueDiligence.objects.count(),
            "vendor_count": VendorDueDiligence.objects.count(),

            "overdue_count": alerts["overdue"].count(),
            "upcoming_count": alerts["upcoming"].count(),
            "completed_count": alerts["completed"].count(),

            "avg_score": avg_score,
            "gaps": gaps,

            # expose lists (important for UI)
            "overdue_tasks": alerts["overdue"][:5],
            "upcoming_tasks": alerts["upcoming"][:5],
            "partner_watchlist": PartnerDueDiligence.objects.filter(risk_rating__in=["high", "critical"])[:5],
            "vendor_watchlist": VendorDueDiligence.objects.filter(risk_rating__in=["high", "critical"])[:5],
        })

        return context


class ComplianceFrameworkCreate(SuccessMessageMixin, CreateView):
    model = ComplianceFramework
    form_class = ComplianceFrameworkForm
    template_name = "compliance/form.html"
    success_url = reverse_lazy("framework")
    # success_message = "Framework created successfully"

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        messages.success(self.request, "Framework created successfully")
        return super().form_valid(form)


class ComplianceFrameworkView(ListView):
    model = ComplianceFramework
    template_name = "compliance/framework_list.html"
    context_object_name = "frames"


class ComplianceFrameworkDetailView(View):
    template_name = "compliance/framework_detail.html"

    def get(self, request, pk):
        framework = get_object_or_404(ComplianceFramework, id=pk)
        requirements = ComplianceRequirement.objects.filter(framework=framework)

        context = {
            "framework": framework,
            "requirements": requirements,
        }
        return render(request, self.template_name, context)


class ComplianceFrameworkUpdate(SuccessMessageMixin, UpdateView):
    model = ComplianceFramework
    form_class = ComplianceFrameworkForm
    template_name = "compliance/form.html"
    success_url = reverse_lazy("framework")
    success_message = "Framework updated successfully"


def compliance_frame_delete(request, pk):
    obj = get_object_or_404(ComplianceFramework, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("framework")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("framework_detail", kwargs={'pk': obj.pk})
    })


class ComplianceRequirementView(ListView):
    model = ComplianceRequirement
    template_name = "compliance/comp_requirement.html"
    context_object_name = "requirements"


class ComplianceRequirementCreateView(View):
    template_name = "compliance/requirement_form.html"

    def get(self, request, framework_id):
        framework = get_object_or_404(ComplianceFramework, id=framework_id)

        form = ComplianceRequirementForm()
        formset = ComplianceDocumentFormSet()

        return render(request, self.template_name, {
            "framework": framework,
            "form": form,
            "formset": formset
        })

    def post(self, request, framework_id):
        framework = get_object_or_404(ComplianceFramework, id=framework_id)

        form = ComplianceRequirementForm(request.POST)
        formset = ComplianceDocumentFormSet(request.POST, request.FILES)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    requirement = form.save(commit=False)
                    requirement.framework = framework

                    if request.user.is_authenticated:
                        requirement.created_by = request.user

                    requirement.save()

                    formset.instance = requirement
                    formset.save()

                    notify(
                        title=form.cleaned_data['title'] or "New Compliance Requirement",
                        message="A new requirement has been created.",
                        request=request,
                        #users=Profile.objects.filter(department__name="Finance"),
                        # for other dept aside from GARCIS include this user line
                    )

                messages.success(request, "Requirement and documents saved successfully")
                return redirect("framework_detail", pk=framework.id)

            except Exception as e:
                messages.error(request, str(e))

        return render(request, self.template_name, {
            "framework": framework,
            "form": form,
            "formset": formset
        })


class ComplianceDetailView(DetailView):
    model = ComplianceRequirement
    template_name = "compliance/requirement_detail.html"
    context_object_name = "req"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tasks"] = self.object.tasks.all()
        context["documents"] = self.object.documents.all()
        context["assessments"] = self.object.complianceassessment_set.all()
        context["completed_tasks"] = self.object.tasks.filter(status="completed").count()
        # ✅ ADD THIS HERE
        context["latest_assessment"] = (
            self.object.complianceassessment_set
            .order_by("-assessed_at")
            .first()
        )

        return context


def compliance_requirement_delete(request, pk):
    obj = get_object_or_404(ComplianceRequirement, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("compliance_register")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("compliance_detail", kwargs={'pk': obj.pk})
    })


class ComplianceCalendarView(TemplateView):
    template_name = "compliance/calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tasks = ComplianceTask.objects.select_related("requirement").all()

        context["tasks"] = tasks  # ✅ for fallback rendering

        context["tasks_json"] = [
            {
                "title": t.requirement.title,
                "date": t.due_date.strftime("%Y-%m-%d"),
                "status": t.status
            }
            for t in tasks
        ]

        return context


class ComplianceTaskCreateView(View):
    template_name = "compliance/task_form.html"

    def get(self, request, requirement_id):
        requirement = get_object_or_404(ComplianceRequirement, id=requirement_id)

        context = {
            "requirement": requirement,
            "statuses": ComplianceTask.STATUS_CHOICES,
            "priorities": ComplianceTask.PRIORITY_CHOICES,
        }
        return render(request, self.template_name, context)

    def post(self, request, requirement_id):
        requirement = get_object_or_404(ComplianceRequirement, id=requirement_id)

        task = ComplianceTask.objects.create(
            requirement=requirement,
            due_date=datetime.strptime(request.POST.get("due_date"), "%Y-%m-%d").date(),
            responsible=request.POST.get("responsible"),
            status=request.POST.get("status"),
            priority=request.POST.get("priority"),
            progress=request.POST.get("progress") or 0,
        )

        return redirect("task_detail", pk=task.id)


class ComplianceTaskUpdateView(View):
    template_name = "compliance/task_form.html"

    def get(self, request, pk):
        task = get_object_or_404(ComplianceTask, id=pk)
        form = ComplianceTaskForm(instance=task)

        return render(request, self.template_name, {
            "form": form,
            "task": task,
            "statuses": ComplianceTask.STATUS_CHOICES,
            "priorities": ComplianceTask.PRIORITY_CHOICES,
        })

    def post(self, request, pk):
        task = get_object_or_404(ComplianceTask, id=pk)
        form = ComplianceTaskForm(request.POST, instance=task)

        if form.is_valid():
            form.save()
            return redirect("task_detail", pk=task.id)

        return render(request, self.template_name, {"form": form})


class ComplianceTaskDetailView(View):
    template_name = "compliance/task_detail.html"

    def get(self, request, pk):
        task = get_object_or_404(
            ComplianceTask.objects.select_related("requirement", "requirement__framework"),
            id=pk
        )

        context = {
            "task": task,
        }
        return render(request, self.template_name, context)


def compliance_task_delete(request, pk):
    obj = get_object_or_404(ComplianceTask, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("compliance_calendar")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("task_detail", kwargs={'pk': obj.pk})
    })


class ComplianceReportView(TemplateView):
    template_name = "compliance/report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data = []

        for req in ComplianceRequirement.objects.all():
            tasks = req.tasks.all()
            docs = req.documents.filter(is_verified=True)

            data.append({
                "req": req,
                "tasks": tasks,
                "verified_docs": docs,
                "score": sum(a.score for a in req.complianceassessment_set.all()) / (req.complianceassessment_set.count() or 1)
            })

        context["report_data"] = data
        return context


class ComplianceAssessmentView(ListView):
    model = ComplianceAssessment
    template_name = "compliance/assessment.html"
    context_object_name = "assessments"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["avg_score"] = ComplianceAssessment.objects.aggregate(
            avg=Avg('score')
        )["avg"] or 0

        return context


class ComplianceAssessmentCreateView(SuccessMessageMixin, View):
    template_name = "compliance/assessment_form.html"

    def get(self, request, requirement_id):
        requirement = get_object_or_404(ComplianceRequirement, id=requirement_id)
        form = ComplianceAssessmentForm()

        return render(request, self.template_name, {
            "form": form,
            "requirement": requirement
        })

    def post(self, request, requirement_id):
        requirement = get_object_or_404(ComplianceRequirement, id=requirement_id)
        form = ComplianceAssessmentForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.requirement = requirement
            obj.save()
            return redirect("compliance_detail", pk=requirement.id)

        return render(request, self.template_name, {"form": form})


class ComplianceAssessmentUpdateView(View):
    template_name = "compliance/assessment_form.html"

    def get(self, request, pk):
        obj = get_object_or_404(ComplianceAssessment, id=pk)
        form = ComplianceAssessmentForm(instance=obj)

        return render(request, self.template_name, {
            "form": form,
            "assessment": obj,
            "requirement": obj.requirement
        })

    def post(self, request, pk):
        obj = get_object_or_404(ComplianceAssessment, id=pk)
        form = ComplianceAssessmentForm(request.POST, instance=obj)

        if form.is_valid():
            form.save()
            return redirect("compliance_assessment")

        return render(request, self.template_name, {"form": form})


def compliance_assessment_delete(request, pk):
    obj = get_object_or_404(ComplianceAssessment, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("compliance_assessment")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("compliance_assessment")
    })


class PartnerDueDiligenceListView(ListView):
    model = PartnerDueDiligence
    template_name = "compliance/partner_list.html"
    context_object_name = "partners"


class PartnerCreate(CreateView):
    model = PartnerDueDiligence
    form_class = PartnerDueDiligenceForm
    template_name = "compliance/form.html"
    success_url = reverse_lazy("partner_due_diligence_list")


class PartnerDetail(DetailView):
    model = PartnerDueDiligence
    template_name = "compliance/partner_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = now().date()
        return context


class PartnerUpdate(SuccessMessageMixin, UpdateView):
    model = PartnerDueDiligence
    form_class = PartnerDueDiligenceForm
    template_name = "compliance/form.html"
    # success_url = reverse_lazy("partner_detail", kwargs={''})

    def post(self, request, pk):
        task = get_object_or_404(PartnerDueDiligence, id=pk)
        form = PartnerDueDiligenceForm(request.POST, instance=task)

        if form.is_valid():
            form.save()
            messages.success(request, f'Successfully updated {task}')
            return redirect("partner_detail", pk=task.id)

        return render(request, self.template_name, {"form": form})


def partner_delete(request, pk):
    obj = get_object_or_404(PartnerDueDiligence, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("partner_due_diligence_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("partner_detail", kwargs={'pk': obj.pk})
    })


def approve_partner(request, pk):
    obj = get_object_or_404(PartnerDueDiligence, pk=pk)
    obj.status = "approved"
    obj.save()
    messages.success(request, "Partner approved")
    return redirect("partner_detail", pk=pk)


def reject_partner(request, pk):
    obj = get_object_or_404(PartnerDueDiligence, pk=pk)
    obj.status = "rejected"
    obj.save()
    messages.warning(request, "Partner rejected")
    return redirect("partner_detail", pk=pk)


def review_partner(request, pk):
    obj = get_object_or_404(PartnerDueDiligence, pk=pk)
    obj.status = "reviewed"
    obj.save()
    messages.info(request, "Marked as reviewed")
    return redirect("partner_detail", pk=pk)


class VendorDueDiligenceListView(ListView):
    model = VendorDueDiligence
    template_name = "compliance/vendor_list.html"
    context_object_name = "vendors"


class VendorCreate(SuccessMessageMixin, CreateView):
    model = VendorDueDiligence
    form_class = VendorDueDiligenceForm
    template_name = "compliance/form.html"
    success_url = reverse_lazy("vendor_due_diligence_list")

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.created_by = self.request.user
        messages.success(self.request, "Vendor created successfully")
        return super().form_valid(form)


class VendorDetail(DetailView):
    model = VendorDueDiligence
    template_name = "compliance/vendor_detail.html"


class VendorUpdate(UpdateView):
    model = VendorDueDiligence
    form_class = VendorDueDiligenceForm
    template_name = "compliance/form.html"
    # success_url = reverse_lazy("vendor_due_diligence_list")

    def post(self, request, pk):
        task = get_object_or_404(VendorDueDiligence, id=pk)
        form = VendorDueDiligenceForm(request.POST, instance=task)

        if form.is_valid():
            form.save()
            messages.success(request, f'Successfully updated {task}')
            return redirect("vendor_detail", pk=task.id)

        return render(request, self.template_name, {"form": form})


def vendor_delete(request, pk):
    obj = get_object_or_404(VendorDueDiligence, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("vendor_due_diligence_list")

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("vendor_detail", kwargs={'pk': obj.pk})
    })


def compliance_report_pdf(request):

    report_data = []

    for req in ComplianceRequirement.objects.prefetch_related(
        "tasks", "documents", "complianceassessment_set"
    ):
        report_data.append({
            "requirement": req,
            "tasks": req.tasks.all(),
            "verified_docs": req.documents.filter(is_verified=True),
            "score": compliance_score(req),
        })

    context = {
        "report_data": report_data,
        "generated_by": request.user if request.user.is_authenticated else "System",
    }

    pdf = generate_pdf("compliance/pdf_report.html", context)

    if pdf:
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="compliance_report.pdf"'
        return response

    return HttpResponse("Error generating PDF", status=500)


class ComplianceDocumentListView(ListView):
    model = ComplianceDocument
    template_name = 'compliance/document_list.html'
    context_object_name = 'documents'


class ComplianceDocumentUpdateView(UpdateView):
    model = ComplianceDocument
    fields = ['requirement', 'file', 'is_verified']
    template_name = 'compliance/document_form.html'
    success_url = reverse_lazy('compliance_doc_list')


def compliance_doc_delete(request, pk):
    obj = get_object_or_404(ComplianceDocument, pk=pk)

    if request.method == "POST":
        obj.delete()
        messages.success(request, f"{obj} deleted successfully")
        return redirect("compliance_detail", kwargs={'pk': obj.requirement.pk})

    return render(request, "delete_confirmation.html", {
        "delete": obj,
        "cancel_url": reverse_lazy("compliance_detail", kwargs={'pk': obj.requirement.pk})
    })


@login_required(login_url='login')
def verify_document(request, pk):
    doc = get_object_or_404(ComplianceDocument, pk=pk)

    doc.is_verified = True
    doc.verified_by = request.user
    doc.verified_at = now()
    doc.save()

    messages.success(request, "Document verified successfully")
    return redirect(request.META.get('HTTP_REFERER', 'compliance_doc_list'))