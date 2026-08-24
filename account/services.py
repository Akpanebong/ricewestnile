from django.contrib.auth.models import Group

from .models import Department


AUTO_GROUPS = {
    "program_area",
    "department",
    "unit",
    "project",
    "REVIEW",
    "HOD"
}


def sync_profile_groups(profile):
    """
    Synchronize automatically managed groups.

    Automatically managed groups:
        • Program Area
        • Department (only reviewers)
        • Unit
        • Project
        • REVIEW

    Manually assigned groups (Admin, HR, Procurement, Finance, etc.)
    are preserved.
    """

    desired_groups = set()

    # Program Area
    if profile.program_area:
        desired_groups.add(profile.program_area)

    # Department (reviewers only)
    if profile.department and profile.can_review:
        desired_groups.add(profile.department.name)

    # if profile.department.head:
    #     desired_groups.add(profile.department.head.name)

    # Unit
    if profile.unit:
        desired_groups.add(profile.unit.name)

    # Project
    if profile.project:
        desired_groups.add(profile.project.name)

    # REVIEW
    if profile.can_review:
        desired_groups.add("REVIEW")

    # Create missing groups
    for name in desired_groups:
        Group.objects.get_or_create(name=name)

    current_groups = profile.groups.all()

    # Remove obsolete auto-managed groups
    for group in current_groups:
        auto_managed = (
            group.name == "REVIEW"
            or group.name == getattr(profile.department, "name", None)
            or group.name == getattr(profile.unit, "name", None)
            or group.name == getattr(profile.project, "name", None)
            or group.name == profile.program_area
            or Department.objects.filter(name=group.name).exists()
        )

        if auto_managed and group.name not in desired_groups:
            profile.groups.remove(group)

    # Add desired groups
    for name in desired_groups:
        profile.groups.add(Group.objects.get(name=name))