from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from hr_apps.HRapp.templatetags.group_tags import has_group


def is_hr(user) -> bool:
    return bool(user and (user.is_superuser or has_group(user, "HR")))


def is_cmt(user) -> bool:
    return bool(user and (user.is_superuser or getattr(user, "is_CMT", False)))


def can_update_or_edit(user) -> bool:
    """Return whether a user may use an update/edit endpoint."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or has_group(user, "ED"):
        return True

    if not user.groups.filter(
        name__iexact="Edit",
        permissions__content_type__app_label="account",
        permissions__codename="can_edit_records",
    ).exists():
        return False

    from .models import EditAccessGrant

    now = timezone.now()
    grant, created = EditAccessGrant.objects.get_or_create(
        user=user,
        defaults={
            "expires_at": now + timedelta(minutes=getattr(settings, "EDIT_GROUP_ACCESS_MINUTES", 30)),
        },
    )
    if grant.expires_at <= now:
        revoke_edit_access(user)
        return False
    return True


def can_delete_or_trash(user) -> bool:
    """Only ED members and superusers may delete or trash records."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or has_group(user, "ED"))
    )


def can_edit_or_delete(user) -> bool:
    """Backward-compatible alias for temporary update/edit access."""
    return can_update_or_edit(user)


def expire_edit_access(user):
    """Revoke a temporary Edit membership once its grant has expired."""
    if not user or not user.is_authenticated:
        return
    if not user.groups.filter(name__iexact="Edit").exists():
        return

    from .models import EditAccessGrant

    grant = EditAccessGrant.objects.filter(user=user).first()
    if grant and grant.expires_at <= timezone.now():
        revoke_edit_access(user)


def expire_all_edit_access():
    """Clean up every expired Edit membership encountered by the system."""
    from .models import EditAccessGrant

    for grant in EditAccessGrant.objects.filter(expires_at__lte=timezone.now()).select_related("user"):
        revoke_edit_access(grant.user)


def revoke_edit_access(user):
    """Remove temporary Edit membership and its grant."""
    edit_groups = list(user.groups.filter(name__iexact="Edit"))
    if edit_groups:
        user.groups.remove(*edit_groups)
    from .models import EditAccessGrant
    EditAccessGrant.objects.filter(user=user).delete()


def consume_edit_access(user):
    """Consume temporary Edit access after a successful write action."""
    if user and user.is_authenticated and not user.is_superuser and not has_group(user, "ED"):
        revoke_edit_access(user)
