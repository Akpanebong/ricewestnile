from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from hr_apps.HRapp.views import is_hr, is_supervisor
from hr_apps.HRapp.models import Employee
from .models import Appraisal, PerformanceImprovementPlan
from hr_apps.HRapp.templatetags.group_tags import has_group
from hr_apps.HRapp.utils import logo_path
from account.models import Profile
from .utils import send_appraisal_email, render_to_pdf
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.db.models import Avg, Count
from datetime import datetime
from django.db import transaction

from notification.utils import notify


def get_appraisal_filename():
    year = datetime.now().year
    return f"Appraisal_{year}.xlsx"


@login_required
def appraisal_dashboard(request):
    if not (is_hr(request.user) or is_supervisor(request.user) or getattr(request.user, "is_CMT", False)):
        return HttpResponseForbidden("Access denied.")

    qs = Appraisal.objects.all()

    stats = qs.aggregate(
        avg_job=Avg("job_description_score"),
        avg_service=Avg("service_score"),
        total=Count("id")
    )

    yearly = qs.values("year") \
        .annotate(avg_score=Avg("job_description_score")) \
        .order_by("year")

    department_stats = qs.values("employee__user__department__name") \
        .annotate(avg=Avg("job_description_score")) \
        .order_by("-avg")

    return render(request, "performance/appraisal_dashboard.html", {
        "stats": stats,
        "yearly": list(yearly),
        "departments": department_stats
    })


@login_required
def appraisal_list(request):
    user = request.user

    # ⚡ Base queryset (lean + optimized)
    qs = (
        Appraisal.objects
        .select_related(
            "employee__user",
            "supervisor__user"
        )
        .only(
            "id", "reference", "status", "created_at",
            "employee__id", "employee__user__first_name", "employee__user__last_name",
            "supervisor__id", "supervisor__user__first_name", "supervisor__user__last_name",
            "year"
        )
        .order_by("-created_at")
    )

    # 🔐 ROLE-BASED ACCESS CONTROL

    # ✅ 1. HR / Admin → Full access
    if has_group(user, 'HR') or user.is_superuser:
        queryset = qs

    # ✅ 2. CMT → ONLY HR-reviewed + Approved
    elif getattr(user, "is_CMT", False):
        queryset = qs.filter(
            Q(status='reviewed_by_hr')
        )

    # ✅ 3. Employee / Supervisor Logic
    else:
        employee = Employee.objects.filter(user=user).first()

        if not employee:
            queryset = qs.none()
        else:
            queryset = qs.filter(
                Q(employee=employee) |                      # Own appraisals
                Q(supervisor=employee) |                    # As supervisor
                Q(employee__supervised_by=employee)         # Subordinates
            ).distinct()

    # 📄 Pagination (enterprise-friendly)
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 📊 Extra context for UI intelligence (Pro feature)
    context = {
        "page_obj": page_obj,
        "is_hr": has_group(user, 'HR'),
        "is_cmt": getattr(user, "is_CMT", False),
        "total_count": queryset.count(),
    }

    return render(request, "performance/appraisal_list.html", context)


@login_required
def appraisal_detail(request, pk):
    user = request.user

    appraisal = get_object_or_404(
        Appraisal.objects.select_related("employee__user", "supervisor__user" ), pk=pk)

    # Get employee instance
    try:
        employee = Employee.objects.get(user=user)
    except Employee.DoesNotExist:
        employee = None

    # Role detection
    is_employee = employee and appraisal.employee == employee
    can_hr = is_hr(user)
    can_supervisor = bool(
        employee
        and (
            appraisal.supervisor_id == employee.id
            or appraisal.employee.supervised_by_id == employee.id
        )
    ) or is_supervisor(user)
    can_cmt = getattr(user, "is_CMT", False)

    # Permission control
    if not (can_hr or can_supervisor or is_employee or can_cmt):
        return HttpResponseForbidden("You are not allowed to view this appraisal.")

    # Determine stage view
    context = {
        'appraisal': appraisal,
        'is_hr': can_hr,
        'is_supervisor': can_supervisor,
        'is_employee': is_employee,
        "pip": getattr(appraisal, "pip", None),    }

    return render(request, 'performance/appraisal_detail.html', context)


@login_required
@transaction.atomic
def create_appraisal(request, employee_id):
    if not (is_hr(request.user) or is_supervisor(request.user) or request.user.is_superuser):
        return HttpResponseForbidden("Access denied.")

    employee = get_object_or_404(Employee, id=employee_id)
    supervisor = get_object_or_404(Employee, user=request.user)

    if request.method == "POST":

        excel_file = request.FILES.get("template_file")
        date_of_submission = request.POST.get("date_of_submission")

        if not excel_file:
            messages.error(request, "Please upload an appraisal template.")
            return redirect(request.path)

        appraisal = Appraisal.objects.create(
            employee=employee,
            supervisor=supervisor,
            status="sent_to_employee",
            date_of_submission=date_of_submission,
        )

        # Send email with uploaded attachment
        send_appraisal_email(
            request=request,
            appraisal=appraisal,
            subject="Appraisal Form Assigned",
            recipient_email=employee.user.email,
            file=excel_file,
        )

        action_url = request.build_absolute_uri(
            reverse("appraisal_detail", args=[appraisal.pk])
        )

        # Create in-app notification
        notify(
            request=request,
            users=employee.user,
            title="Appraisal Form Assigned",
            message=(
                f"Dear {employee.user.get_full_name()},\n\n"
                f"You have been assigned an appraisal by "
                f"{supervisor.user.get_full_name()}.\n\n"
                f"Please complete and submit it on or before "
                f"{date_of_submission}."
            ),
            category="info",
            source_app="hr",
            action_url=action_url,
        )

        messages.success(
            request,
            "Appraisal sent successfully with attachment."
        )

        return redirect("appraisal_list")

    return render(
        request,
        "performance/create_appraisal.html",
        {
            "employee": employee,
        },
    )

@login_required
def employee_submit(request, pk):
    appraisal = get_object_or_404(Appraisal, pk=pk)

    # 🔒 Security
    if appraisal.employee.user != request.user:
        return HttpResponseForbidden()

    # if appraisal.status == 'approved':
    #     messages.error(request, "You are not allowed to submit this appraisal again.")
    #     return redirect('appraisal_detail', pk=pk)

    if request.method == "POST":
        appraisal.significant_event = request.POST.get("significant_event")
        appraisal.staff_opinion = request.POST.get("staff_opinion")
        appraisal.strengths = request.POST.get("strengths")
        appraisal.weaknesses = request.POST.get("weaknesses")
        appraisal.capacity_gaps = request.POST.get("capacity_gaps")
        appraisal.duty_station = request.POST.get("duty_station")
        appraisal.year = request.POST.get("year")
        appraisal.years_in_org = request.POST.get("years_in_org")
        uploaded_file = request.FILES.get("filled_appraisal")

        if uploaded_file:
            appraisal.filled_appraisal = uploaded_file

        appraisal.status = 'submitted_by_employee'
        appraisal.save()

        # 🔥 Send back to supervisor WITH attachment
        send_appraisal_email(
            request,
            appraisal,
            "Employee Submitted Appraisal",
            appraisal.supervisor.user.email,
            file=uploaded_file  # ✅ attach saved file
        )

        action_url = request.build_absolute_uri(
            reverse("appraisal_detail", args=[appraisal.pk])
        )
        supervisor = appraisal.supervisor.user
        # Create in-app notification
        notify(
            request=request,
            users=supervisor,
            title="Employee Submitted Appraisal",
            message=(
                f"Dear {supervisor.get_full_name()},\n\n"
                f"appraisal has been submitted by"
                f"{appraisal.employee}.\n\n "
                f" for your action."
                f"THANK YOU."
            ),
            category="info",
            source_app="hr",
            action_url=action_url,
        )

        messages.success(request, "Appraisal submitted successfully.")
        return redirect('appraisal_detail', pk=pk)

    return render(request, 'performance/appraisal_employee_form.html', {
        'appraisal': appraisal
    })


@login_required
def supervisor_review(request, pk):
    appraisal = get_object_or_404(Appraisal, pk=pk)
    employee = Employee.objects.filter(user=request.user).first()
    if not (employee and appraisal.supervisor_id == employee.id):
        return HttpResponseForbidden("Access denied.")

    if appraisal.status != 'submitted_by_employee':
        messages.error(request, "Invalid stage.")
        return redirect('appraisal_detail', pk=pk)

    if request.method == "POST":
        appraisal.supervisor_comment = request.POST.get("comment")
        appraisal.job_description_score = request.POST.get("job_description_score")
        appraisal.job_description_interpretation = request.POST.get("job_description_interpretation")
        appraisal.service_score = request.POST.get("service_score")
        appraisal.service_interpretation = request.POST.get("service_interpretation")
        uploaded_file = request.FILES.get("filled_appraisal")

        if uploaded_file:
            appraisal.filled_appraisal = uploaded_file

        appraisal.status = 'reviewed_by_supervisor'
        appraisal.save()

        # Send to HR

        hr_user = Profile.objects.filter(groups__name="HR")
        for pro in hr_user:
            hr_email = pro.email
            send_appraisal_email(request, appraisal, "Supervisor Review Completed", hr_email)

            action_url = request.build_absolute_uri(
                reverse("appraisal_detail", args=[appraisal.pk])
            )
            # Create in-app notification
            notify(
                request=request,
                users=pro,
                title="Supervisor Reviewed Appraisal",
                message=(
                    f"Dear HR,\n\n"
                    f"appraisal has been reviewed and submitted by "
                    f" {appraisal.employee.supervised_by}.\n\n "
                    f" for your action."
                    f"THANK YOU."
                ),
                category="info",
                source_app="hr",
                action_url=action_url,
            )

        return redirect('appraisal_list')

    return render(request, 'performance/supervisor_review.html', {'appraisal': appraisal})


@login_required
def hr_review(request, pk):
    if not is_hr(request.user):
        return HttpResponseForbidden("Access denied.")

    appraisal = get_object_or_404(Appraisal, pk=pk)

    if appraisal.status != 'reviewed_by_supervisor':
        messages.error(request, "Invalid stage.")
        return redirect('appraisal_detail', pk=pk)

    if request.method == "POST":
        appraisal.hr_comment = request.POST.get("comment")
        appraisal.status = 'reviewed_by_hr'
        appraisal.save()

        cmt_profile = Profile.objects.filter(is_CMT=True)
        for pro in cmt_profile:
            cmt_email = pro.email

            send_appraisal_email(request, appraisal, "HR Review Completed", cmt_email)

        return redirect('appraisal_list')

    return render(request, 'performance/hr_review.html', {'appraisal': appraisal})


@login_required
def cmt_approval(request, pk):
    if not getattr(request.user, "is_CMT", False):
        messages.success(request, "Oops!!! Access denied.")
        return redirect('appraisal_detail', pk=pk)

    appraisal = get_object_or_404(Appraisal, pk=pk)

    if appraisal.status != 'reviewed_by_hr':
        messages.success(request, "Oops!!! Access denied.")
        return redirect('appraisal_detail', pk=pk)

    if request.method == "POST":
        appraisal.cmt_comment = request.POST.get("comment")
        appraisal.verdict = request.POST.get("verdict")
        appraisal.cmt_signature = request.FILES.get("cmt_signature")
        appraisal.status = 'approved_by_cmt'
        appraisal.save()

        # 🔥 Generate PDF
        pdf = render_to_pdf('performance/appraisal_pdf.html', {'appraisal': appraisal, "logo_path": logo_path})

        if pdf:
            from django.core.files.base import ContentFile
            appraisal.pdf.save(f"appraisal_{appraisal.id}.pdf", ContentFile(pdf))

        messages.success(request, "Final appraisal completed.")
        return redirect('appraisal_detail', pk=pk)

    return render(request, 'performance/cmt_review.html', {'appraisal': appraisal})


@login_required
def send_pip(request, pk):

    appraisal = get_object_or_404(Appraisal, pk=pk)
    if not (is_hr(request.user) or is_supervisor(request.user) or getattr(request.user, "is_CMT", False)):
        messages.error(request, "Access denied.")
        return redirect("appraisal_detail", pk=pk)

    if appraisal.status != "approved_by_cmt":
        messages.error(request, "Appraisal has not been approved by CMT.")
        return redirect("appraisal_detail", pk=pk)

    if appraisal.verdict != "Retained but sign PIP":
        messages.error(request, "This appraisal does not require a PIP.")
        return redirect("appraisal_detail", pk=pk)

    pip, created = PerformanceImprovementPlan.objects.get_or_create(
        appraisal=appraisal,
        defaults={
            "employee": appraisal.employee,
            "status": "sent_to_staff",
            "sent_at": timezone.now(),
            "sent_by": request.user,
        }
    )

    if not created:
        messages.info(request, "PIP has already been sent.")
        return redirect("appraisal_detail", pk=pk)

    # send email / notification here
    action_url = request.build_absolute_uri(reverse("fill_pip", args=[pip.token]))

    notify(
        request=request,
        users=appraisal.employee.user,
        title="Performance Improvement Plan",
        message=(
            f"Dear {appraisal.employee.user.get_full_name()},\n\n "
            f"A Performance Improvement Plan has been assigned to you by "
            f"{request.user.get_full_name()}.\n\n "
            f"Please complete and submit the PIP form as soon as possible. "
        ),
        category="info",
        source_app="hr",
        action_url=action_url,
    )

    messages.success(request, "Performance Improvement Plan sent successfully.")

    return redirect("appraisal_detail", pk=pk)

#
# @login_required
# def fill_pip(request, token):
#
#     pip = get_object_or_404(
#         PerformanceImprovementPlan,
#         token=token,
#     )
#
#     employee = get_object_or_404(Employee, user=request.user)
#
#     if pip.employee != employee:
#         return HttpResponseForbidden("Access denied.")
#
#     # Already submitted?
#     if pip.status == "submitted_by_staff":
#         messages.info(
#             request,
#             "You have already completed and submitted your Performance Improvement Plan."
#         )
#         return redirect("appraisal_detail", pk=pip.appraisal.pk)
#
#     if request.method == "POST":
#         pip.staff_comment = request.POST.get("staff_comment")
#         pip.staff_signature = request.FILES.get("staff_signature")
#         pip.status = "submitted_by_staff"
#         pip.submitted_at = timezone.now()
#         pip.save()
#
#         messages.success(
#             request,
#             "Performance Improvement Plan submitted successfully."
#         )
#
#         return redirect("appraisal_detail", pk=pip.appraisal.pk)
#
#     return render(
#         request,
#         "performance/fill_pip.html",
#         {"pip": pip},
#     )


@login_required
def fill_pip(request, token):

    pip = get_object_or_404(
        PerformanceImprovementPlan,
        token=token,
    )

    employee = get_object_or_404(Employee, user=request.user)

    if pip.employee != employee:
        return HttpResponseForbidden("Access denied.")

    if pip.status == "submitted_by_staff":
        messages.info(
            request,
            "You have already submitted your Performance Improvement Plan."
        )
        return redirect("appraisal_detail", pk=pip.appraisal.pk)

    if request.method == "POST":

        pip.improvement_areas = request.POST.get("improvement_areas")
        pip.improvement_actions = request.POST.get("improvement_actions")
        pip.support_required = request.POST.get("support_required")
        pip.expected_completion_date = request.POST.get("expected_completion_date") or None
        pip.staff_commitment = request.POST.get("staff_commitment")
        pip.staff_signature = request.FILES.get("staff_signature")

        pip.status = "submitted_by_staff"
        pip.submitted_at = timezone.now()

        pip.save()

        messages.success(
            request,
            "Performance Improvement Plan submitted successfully."
        )

        return redirect("appraisal_detail", pk=pip.appraisal.pk)

    return render(
        request,
        "performance/fill_pip.html",
        {
            "pip": pip,
        },
    )
