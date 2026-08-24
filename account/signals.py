from django.contrib.auth.models import Group
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from hr_apps.HRapp.employee_models import Employee
from notification.utils import notify
from .models import Profile, ExitProcess
from .services import sync_profile_groups

# @receiver(pre_save, sender=Profile)
# def track_profile_department_and_status(sender, instance, **kwargs):
#     if not instance.pk:
#         instance._previous_department_id = None
#         instance._previous_status = None
#         return
#
#     previous = Profile.objects.filter(pk=instance.pk).only("department_id", "status").first()
#     instance._previous_department_id = getattr(previous, "department_id", None)
#     instance._previous_status = getattr(previous, "status", None)


# @receiver(post_save, sender=Profile)
# def manage_profile_department_group(sender, instance, created, **kwargs):
#     if not instance.department_id:
#         return
#
#     dept_name = instance.department.name
#     group, _ = Group.objects.get_or_create(name=dept_name)
#
#     # If department changed, remove old department group.
#     previous_department_id = getattr(instance, "_previous_department_id", None)
#     if previous_department_id and previous_department_id != instance.department_id:
#         previous_department_name = (
#             Department.objects.filter(pk=previous_department_id)
#             .values_list("name", flat=True)
#             .first()
#         )
#         if previous_department_name and previous_department_name != dept_name:
#             try:
#                 instance.groups.remove(Group.objects.get(name=previous_department_name))
#             except Group.DoesNotExist:
#                 pass
#
#     instance.groups.add(group)
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