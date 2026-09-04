from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from account.models import Department, Profile, Unit
from .models import RecruitmentRequest, JobOpening, Applicant
from .forms import RecruitmentRequestForm, JobPublishForm, ApplicantForm, JobOpeningForm, ApplicantReviewForm
from notification.utils import _send_html_email, notify
from hr_apps.HRapp.views import is_hr
from hr_apps.HRapp.views import is_supervisor
from django.core.mail import EmailMessage

from hr_apps.HRapp.utils import render_template_to_pdf_bytes


RECRUITMENT_EMAIL_TEMPLATE = "emails/recruitment/workflow_notification.html"


def _absolute_url(request, url_name, *args, **kwargs):
    return request.build_absolute_uri(reverse(url_name, args=args, kwargs=kwargs))


def _group_recipients(group_name):
    return Profile.objects.filter(groups__name=group_name, is_active=True).distinct()


def _send_recruitment_email(*, subject, recipients, request_obj, message, action_url, recipient_label):
    to = [user.email for user in recipients if user.email]
    if not to:
        return

    _send_html_email(
        subject=subject,
        to=to,
        template=RECRUITMENT_EMAIL_TEMPLATE,
        context={
            "title": subject,
            "recipient_label": recipient_label,
            "request_obj": request_obj,
            "message": message,
            "action_url": action_url,
        },
    )


@login_required(login_url="login")
def recruitment_request_create(request):

    if request.user.is_superuser:
        units = Unit.objects.all()
    else:
        units = Unit.objects.filter(head=request.user)

    if not units.exists():
        messages.error(
            request,
            "Only Unit Heads can submit recruitment requests."
        )
        return redirect("dashboard")

    form = RecruitmentRequestForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():

        obj = form.save(commit=False)
        obj.requested_by = request.user

        # Security: ensure the selected unit actually belongs to the user
        if not units.filter(pk=obj.unit_id).exists():
            return HttpResponseForbidden(
                "You are not authorized to submit requests for this unit."
            )

        obj.save()

        messages.success(
            request,
            "Recruitment request submitted successfully."
        )

        return redirect("vacancy:recruitment_request_list")

    return render(
        request,
        "vacancy/request_form.html",
        {
            "form": form,
        },
    )


@login_required(login_url='login')
def recruitment_request_list(request):
    user = request.user
    if is_hr(user) or is_supervisor(user) or user.is_superuser or user.groups.filter(name="ED").exists():
        req_list = RecruitmentRequest.objects.select_related("unit", "requested_by").all()
    else:
        req_list = RecruitmentRequest.objects.select_related("unit", "requested_by").filter(requested_by=user)

    paginator = Paginator(req_list, 6)  # 10 employees per page
    page_number = request.GET.get('page')
    req = paginator.get_page(page_number)

    context = {'req_list': req}
    return render(request, 'vacancy/request_list.html', context)


@login_required(login_url='login')
def trash_recruitment_request(request, pk, slug):
    req = get_object_or_404(RecruitmentRequest, pk=pk, slug=slug)

    if not (is_hr(request.user) or is_supervisor(user=request.user) or request.user.is_superuser):
        messages.error(request, 'Access Denied.')
        return redirect('vacancy:recruitment_request_list')

    if request.method == 'POST':
        messages.success(request, f"Training with ({req}) deleted successfully.")
        req.delete()
        return redirect('vacancy:recruitment_request_list')
    return render(request, 'hr/delete_confirmation.html', {'delete': req,
                                                           "cancel_url": reverse('vacancy:recruitment_request_list')})


# 2️⃣ HR reviews
@login_required(login_url='login')
def hr_review(request, pk, slug):
    if not is_hr(request.user):
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(RecruitmentRequest, pk=pk, slug=slug)
    recipient = _group_recipients("ED")
    action_url = _absolute_url(request, "vacancy:ed_approve", req.pk, req.slug)
    subject = f"Recruitment Request Pending ED Approval - {req.title}"
    message = (
        f"The recruitment request '{req.title}' has been reviewed by HR and is pending ED approval.\n\n"
        f"Open the request to approve or take the required action."
    )

    req.hr_reviewed = True
    req.status = "HRReviewed"
    req.save()

    notify(
        request=request,
        title=subject,
        message=message,
        users=recipient,
        action_url=action_url,
        source_app="hr",
    )
    _send_recruitment_email(
        subject=subject,
        recipients=recipient,
        request_obj=req,
        message=message,
        action_url=action_url,
        recipient_label="ED",
    )

    messages.success(request, "Request reviewed by HR.")
    return redirect("vacancy:recruitment_request_list")


# 3️⃣ ED approves
@login_required(login_url='login')
def ed_approve(request, pk, slug):
    if not (request.user.groups.filter(name="ED").exists() or request.user.is_superuser):
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(RecruitmentRequest, pk=pk, slug=slug)
    return render(request, 'vacancy/ed_approve_request.html', {'req': req})


@login_required(login_url='login')
def ed_approve_confirm(request, slug):
    if not (request.user.groups.filter(name="ED").exists() or request.user.is_superuser):
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(RecruitmentRequest, slug=slug)
    req.ed_approved = True
    req.status = "EDApproved"
    req.save()

    recipients = _group_recipients("HR")
    action_url = _absolute_url(request, "vacancy:publish_job", req.pk, req.slug)
    subject = f"Recruitment Request Approved by ED - {req.title}"
    message = (
        f"The recruitment request '{req.title}' has been approved by ED.\n\n"
        f"HR can now publish the vacancy."
    )
    notify(
        request=request,
        title=subject,
        message=message,
        users=recipients,
        action_url=action_url,
        source_app="hr",
    )
    _send_recruitment_email(
        subject=subject,
        recipients=recipients,
        request_obj=req,
        message=message,
        action_url=action_url,
        recipient_label="HR",
    )

    messages.success(request, "Request approved by ED.")
    return redirect("vacancy:recruitment_request_list")


# 4️⃣ HR publishes job
@login_required(login_url='login')
def publish_job(request, pk, slug):
    if not is_hr(request.user):
        return HttpResponseForbidden("Access denied.")

    req = get_object_or_404(RecruitmentRequest, pk=pk, slug=slug)

    if req.status == 'Published':
        messages.error(request, f"Oops!!! {req.title} has been published previously.")
        return redirect("vacancy:recruitment_request_list")

    if req.status != "EDApproved" and not req.ed_approved:
        messages.error(request, "Request must be ED approved.")
        return redirect("vacancy:recruitment_request_list")

    form = JobPublishForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        description = form.cleaned_data["description"]
        JobOpening.objects.create(
            request=req,
            description=description if description else req.justification,
            department=req.department,
            deadline=form.cleaned_data['deadline']
        )
        req.status = "Published"
        req.save()

        recipients = _group_recipients("ED")
        action_url = _absolute_url(request, "vacancy:job_list")
        subject = f"Vacancy Published - {req.title}"
        message = (
            f"The vacancy for '{req.title}' has been published by HR.\n\n"
            f"The job opening is now available in the recruitment module."
        )
        notify(
            request=request,
            title=subject,
            message=message,
            users=recipients,
            action_url=action_url,
            source_app="hr",
        )
        _send_recruitment_email(
            subject=subject,
            recipients=recipients,
            request_obj=req,
            message=message,
            action_url=action_url,
            recipient_label="ED",
        )

        messages.success(request, "Job published successfully.")
        return redirect("vacancy:job_list")

    return render(request, "vacancy/publish_job.html", {"form": form, "req": req})


def job_list(request):
    jobs = (
        JobOpening.objects
        .select_related("request", "request__unit")
        .annotate(applicant_count=Count("applicants"))
    )

    search = request.GET.get("q", "").strip()
    unit_id = request.GET.get("unit", "").strip()

    if search:
        jobs = jobs.filter(
            Q(request__title__icontains=search)
            | Q(request__unit__name__icontains=search)
            | Q(description__icontains=search)
        )

    if unit_id:
        jobs = jobs.filter(request__unit_id=unit_id)

    jobs = jobs.order_by("-posted_at")  # or "-id" if created_at doesn't exist

    paginator = Paginator(jobs, 6)

    return render(
        request,
        "vacancy/job_openings.html",
        {
            "jobs": paginator.get_page(request.GET.get("page")),
            "units": Unit.objects.exclude(name="ED").order_by("name"),
            "selected_unit": unit_id,
        },
    )


def job_detail_modal(request, pk):
    job = JobOpening.objects.annotate(
        applicant_count=Count("applicants")
    ).get(pk=pk)

    html = render_to_string(
        "vacancy/partials/job_detail_modal.html",
        {"job": job},
        request=request
    )
    return JsonResponse({"html": html})


@login_required(login_url='login')
def trash_job_opening(request, slug, pk):
    req = get_object_or_404(JobOpening, pk=pk, slug=slug)

    if not (is_hr(request.user) or is_supervisor(user=request.user) or request.user.is_superuser):
        messages.error(request, 'Access Denied.')
        return redirect('vacancy:job_list')

    if request.method == 'POST':
        messages.success(request, f"Training with ({req}) deleted successfully.")
        req.delete()
        return redirect('vacancy:job_list')
    return render(request, 'hr/delete_confirmation.html', {'delete': req,
                                                           "cancel_url": reverse('vacancy:job_list')})


@login_required(login_url='login')
def edit_job_opening(request, pk, slug):
    job = get_object_or_404(JobOpening, pk=pk, slug=slug)
    if not (is_hr(request.user) or is_supervisor(user=request.user) or request.user.is_superuser):
        messages.error(request, 'Access Denied.')
        return redirect('logout')

    if request.method == 'POST':
        form = JobOpeningForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Opportunity updated successfully.")
            return redirect('vacancy:job_list')
    else:
        form = JobOpeningForm(instance=job)
    return render(request, 'vacancy/edit_job_openings.html', {'form': form, 'job': job})


def apply_job(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    form = ApplicantForm(request.POST or None, request.FILES or None)
    applicant_count = Applicant.objects.filter(job=job).count()


    today = timezone.now().date()
    if job.deadline and job.deadline <= today:
        messages.success(request, f"Application for {job.request.title} is closed.")
        return redirect('vacancy:job_list')

    if request.method == "POST" and form.is_valid():
        applicant = form.save(commit=False)
        applicant.job = job
        applicant.save()
        messages.success(request, "Application submitted.")
        return redirect("vacancy:job_list")

    return render(request, "vacancy/apply_job.html", {"form": form, "job": job, 'applicant_count': applicant_count})


@login_required(login_url='login')
def applicants_list(request):
    if not is_hr(request.user):
        messages.error(request, "Access Denied.")
        return redirect("vacancy:job_list")

    applicants = (
        Applicant.objects
        .select_related("job", "job__request", "job__request__unit", "reviewed_by")
        .order_by("-applied_at")
    )
    return render(request, 'hr/applicant_list.html', {'applicants': applicants})


@login_required(login_url="login")
def applicant_review(request, pk):
    if not is_hr(request.user):
        messages.error(request, "Access Denied.")
        return redirect("vacancy:job_list")

    applicant = get_object_or_404(Applicant, pk=pk)
    form = ApplicantReviewForm(request.POST or None, instance=applicant)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save()
        messages.success(request, "Applicant review saved.")
        return redirect("vacancy:applicants_list")

    return render(request, "hr/applicant_review.html", {"form": form, "applicant": applicant})


@login_required(login_url="login")
def send_applicant_result(request, pk):
    if not is_hr(request.user):
        messages.error(request, "Access Denied.")
        return redirect("vacancy:job_list")

    applicant = get_object_or_404(Applicant.objects.select_related("job", "job__request"), pk=pk)

    context = {
        "applicant": applicant,
        "job": applicant.job,
        "request_obj": applicant.job.request,
        "reviewed_by": applicant.reviewed_by,
        "reviewed_at": applicant.reviewed_at,
        "generated_at": timezone.now(),
    }

    pdf_bytes = render_template_to_pdf_bytes("hr/applicant_result_pdf.html", context)
    if not pdf_bytes:
        messages.error(request, "Failed to generate result PDF.")
        return redirect("vacancy:applicants_list")

    subject = f"Interview Result - {applicant.job.request.title}"
    body = (
        f"Dear {applicant.full_name},\n\n"
        f"Please find attached your interview result for '{applicant.job.request.title}'.\n\n"
        f"Regards,\nHR Team"
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        to=[applicant.email],
    )
    safe_name = "".join(c for c in applicant.full_name if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
    email.attach(
        filename=f"Interview_Result_{safe_name or 'Applicant'}_{applicant.pk}.pdf",
        content=pdf_bytes,
        mimetype="application/pdf",
    )
    email.send(fail_silently=False)

    applicant.decision_sent_at = timezone.now()
    applicant.save(update_fields=["decision_sent_at"])

    messages.success(request, "Interview result PDF sent successfully.")
    return redirect("vacancy:applicants_list")
