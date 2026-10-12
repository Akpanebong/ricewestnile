from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Prefetch
from django.db import transaction
from django.http import JsonResponse
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from hr_apps.HRapp.templatetags.group_tags import has_group
from account.models import Unit
from account.permissions import is_cmt
from core.forms import (
    ActivityConceptNoteForm, ActivityConceptNoteUploadForm, ProjectActivityFormSet, ProjectDocumentForm, ProjectForm, ProjectBudgetFormSet,
    ProjectSubmissionForm, StakeholderUpdateForm, TeamMeetingForm,
)
from core.project_models import (
    ActivityConceptNote, Project, ProjectActivity, ProjectBudget, ProjectDocument, ProjectSubmission,
    StakeholderUpdate, TeamMeeting,
)
from core.workplan_services import extract_workplan_activities
from core.project_reporting_exports import stakeholder_updates_workbook, team_meetings_workbook
from notification.utils import notify


def default_project_budget_rows():
    fiscal_year = ProjectBudget.current_fiscal_year()
    return [
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.FULL_YEAR},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q1},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q2},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q3},
        {'fiscal_year': fiscal_year, 'period': ProjectBudget.Q4},
    ]


# -------------------- PROJECT--------------------
@login_required
def project_list(request):
    fiscal_year = request.GET.get('fiscal_year') or ProjectBudget.current_fiscal_year()
    projects = Project.objects.select_related('project_officer', 'program_area', 'unit').prefetch_related(
        'budgets',
        Prefetch(
            'documents',
            queryset=ProjectDocument.objects.prefetch_related(
                Prefetch('activities', to_attr='_prefetched_activities')
            ),
            to_attr='_prefetched_schedule_documents',
        ),
    )

    for project in projects:
        budgets = [budget for budget in project.budgets.all() if budget.fiscal_year == fiscal_year]
        full_year_budgets = [
            budget for budget in budgets
            if budget.period == ProjectBudget.FULL_YEAR
        ]
        budget_source = full_year_budgets or budgets
        budget_amount = sum((budget.budget_amount for budget in budget_source), 0)
        amount_used = sum((budget.actual_amount_used() for budget in budget_source), 0)
        project.budget_summary = {
            'budget_amount': budget_amount,
            'amount_used': amount_used,
            'amount_remaining': budget_amount - amount_used,
        }

    return render(request, 'project/project_list.html', {
        'projects': projects,
        'fiscal_year': fiscal_year,
    })


@login_required
def project_create(request):

    if not has_group(request.user, 'Procurement'):
        messages.warning(request, "Procurement access required.")
        return redirect('core:project_list')

    project = Project.objects.all()
    form = ProjectForm(request.POST or None)
    formset = ProjectBudgetFormSet(
        request.POST or None,
        prefix='budgets',
        initial=default_project_budget_rows() if request.method != 'POST' else None,
    )
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        new_project = form.save()
        formset.instance = new_project
        formset.save()
        messages.success(request, "Project created successfully.")
        return redirect('core:project_list')
    elif request.method != 'POST':
        form = ProjectForm()
        formset = ProjectBudgetFormSet(prefix='budgets', initial=default_project_budget_rows())
    return render(request, 'project/project_form.html', {
        'form': form,
        'formset': formset,
        'project': project,
        'title': 'Create Project',
    })


@login_required
def project_update(request, pk, slug):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    form = ProjectForm(request.POST or None, instance=project)
    formset = ProjectBudgetFormSet(request.POST or None, instance=project, prefix='budgets')
    if request.method == 'POST' and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, "Project updated successfully.")
        return redirect('core:project_list')
    return render(request, 'project/project_form.html',
                  {
                      'form': form,
                      'formset': formset,
                      'is_update': True,
                      'title': 'Update Project',
                      'project': project,
                  })


@login_required
def project_delete(request, pk, name):
    project = get_object_or_404(Project, pk=pk, name=name)
    if request.method == 'POST':
        project.delete()
        messages.success(request, "Project deleted successfully.")
        return redirect('core:project_list')
    return render(request, 'delete_confirmation.html',
                  {'delete': project, "cancel_url": reverse('core:project_list')})


def _can_upload_project_documents(request, project):
    return request.user.is_superuser or project.project_officer_id == request.user.pk


def _is_project_officer(request, project):
    return request.user.is_superuser or project.project_officer_id == request.user.pk


def _forbidden(message):
    return HttpResponseForbidden(message)


def _concept_note_project(activity):
    return activity.workplan.project


def _can_manage_concept_note(request, project):
    return request.user.is_superuser or project.project_officer_id == request.user.pk


def _can_view_concept_note(request, project):
    if request.user.is_superuser:
        return True
    program_head_id = project.unit.department.head_id if project.unit_id and project.unit.department_id else None
    return request.user.pk in {project.project_officer_id, project.project_head_id, program_head_id}


def _get_activity_for_concept_note(pk, activity_id):
    return get_object_or_404(
        ProjectActivity.objects.select_related("workplan__project", "workplan__project__project_head", "workplan__project__unit__department__head", "workplan__project__program_area"),
        pk=activity_id,
        workplan__project_id=pk,
        confirmed=True,
    )


def _concept_note_action_url(request, project, activity):
    return request.build_absolute_uri(
        reverse(
            "core:activity_concept_note_detail",
            args=[project.pk, project.slug, activity.pk],
        )
    )


def _notify_concept_note(*, request, note, recipients, title, message, category):
    """Send the same concept-note event through in-app and email channels."""
    unique_recipients = []
    seen_ids = set()
    for recipient in recipients:
        if recipient and recipient.pk not in seen_ids and recipient.is_active:
            unique_recipients.append(recipient)
            seen_ids.add(recipient.pk)

    if not unique_recipients:
        return

    action_url = _concept_note_action_url(request, note.project, note.activity)
    notify(
        title=title,
        message=message,
        request=request,
        users=unique_recipients,
        category=category,
        action_url=action_url,
    )

    email_message = f"{message}\n\nOpen the activity concept note:\n{action_url}"
    email_recipients = [recipient.email for recipient in unique_recipients if recipient.email]
    if email_recipients:
        send_mail(
            subject=title,
            message=email_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=email_recipients,
            fail_silently=True,
        )


@login_required
def activity_concept_note_entry(request, pk, slug, activity_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    activity = _get_activity_for_concept_note(project.pk, activity_id)
    if not _can_manage_concept_note(request, project):
        return _forbidden("Only the assigned Project Officer can prepare this activity concept note.")
    note = ActivityConceptNote.objects.filter(activity=activity).first()
    if note and note.status == ActivityConceptNote.APPROVED:
        return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)
    form = ActivityConceptNoteForm(request.POST or None, instance=note, activity=activity)
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        note.activity = activity
        note.source = ActivityConceptNote.ONLINE
        note.created_by = note.created_by or request.user
        note.save()
        messages.success(request, "Activity concept note saved as a draft.")
        return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)
    return render(request, "project/activity_concept_note_form.html", {
        "project": project, "activity": activity, "form": form, "note": note, "entry_mode": "online",
    })


@login_required
def activity_concept_note_upload(request, pk, slug, activity_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    activity = _get_activity_for_concept_note(project.pk, activity_id)
    if not _can_manage_concept_note(request, project):
        return _forbidden("Only the assigned Project Officer can upload this activity concept note.")
    note = ActivityConceptNote.objects.filter(activity=activity).first()
    if note and note.status not in {ActivityConceptNote.DRAFT, ActivityConceptNote.REJECTED}:
        messages.info(request, "This concept note is already in the approval workflow.")
        return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)
    form = ActivityConceptNoteUploadForm(request.POST or None, request.FILES or None, instance=note)
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        note.activity = activity
        note.source = ActivityConceptNote.UPLOADED
        note.created_by = note.created_by or request.user
        note.save()
        messages.success(request, "Completed concept note uploaded as a draft.")
        return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)
    return render(request, "project/activity_concept_note_form.html", {
        "project": project, "activity": activity, "form": form, "note": note, "entry_mode": "upload",
    })


@login_required
def activity_concept_note_detail(request, pk, slug, activity_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    activity = _get_activity_for_concept_note(project.pk, activity_id)
    note = get_object_or_404(ActivityConceptNote, activity=activity)
    if not _can_view_concept_note(request, project):
        return _forbidden("You are not authorised to view this activity concept note.")
    return render(request, "project/activity_concept_note_detail.html", {
        "project": project, "activity": activity, "note": note,
        "can_manage": _can_manage_concept_note(request, project),
        "can_review": request.user.is_superuser or project.project_head_id == request.user.pk,
        "can_approve": request.user.is_superuser or (
            project.unit_id and project.unit.department_id and project.unit.department.head_id == request.user.pk
        ),
    })


@login_required
def activity_concept_note_submit(request, pk, slug, activity_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    activity = _get_activity_for_concept_note(project.pk, activity_id)
    note = get_object_or_404(ActivityConceptNote, activity=activity)
    if not _can_manage_concept_note(request, project):
        return _forbidden("Only the assigned Project Officer can submit this concept note.")
    if request.method != "POST" or note.status not in {ActivityConceptNote.DRAFT, ActivityConceptNote.REJECTED}:
        return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)
    if not note.uploaded_file and not any([note.background, note.objectives, note.methodology, note.expected_outputs]):
        messages.error(request, "Complete the online concept note or upload the filled form before submitting.")
        return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)
    note.status = ActivityConceptNote.SUBMITTED
    note.submitted_by = request.user
    note.submitted_at = timezone.now()
    note.rejection_reason = ""
    note.save(update_fields=["status", "submitted_by", "submitted_at", "rejection_reason", "updated_at"])
    _notify_concept_note(
        request=request,
        note=note,
        recipients=[project.project_head],
        title="Activity concept note submitted for your review",
        message=(
            f"{request.user.get_full_name() or request.user.username} submitted the "
            f"activity concept note for {activity.name} in {project.name}."
        ),
        category="info",
    )
    messages.success(request, "Concept note submitted to the Project Head for review.")
    return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)


@login_required
def activity_concept_note_review(request, pk, slug, activity_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    activity = _get_activity_for_concept_note(project.pk, activity_id)
    note = get_object_or_404(ActivityConceptNote, activity=activity)
    if not (request.user.is_superuser or project.project_head_id == request.user.pk):
        return _forbidden("Only the Project Head can review this concept note.")
    if request.method == "POST" and note.status == ActivityConceptNote.SUBMITTED:
        action = request.POST.get("action")
        comments = request.POST.get("comments", "").strip()
        note.reviewed_by = request.user
        note.reviewed_at = timezone.now()
        note.review_comments = comments
        if action == "return":
            note.status = ActivityConceptNote.REJECTED
            note.rejection_reason = comments
            notification_title = "Activity concept note returned for revision"
            notification_message = (
                f"The Project Head returned the activity concept note for {activity.name} "
                f"in {project.name} for revision."
            )
            messages.success(request, "Concept note returned to the Project Officer for revision.")
        else:
            note.status = ActivityConceptNote.REVIEWED
            notification_title = "Activity concept note reviewed"
            notification_message = (
                f"The Project Head reviewed the activity concept note for {activity.name} "
                f"in {project.name}. It is ready for your action."
            )
            messages.success(request, "Concept note reviewed and sent to the Head of Program Department.")
        note.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comments", "rejection_reason", "updated_at"])
        if action == "return":
            _notify_concept_note(
                request=request,
                note=note,
                recipients=[project.project_officer, note.submitted_by],
                title=notification_title,
                message=notification_message,
                category="warning",
            )
        else:
            _notify_concept_note(
                request=request,
                note=note,
                recipients=[note.program_head],
                title=notification_title,
                message=notification_message,
                category="info",
            )
    return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)


@login_required
def activity_concept_note_approve(request, pk, slug, activity_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    activity = _get_activity_for_concept_note(project.pk, activity_id)
    note = get_object_or_404(ActivityConceptNote, activity=activity)
    program_head_id = project.unit.department.head_id if project.unit_id and project.unit.department_id else None
    if not (request.user.is_superuser or program_head_id == request.user.pk):
        return _forbidden("Only the Head of Program Department can approve this concept note.")
    if request.method == "POST" and note.status == ActivityConceptNote.REVIEWED:
        rejected = request.POST.get("action") == "reject"
        if rejected:
            note.status = ActivityConceptNote.REJECTED
            note.rejection_reason = request.POST.get("comments", "").strip()
            messages.success(request, "Concept note returned to the Project Officer for revision.")
        else:
            note.status = ActivityConceptNote.APPROVED
            note.approved_by = request.user
            note.approved_at = timezone.now()
            messages.success(request, "Activity concept note approved.")
        note.save(update_fields=["status", "rejection_reason", "approved_by", "approved_at", "updated_at"])
        _notify_concept_note(
            request=request,
            note=note,
            recipients=[project.project_head, project.project_officer, note.submitted_by],
            title=(
                "Activity concept note rejected"
                if rejected
                else "Activity concept note approved"
            ),
            message=(
                f"The Head of Program Department {'rejected' if rejected else 'approved'} "
                f"the activity concept note for {activity.name} in {project.name}."
            ),
            category="warning" if rejected else "success",
        )
    return redirect("core:activity_concept_note_detail", pk=project.pk, slug=project.slug, activity_id=activity.pk)


@login_required
def project_documents(request, pk, slug):
    project = get_object_or_404(
        Project.objects.select_related("project_officer"), pk=pk, slug=slug,)

    documents = list(ProjectDocument.objects.filter(project=project).select_related("uploaded_by").prefetch_related(
        Prefetch("activities", queryset=ProjectActivity.objects.select_related("concept_note"), to_attr="_prefetched_activities")
    ).all())
    project._prefetched_schedule_documents = documents
    latest_workplan = project._latest_workplan()
    latest_activities = [
        activity for activity in (getattr(latest_workplan, "_prefetched_activities", []) if latest_workplan else [])
        if activity.confirmed
    ]
    return render(request, "project/project_documents.html", {
        "project": project,
        "documents": documents,
        "latest_workplan": latest_workplan,
        "latest_activities": latest_activities,
        "can_upload": _can_upload_project_documents(request, project),
    })


@login_required
def project_document_upload(request, pk, slug, document_type):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    if document_type not in {ProjectDocument.WORKPLAN, ProjectDocument.REPORT}:
        return redirect("core:project_documents", pk=project.pk, slug=project.slug)
    if not _can_upload_project_documents(request, project):
        messages.error(request, "Only the assigned Project Officer can upload documents for this project.")
        return redirect("core:project_documents", pk=project.pk, slug=project.slug)

    form = ProjectDocumentForm(
        request.POST or None,
        request.FILES or None,
        document_type=document_type,
        project=project,
    )
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.project = project
        document.document_type = document_type
        document.uploaded_by = request.user
        document.save()
        if document_type == ProjectDocument.WORKPLAN:
            extracted_count = extract_workplan_activities(document)
            messages.info(request, f"{extracted_count} activities extracted. Please confirm their names and dates.")
            return redirect("core:project_activity_confirm", pk=project.pk, slug=project.slug, document_id=document.pk)
        messages.success(request, f"{document.get_document_type_display()} uploaded successfully.")
        return redirect("core:project_documents", pk=project.pk, slug=project.slug)

    return render(request, "project/project_document_form.html", {
        "project": project,
        "form": form,
        "document_type": document_type,
        "document_title": "Workplan" if document_type == ProjectDocument.WORKPLAN else "Report",
    })


@login_required
def project_activity_confirm(request, pk, slug, document_id):
    project = get_object_or_404(Project, pk=pk, slug=slug)
    if not _can_upload_project_documents(request, project):
        messages.error(request, "Only the assigned Project Officer can confirm workplan activities.")
        return redirect("core:project_documents", pk=project.pk, slug=project.slug)
    workplan = get_object_or_404(
        ProjectDocument,
        pk=document_id,
        project=project,
        document_type=ProjectDocument.WORKPLAN,
    )
    formset = ProjectActivityFormSet(request.POST or None, instance=workplan, prefix="activities")
    if request.method == "POST" and formset.is_valid():
        confirmed_at = timezone.now()
        with transaction.atomic():
            # Let the formset save and delete exactly the rows the officer
            # confirmed in the form, then explicitly persist confirmation
            # metadata because those fields are intentionally excluded from
            # the editable activity form.
            formset.save()
            confirmed_count = ProjectActivity.objects.filter(workplan=workplan).update(
                confirmed=True,
                confirmed_by=request.user,
                confirmed_at=confirmed_at,
            )
            workplan.activities_count = confirmed_count
            workplan.save(update_fields=["activities_count"])
        messages.success(request, "Workplan activities and dates confirmed successfully.")
        return redirect("core:project_documents", pk=project.pk, slug=project.slug)
    return render(request, "project/project_activity_confirm.html", {
        "project": project,
        "workplan": workplan,
        "formset": formset,
    })


@login_required
def project_reporting_input(request, pk, slug):
    """Project Officer entry point for the stakeholder, meeting and submission records."""
    project = get_object_or_404(Project, pk=pk, slug=slug)
    if not _is_project_officer(request, project):
        return _forbidden("Only the assigned Project Officer can enter records for this project.")

    stakeholder_form = StakeholderUpdateForm(prefix="stakeholder")
    meeting_form = TeamMeetingForm(prefix="meeting")
    submission_form = ProjectSubmissionForm(prefix="submission")
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "stakeholder":
            stakeholder_form = StakeholderUpdateForm(request.POST, prefix="stakeholder")
            if stakeholder_form.is_valid():
                record = stakeholder_form.save(commit=False)
                record.project = project
                record.entered_by = request.user
                record.save()
                messages.success(request, "Stakeholder update saved.")
                return redirect("core:project_reporting_input", pk=project.pk, slug=project.slug)
        elif form_type == "meeting":
            meeting_form = TeamMeetingForm(request.POST, prefix="meeting")
            if meeting_form.is_valid():
                record = meeting_form.save(commit=False)
                record.project = project
                record.entered_by = request.user
                record.save()
                messages.success(request, "Team meeting record saved.")
                return redirect("core:project_reporting_input", pk=project.pk, slug=project.slug)
        elif form_type == "submission":
            submission_form = ProjectSubmissionForm(request.POST, request.FILES, prefix="submission")
            if submission_form.is_valid():
                submission = submission_form.save(commit=False)
                submission.project = project
                submission.uploaded_by = request.user
                submission.save()
                messages.success(request, "Project document uploaded for CMT review.")
                return redirect("core:project_reporting_input", pk=project.pk, slug=project.slug)

    return render(request, "project/project_reporting_input.html", {
        "project": project,
        "stakeholder_form": stakeholder_form,
        "meeting_form": meeting_form,
        "submission_form": submission_form,
    })


@login_required
def cmt_project_reporting(request, pk, slug):
    """CMT-only read view for all project updates and confidential submissions."""
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can view project reporting records.")
    project = get_object_or_404(Project.objects.select_related("project_officer"), pk=pk, slug=slug)
    section = request.GET.get("section", "all")
    if section not in {"all", "documents", "stakeholder", "meetings"}:
        section = "all"
    return render(request, "project/cmt_project_reporting.html", {
        "project": project,
        "active_section": section,
        "stakeholder_updates": project.stakeholder_updates.select_related("entered_by").all() if section in {"all", "stakeholder"} else [],
        "team_meetings": project.team_meetings.select_related("entered_by").all() if section in {"all", "meetings"} else [],
        "submissions": project.submissions.select_related("uploaded_by").all() if section in {"all", "documents"} else [],
    })


@login_required
def cmt_reporting_all(request):
    """CMT-only consolidated view across every project."""
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can view project reporting records.")
    section = request.GET.get("section", "all")
    if section not in {"all", "documents", "stakeholder", "meetings"}:
        section = "all"
    return render(request, "project/cmt_project_reporting.html", {
        "project": None,
        "page_title": "All Projects — CMT Reporting",
        "all_projects": True,
        "active_section": section,
        "stakeholder_updates": StakeholderUpdate.objects.select_related("project", "entered_by").all() if section in {"all", "stakeholder"} else [],
        "team_meetings": TeamMeeting.objects.select_related("project", "entered_by").all() if section in {"all", "meetings"} else [],
        "submissions": ProjectSubmission.objects.select_related("project", "uploaded_by").all() if section in {"all", "documents"} else [],
    })


@login_required
def cmt_project_submission_download(request, pk, slug, submission_id):
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can download project submissions.")
    project = get_object_or_404(Project, pk=pk, slug=slug)
    submission = get_object_or_404(ProjectSubmission, pk=submission_id, project=project)
    response = FileResponse(submission.file.open("rb"), as_attachment=True, filename=submission.file.name.rsplit("/", 1)[-1])
    return response


@login_required
def cmt_stakeholder_updates_download(request, pk, slug):
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can download stakeholder updates.")
    project = get_object_or_404(Project, pk=pk, slug=slug)
    return stakeholder_updates_workbook(project)


@login_required
def cmt_team_meetings_download(request, pk, slug):
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can download team meeting records.")
    project = get_object_or_404(Project, pk=pk, slug=slug)
    return team_meetings_workbook(project)


@login_required
def cmt_all_stakeholder_export(request):
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can download stakeholder updates.")
    return stakeholder_updates_workbook(None)


@login_required
def cmt_all_team_meetings_export(request):
    if not is_cmt(request.user):
        return _forbidden("Only CMT members can download team meeting records.")
    return team_meetings_workbook(None)


@login_required
def units_for_department(request):
    units = Unit.objects.filter(department_id=request.GET.get('department')).order_by('name')
    return JsonResponse({'units': [{'id': unit.id, 'name': unit.name} for unit in units]})


@login_required
def projects_for_unit(request):
    projects = Project.objects.filter(unit_id=request.GET.get('unit')).order_by('name')
    return JsonResponse({'projects': [{'id': project.id, 'name': project.name} for project in projects]})
