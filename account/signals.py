from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from hr_apps.HRapp.employee_models import Employee
from notification.utils import notify
from .models import Profile, ExitProcess
from .services import sync_profile_groups


@receiver(post_save, sender=Profile)
def profile_post_save(sender, instance, created, **kwargs):

    sync_profile_groups(instance)

    if (
        created
        and instance.department
        and instance.can_review
        and not instance.department.head
    ):
        instance.department.head = instance
        instance.department.save(update_fields=["head"])


@receiver(pre_save, sender=Profile)
def cache_previous_profile_assignments(sender, instance, **kwargs):
    """Keep old assignment names available to the post-save synchronizer."""
    if not instance.pk:
        return

    previous = Profile.objects.select_related(
        "department", "unit", "project", "program_area"
    ).filter(pk=instance.pk).first()
    if not previous:
        return

    instance._previous_department_name = getattr(previous.department, "name", None)
    instance._previous_unit_name = getattr(previous.unit, "name", None)
    instance._previous_project_name = getattr(previous.project, "name", None)
    instance._previous_program_area_name = getattr(previous.program_area, "name", None)


@receiver(m2m_changed, sender=Profile.groups.through)
def profile_groups_changed(sender, instance, action, pk_set=None, **kwargs):
    """Prevent direct group edits from leaving conflicting unit groups."""
    if action not in {"post_add", "post_remove", "post_clear"}:
        return

    if isinstance(instance, Profile):
        profiles = [instance]
    elif pk_set:
        profiles = Profile.objects.filter(pk__in=pk_set)
    else:
        profiles = []

    for profile in profiles:
        sync_profile_groups(profile)


@receiver(post_save, sender=Profile)
def create_exit_process_and_notify_hr(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "_previous_status", None)
    became_exit = instance.status == "Exit" and previous_status != "Exit"

    if not became_exit:
        return

    process, _ = ExitProcess.objects.get_or_create(staff=instance)
    process.ensure_steps()

    hr_users = Profile.objects.filter(groups__name="HR").distinct()
    if not hr_users.exists():
        return

    url = ""
    try:
        url = reverse("account_exit_process_update", kwargs={"staff_slug": instance.slug})
    except Exception:
        url = ""

    message = (
        f"{instance.get_full_name() or instance.username} has been marked Exit. "
        f"Start the clearance/offboarding process."
    )

    for hr_user in hr_users:
        notify(
            title="Staff Exit - Clearance Process Required",
            message=message,
            users=hr_user,
            action_url=url,
            source_app="hr"
        )


@receiver(pre_save, sender=Employee)
def cache_previous_supervisor(sender, instance, **kwargs):
    """
    Cache the previous supervisor before saving so we can detect changes.
    """
    instance._previous_supervisor = None

    if instance.pk:
        try:
            instance._previous_supervisor = (
                Employee.objects
                .select_related("user")
                .get(pk=instance.pk)
                .supervised_by
            )
        except Employee.DoesNotExist:
            pass


@receiver(post_save, sender=Employee)
def update_supervisor_group(sender, instance, **kwargs):
    """
    Ensure every employee acting as a supervisor belongs to the
    'Supervisor' group.
    Remove the group if they no longer supervise anyone.
    """

    supervisor_group, _ = Group.objects.get_or_create(name="Supervisor")

    # -----------------------------
    # Add current supervisor
    # -----------------------------
    if instance.supervised_by and instance.supervised_by.user:
        instance.supervised_by.user.groups.add(supervisor_group)

    # -----------------------------
    # Remove previous supervisor
    # if they no longer supervise anyone
    # -----------------------------
    previous = getattr(instance, "_previous_supervisor", None)

    if (
        previous
        and previous != instance.supervised_by
        and previous.user
    ):
        still_supervises = Employee.objects.filter(
            supervised_by=previous
        ).exclude(pk=instance.pk).exists()

        if not still_supervises:
            previous.user.groups.remove(supervisor_group)
