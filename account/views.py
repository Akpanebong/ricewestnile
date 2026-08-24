import datetime
from smtplib import SMTPRecipientsRefused
from django.core.paginator import Paginator
from django.urls import reverse, reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect

from core.project_models import Project
from hr_apps.HRapp.models import Employee
from hr_apps.HRapp.templatetags.group_tags import has_group
from django.db import transaction
from hr_apps.HRapp.views import is_supervisor
from hr_apps.HRapp.utils import employee_leave_balances
from .models import Department, Profile, ExitProcess, ExitStepType, ExitStepStatus, Unit
from .forms import DepartmentForm, ProfileForm, EmployeeUpdateForm, ExitProcessStepFormSet, get_employee_profile_form_sections
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from .permissions import is_hr, is_cmt
from .utils import generate_strong_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model, logout
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponseForbidden, JsonResponse
import logging
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import date as dt_date
from hr_apps.HRapp.employee_models import (BankDetail, Dependant, EducationHistory, EmergencyContact, EmployeeAddress, EmployeeContact, EmployeePersonalInfo, WorkExperience)

User = get_user_model()
logger = logging.getLogger(__name__)


token_generator = PasswordResetTokenGenerator()


# -------------------- DEPARTMENT --------------------
@login_required
def department_list(request):
    departments = Department.objects.all()
    return render(request, 'dept/dept_list.html', {'departments': departments})


@login_required
def department_create(request):
    departments = Department.objects.exclude(name='ED')
    form = DepartmentForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Department created successfully.")
        return redirect('department_list')
    return render(request, 'dept/dept_form.html', {'form': form, 'title': 'Create Department', 'departments': departments})


@login_required
def department_update(request, pk):
    department = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=department)
    if form.is_valid():
        form.save()
        messages.success(request, "Department updated successfully.")
        return redirect('department_list')
    return render(request, 'dept/dept_form.html', {'form': form, 'title': 'Update Department'})


@login_required
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    department.delete()
    messages.success(request, "Department deleted successfully.")
    return redirect('department_list')


# -------------------- PROFILE --------------------
@login_required
def profile_list(request):
    user = request.user
    data_type = request.GET.get('type', 'profiles')

    filter_types = [
        ("profiles", "All Profiles"),
        ("employee", "Employee"),
        ("intern", "Intern"),
        ("volunteer", "Volunteer"),
        ("community_structure", "Community Structure"),
    ]

    # ✅ BASE QUERYSETS
    profiles_qs = Profile.objects.select_related("department").order_by('program_area')

    staff_qs = Employee.objects.select_related(
        "user", "user__department"
    ).order_by("staff_id")

    # ✅ ACCESS CONTROL
    if not (has_group(user, 'HR') or user.is_superuser):
        profiles_qs = profiles_qs.filter(department=user.department)
        staff_qs = staff_qs.filter(user__department=user.department)
        data_type = "profiles"

    # ✅ STRICT FILTERING (NO MIXING)
    queryset_map = {
        "profiles": profiles_qs,

        # 🔵 PURE STAFF
        "employee": staff_qs.filter(
            user__profile_type="Staff"
        ),

        # 🟡 INTERN
        "intern": staff_qs.filter(
            user__profile_type="Intern"
        ),

        # 🟢 VOLUNTEER
        "volunteer": staff_qs.filter(
            user__profile_type="Volunteer"
        ),

        # 🟣 COMMUNITY STRUCTURE
        "community_structure": staff_qs.filter(
            user__profile_type="Community Structure"
        ),
    }

    queryset = queryset_map.get(data_type, profiles_qs)

    # ✅ PAGINATION
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'profile/profile_list.html', {
        'page_obj': page_obj,
        'data_type': data_type,
        'filter_types': filter_types,
    })



@login_required
def units_for_department(request):
    units = Unit.objects.filter(department_id=request.GET.get('department')).order_by('name')
    return JsonResponse({'units': [{'id': unit.id, 'name': unit.name} for unit in units]})


@login_required
def projects_for_unit(request):
    projects = Project.objects.filter(unit_id=request.GET.get('unit')).order_by('name')
    return JsonResponse({'projects': [{'id': project.id, 'name': project.name} for project in projects]})




@login_required
def profile_create(request):
    current_user = request.user

    if not has_group(current_user, 'HR'):
        logout(request)
        messages.warning(request, 'Oops!!! Access Denied')
        return redirect(reverse('logout'))

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save(commit=False)

            password = generate_strong_password()
            user.set_password(password)
            user.save()

            profile_type = form.cleaned_data.get('profile_type')
            phone = form.cleaned_data.get('phone')
            department = form.cleaned_data.get('department')

            if profile_type:
                Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        "date_joined": datetime.datetime.now(),
                        # "phone": phone,
                        "staff_id": f'R-{user.id}',
                        "category": profile_type,
                        "department": department
                    }
                )

            # ✅ EMAIL
            subject = "Your Account Has Been Created"
            login_url = request.build_absolute_uri(reverse('login'))

            message = (
                f"Dear {user.first_name or user.username},\n\n"
                f"Your account has been successfully created.\n\n"
                f"Username: {user.username}\n"
                f"Password: {password}\n\n"
                f"Login here: {login_url}\n\n"
                f"Please change your password.\n\n"
                f"Regards,\nHR Team"
            )

            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
            except Exception as e:
                messages.warning(request, f"Profile created, but email failed: {e}")

            messages.success(request, f"Profile for {user.username} created successfully.")
            return redirect('profile_list')

        else:
            # 🔥 THIS WAS MISSING
            print(form.errors)  # optional debug
            messages.error(request, "Please correct the errors below.")

    else:
        form = ProfileForm()

    return render(request, 'profile/profile_form.html', {
        'form': form,
        'title': 'Create Profile'
    })


@login_required(login_url='login')
def update_profile(request, slug):
    user = request.user
    readonly_profile_fields = {
        "department",
        "profile_type",
        "status",
        "probation_starts",
        "probation_ends",
        "is_CMT",
    }
    readonly_employee_fields = {
        "department",
        "supervised_by",
        "employment_status",
    }

    employee = (
        Employee.objects
        .select_related("user", "department", "supervised_by")
        .filter(user__slug=slug, user=user)
        .first()
    )
    if employee:
        if request.method == "POST":
            profile_form = ProfileForm(
                request.POST,
                request.FILES,
                instance=user,
                readonly_fields=readonly_profile_fields,
            )
            employee_form = EmployeeUpdateForm(
                request.POST,
                request.FILES,
                instance=employee,
                readonly_fields=readonly_employee_fields,
            )
            single_forms, formsets, employee_sections = get_employee_profile_form_sections(
                post_data=request.POST,
                files=request.FILES,
                employee=employee,
            )
            supplemental_forms = [*single_forms.values(), *formsets.values()]

            if (
                profile_form.is_valid()
                and employee_form.is_valid()
                and all(form.is_valid() for form in supplemental_forms)
            ):
                with transaction.atomic():
                    profile_form.save()
                    employee_form.save()

                    personal_form = single_forms["personal_info_form"]
                    if personal_form.instance.pk or personal_form.has_changed():
                        personal_info = personal_form.save(commit=False)
                        personal_info.employee = employee
                        personal_info.save()

                    bank_form = single_forms["bank_detail_form"]
                    if bank_form.instance.pk or bank_form.has_changed():
                        bank_detail = bank_form.save(commit=False)
                        bank_detail.employee = employee
                        bank_detail.save()

                    for formset in formsets.values():
                        formset.save()
                messages.success(request, "Profile updated successfully.")
                return redirect("update_employee", slug=user.slug)
            messages.error(request, "Please correct the errors below.")
        else:
            profile_form = ProfileForm(instance=user, readonly_fields=readonly_profile_fields)
            employee_form = EmployeeUpdateForm(instance=employee, readonly_fields=readonly_employee_fields)
            single_forms, formsets, employee_sections = get_employee_profile_form_sections(employee=employee)

        return render(request, "account/update_profile.html", {
            "obj": employee,
            "profile_form": profile_form,
            "employee_form": employee_form,
            "employee_sections": employee_sections,
            "is_staff": True,
            "title": "My Employee Bio Data",
        })

    # obj = get_object_or_404(Internship, user__slug=slug, user=user)

    if request.method == "POST":
        profile_form = ProfileForm(
            request.POST,
            request.FILES,
            instance=user,
            readonly_fields=readonly_profile_fields,
        )
        # internship_form = InternshipUpdateForm(request.POST, instance=obj)

        if profile_form.is_valid(): # and internship_form.is_valid()
            with transaction.atomic():
                profile_form.save()
                # internship_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("update_employee", slug=user.slug)
        messages.error(request, "Please correct the errors below.")
    else:
        profile_form = ProfileForm(instance=user, readonly_fields=readonly_profile_fields)
        # internship_form = InternshipUpdateForm(instance=obj)

    return render(request, "account/update_profile.html", {
        # "obj": obj,
        "profile_form": profile_form,
        # "internship_form": internship_form,
        "is_staff": False,
        "title": "My Profile",
    })



def _format_employee_record_value(obj, field):
    value = getattr(obj, field.name)

    if value in (None, ""):
        return "Not provided"

    display_method = getattr(obj, f"get_{field.name}_display", None)
    if callable(display_method):
        return display_method()

    if getattr(field, "is_relation", False):
        return str(value)

    if isinstance(value, bool):
        return "Yes" if value else "No"

    return value


def _employee_record_fields(obj):
    return [
        {
            "label": field.verbose_name.title(),
            "value": _format_employee_record_value(obj, field),
        }
        for field in obj._meta.fields
        if field.name not in {"id", "employee", "slug"}
    ]


def _employee_record_section(key, number, title, description, icon, records):
    if records is None:
        normalized_records = []
    elif isinstance(records, list):
        normalized_records = records
    else:
        normalized_records = [records]

    return {
        "key": key,
        "number": number,
        "title": title,
        "description": description,
        "icon": icon,
        "records": [
            {"label": f"Record {index}", "fields": _employee_record_fields(record)}
            for index, record in enumerate(normalized_records, start=1)
        ],
    }



def get_employee_readonly_sections(employee):
    return [
        _employee_record_section(
            "employment",
            "03",
            "Employment Snapshot",
            "Read-only master employment data from the employee record.",
            "fa-id-card",
            employee,
        ),
        _employee_record_section(
            "personal",
            "04",
            "Personal Information",
            "Identity, demographic, and statutory personal details.",
            "fa-user",
            EmployeePersonalInfo.objects.filter(employee=employee).first(),
        ),
        _employee_record_section(
            "addresses",
            "05",
            "Addresses",
            "Permanent, present, and office address records.",
            "fa-map-marker",
            list(EmployeeAddress.objects.filter(employee=employee)),
        ),
        _employee_record_section(
            "contacts",
            "06",
            "Contact Channels",
            "Personal, official, home phone, and email contact records.",
            "fa-address-book",
            list(EmployeeContact.objects.filter(employee=employee)),
        ),
        _employee_record_section(
            "emergency",
            "07",
            "Emergency Contacts",
            "Next-of-kin and emergency contact details for HR use.",
            "fa-medkit",
            list(EmergencyContact.objects.filter(employee=employee)),
        ),
        _employee_record_section(
            "dependants",
            "08",
            "Dependants",
            "Dependants registered against this employee profile.",
            "fa-users",
            list(Dependant.objects.filter(employee=employee)),
        ),
        _employee_record_section(
            "education",
            "09",
            "Education History",
            "Academic qualifications, institutions, and certifications.",
            "fa-graduation-cap",
            list(EducationHistory.objects.filter(employee=employee)),
        ),
        _employee_record_section(
            "experience",
            "10",
            "Work Experience",
            "Previous employers, roles, years of experience, and skills.",
            "fa-briefcase",
            list(WorkExperience.objects.filter(employee=employee)),
        ),
        _employee_record_section(
            "banking",
            "11",
            "Banking Details",
            "Payroll bank account and branch information.",
            "fa-bank",
            BankDetail.objects.filter(employee=employee).first(),
        ),
    ]


@login_required(login_url='login')
def employee_profile_update(request, pk, slug):
    employee = get_object_or_404(Employee, pk=pk, slug=slug)
    profile = employee.user  # 🔥 FK relationship

    # ✅ Permission check
    if not (is_supervisor(request.user) or request.user.is_superuser):
        messages.error(request, "Access Denied.")
        return redirect('profile_list')

    if request.method == "POST":
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        employee_form = EmployeeUpdateForm(request.POST, request.FILES, instance=employee)

        if profile_form.is_valid() and employee_form.is_valid():
            try:
                with transaction.atomic():  # 🔥 prevents partial save
                    profile_form.save()
                    employee_form.save()

                messages.success(request, "Profile & Employee updated successfully.")
                return redirect('profile_list')

            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "❌ Please correct the errors below.")

    else:
        profile_form = ProfileForm(instance=profile)
        employee_form = EmployeeUpdateForm(instance=employee)

    leave_year = int(request.GET.get("leave_year", dt_date.today().year))
    leave_start = parse_date(request.GET.get("leave_start") or "")
    leave_end = parse_date(request.GET.get("leave_end") or "")
    leave_balance_rows = employee_leave_balances(
        employee=profile,
        year=leave_year,
        start_date=leave_start,
        end_date=leave_end,
    )
    leave_total_allotted = sum(int(r.get("allotted_days") or 0) for r in leave_balance_rows)
    leave_total_taken = sum(int(r.get("taken_days") or 0) for r in leave_balance_rows)
    leave_total_remaining = sum(int(r.get("remaining_days") or 0) for r in leave_balance_rows)

    return render(request, 'profile/employee_profile_form.html', {
        'profile_form': profile_form,
        'employee_form': employee_form,
        'employee_readonly_sections': get_employee_readonly_sections(employee),
        'employee': employee,
        'profile': profile,
        'is_update': True,
        'title': 'Update Employee Profile',
        "leave_year": leave_year,
        "leave_start": request.GET.get("leave_start") or "",
        "leave_end": request.GET.get("leave_end") or "",
        "leave_balance_rows": leave_balance_rows,
        "leave_total_allotted": leave_total_allotted,
        "leave_total_taken": leave_total_taken,
        "leave_total_remaining": leave_total_remaining,
    })


@login_required
def profile_delete(request, pk):
    profile = get_object_or_404(Profile, pk=pk)
    if request.method == 'POST':
        profile.delete()
        messages.success(request, "Profile deleted successfully.")
        return redirect('profile_list')
    return render(request, 'delete_confirmation.html',
                  {'delete': profile, "cancel_url": reverse('profile_list')})


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, "Please enter your email address.")
            return redirect('forgot_password')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # For security we can show success message or show error depending on preference.
            # Here we show a success message to avoid leaking which emails exist.
            messages.success(request, "If that email exists in our system, a password reset link has been sent.")
            return redirect('forgot_password')

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        reset_path = reverse('reset_password', kwargs={'uidb64': uid, 'token': token})
        reset_link = request.build_absolute_uri(reset_path)

        subject = "Reset your password for RICE West Nile Procurement System"
        # plain text fallback
        text_content = render_to_string('account/reset_email.txt', {
            'user': user,
            'reset_link': reset_link,
        })
        # HTML content
        html_content = render_to_string('account/password_reset_email.html', {
            'user': user,
            'reset_link': reset_link,
            'app_name': "RICE West Nile Human Resource System",
        })

        from_email = settings.DEFAULT_FROM_EMAIL
        to = [user.email]

        try:
            msg = EmailMultiAlternatives(subject, text_content, from_email, to)
            msg.attach_alternative(html_content, "text/html")
            msg.send()
        except SMTPRecipientsRefused as e:
            # Recipient refused (rate limiting, mailbox full etc.)
            logger.warning("SMTPRecipientsRefused when sending password reset to %s: %s", user.email, e)
            messages.error(request, "We couldn't deliver the reset email to that address right now. Please try again later.")
            return redirect('forgot_password')
        except Exception as e:
            logger.exception("Unexpected error when sending password reset email")
            messages.error(request, "An error occurred while sending the email. Please try again later.")
            return redirect('forgot_password')

        messages.success(request, "If that email exists in our system, a password reset link has been sent.")
        return redirect('forgot_password')

    return render(request, 'account/forgot_password.html')


def reset_password(request, uidb64, token):
    # decode user id
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not token_generator.check_token(user, token):
        messages.error(request, "The password reset link is invalid or has expired.")
        return redirect('forgot_password')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not password1 or not password2:
            messages.error(request, "Please provide both password fields.")
            return redirect(request.path)

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect(request.path)

        # You can add password validators here if required
        user.set_password(password1)
        user.save()
        messages.success(request, "Your password has been reset successfully. You can now log in.")
        return redirect('login')

    return render(request, 'account/reset_password.html', {'validlink': True})


def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "You have been logged out successfully.")

    return redirect("login")


# -------------------- EXIT FLOW --------------------
@login_required(login_url='login')
def exit_process_hr_list(request):
    if not is_hr(request.user):
        return HttpResponseForbidden("Access denied.")

    staff_qs = (
        Profile.objects.filter(status="Exit")
        .select_related("department", "unit")
        .order_by("last_name", "first_name", "username")
    )

    processes = []
    for staff in staff_qs:
        process, _ = ExitProcess.objects.get_or_create(staff=staff)
        process.ensure_steps()
        processes.append(process)

    return render(request, "account/exitflow/hr_list.html", {"processes": processes})


@login_required(login_url='login')
def exit_process_hr_update(request, staff_slug):
    user = request.user
    is_hr_user = is_hr(user)
    is_self_exit_staff = bool(
        user
        and user.is_authenticated
        and getattr(user, "status", None) == "Exit"
        and getattr(user, "slug", None) == staff_slug
    )

    if not (is_hr_user or is_self_exit_staff):
        return HttpResponseForbidden("Access denied.")

    staff = get_object_or_404(Profile, slug=staff_slug, status="Exit")
    process, _ = ExitProcess.objects.get_or_create(staff=staff)
    process.ensure_steps()

    all_steps_qs = process.steps.all()
    # if all_steps_qs and is_hr(request.user):
    #     notify(
    #         request=request,
    #         users=staff,
    #         title="Clearance Form",
    #         message=(
    #             f"Dear {staff},\n\n "
    #             f"A clearance form has been sent to you by "
    #             f"{request.user.get_full_name()}.\n\n "
    #             f"Please complete and submit it form as soon as possible. "
    #         ),
    #         category="info",
    #         source_app="hr",
    #         action_url="/",
    #     )

    editable_qs = all_steps_qs
    if is_self_exit_staff and not is_hr_user:
        # Exit staff can only submit their clearance form (view others).
        editable_qs = all_steps_qs.filter(step_type=ExitStepType.CLEARANCE_FORM_SUBMITTED)

    if request.method == "POST":
        formset = ExitProcessStepFormSet(
            request.POST, request.FILES, queryset=editable_qs
        )
        if formset.is_valid():
            steps = formset.save(commit=False)
            for step in steps:
                step.updated_by = request.user
                step.updated_at = timezone.now()

                if is_self_exit_staff and not is_hr_user:
                    # Enforce staff restriction server-side.
                    if step.step_type != ExitStepType.CLEARANCE_FORM_SUBMITTED:
                        return HttpResponseForbidden("Access denied.")
                    step.status = ExitStepStatus.DONE
                step.save()
            messages.success(request, "Exit flow updated.")
            return redirect("account_exit_process_update", staff_slug=staff.slug)
        messages.error(request, "Please correct the errors below.")
    else:
        formset = ExitProcessStepFormSet(queryset=editable_qs)

    step_labels = dict(ExitStepType.choices)

    return render(
        request,
        "account/exitflow/hr_update.html",
        {
            "staff": staff,
            "process": process,
            "formset": formset,
            "all_steps": list(all_steps_qs),
            "is_self_exit_staff": is_self_exit_staff and not is_hr_user,
            "step_labels": step_labels,
        },
    )


@login_required(login_url='login')
def exit_process_cmt_list(request):
    if not is_cmt(request.user):
        return HttpResponseForbidden("Access denied.")

    processes = (
        ExitProcess.objects.select_related("staff", "staff__department")
        .filter(staff__status="Exit")
        .order_by("-created_at")
    )
    for process in processes:
        process.ensure_steps()

    return render(request, "account/exitflow/cmt_list.html", {"processes": processes})


@login_required(login_url='login')
def exit_process_cmt_detail(request, staff_slug):
    if not is_cmt(request.user):
        return HttpResponseForbidden("Access denied.")

    staff = get_object_or_404(Profile, slug=staff_slug, status="Exit")
    process, _ = ExitProcess.objects.get_or_create(staff=staff)
    process.ensure_steps()

    step_labels = dict(ExitStepType.choices)

    return render(
        request,
        "account/exitflow/cmt_detail.html",
        {
            "staff": staff,
            "process": process,
            "steps": process.steps.all(),
            "step_labels": step_labels,
        },
    )
