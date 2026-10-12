from django.contrib.auth.models import Group

from core.project_models import Project

from .models import Department, ProgramArea, Unit


# These groups are derived from profile data and must not be treated as
# manually assigned permissions. Unit groups are mutually exclusive.
ROLE_GROUPS = {"REVIEW", "CMT"}


def _managed_group_names(profile):
    """Return groups that are safe to manage for this profile."""
    names = set(ROLE_GROUPS)

    # Once a unit is assigned, every other known unit group is exclusive. The
    # cached previous name also handles a unit being cleared or renamed.
    if profile.unit_id:
        names.update(Unit.objects.values_list("name", flat=True))
    if getattr(profile, "_previous_unit_name", None):
        names.add(profile._previous_unit_name)

    # Department groups are only automatic for reviewers. Avoid deleting a
    # manually assigned department-named access group from an unassigned user.
    if profile.can_review and profile.department_id:
        names.update(Department.objects.values_list("name", flat=True))
    if getattr(profile, "_previous_department_name", None):
        names.add(profile._previous_department_name)

    if profile.program_area_id:
        names.update(ProgramArea.objects.values_list("name", flat=True))
    if getattr(profile, "_previous_program_area_name", None):
        names.add(profile._previous_program_area_name)

    if profile.project_id:
        names.update(Project.objects.values_list("name", flat=True))
    if getattr(profile, "_previous_project_name", None):
        names.add(profile._previous_project_name)

    return names


def sync_profile_groups(profile):
    """Synchronize groups derived from a profile without touching permissions.

    Groups such as Admin, Supervisor, Staff, Edit, and other manually granted
    permission groups are preserved. Groups represented by organizational
    units, profile roles, departments, projects, or program areas are managed
    here and stale memberships are removed whenever the profile changes.
    """
    if getattr(profile, "_group_sync_in_progress", False):
        return

    profile._group_sync_in_progress = True
    try:
        desired_names = set()

        if profile.program_area:
            desired_names.add(profile.program_area.name)
        if profile.department and profile.can_review:
            desired_names.add(profile.department.name)
        if profile.unit:
            desired_names.add(profile.unit.name)
        if profile.project:
            desired_names.add(profile.project.name)
        if profile.can_review:
            desired_names.add("REVIEW")
        if profile.is_CMT:
            desired_names.add("CMT")

        managed_names = _managed_group_names(profile)
        desired_groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in desired_names
        }

        stale_groups = profile.groups.filter(name__in=managed_names - desired_names)
        if stale_groups.exists():
            profile.groups.remove(*stale_groups)

        missing_groups = [
            group for group in desired_groups.values()
            if not profile.groups.filter(pk=group.pk).exists()
        ]
        if missing_groups:
            profile.groups.add(*missing_groups)
    finally:
        profile._group_sync_in_progress = False
