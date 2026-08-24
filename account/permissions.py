from hr_apps.HRapp.templatetags.group_tags import has_group


def is_hr(user) -> bool:
    return bool(user and (user.is_superuser or has_group(user, "HR")))


def is_cmt(user) -> bool:
    return bool(user and (user.is_superuser or getattr(user, "is_CMT", False)))

