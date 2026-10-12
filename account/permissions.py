from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from hr_apps.HRapp.templatetags.group_tags import has_group


def is_hr(user) -> bool:
    return bool(user and (user.is_superuser or has_group(user, "HR")))


def is_cmt(user) -> bool:
    return bool(user and (user.is_superuser or getattr(user, "is_CMT", False)))


def has_uploaded_signature(user) -> bool:
    """Return True only when the user's profile signature file is available."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    signature = getattr(user, "signature", None)
    if not signature or not getattr(signature, "name", None):
        return False

    try:
        return signature.storage.exists(signature.name)
    except (OSError, ValueError):
        return False


def signature_required(view):
    """Block workflow writes until the acting profile has a signature."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if has_uploaded_signature(request.user):
            return view(request, *args, **kwargs)

        messages.warning(
            request,
            "Upload your signature to your profile before creating, reviewing, checking, or approving documents.",
        )
        return redirect(reverse("update_employee", kwargs={"slug": request.user.slug}))

    return wrapped


def _signatory_user_id(actor):
    """Resolve a profile/user/employee signer to the underlying user id."""
    if actor is None:
        return None
    user_id = getattr(actor, "user_id", None)
    if user_id:
        return user_id
    return getattr(actor, "pk", None)


def can_sign_without_conflict(user, *, requester=None, previous_signers=()):
    """Enforce separation of duties for a document workflow.

    ``requester`` may be a User/Profile or an Employee; previous signers are
    compared by their underlying account id. This keeps the rule consistent
    across HR (Employee supervisor) and the other apps (User foreign keys).
    """
    actor_id = _signatory_user_id(user)
    if not actor_id:
        return False

    if _signatory_user_id(requester) == actor_id:
        return False

    return not any(
        _signatory_user_id(signer) == actor_id
        for signer in previous_signers
        if signer is not None
    )


def deny_signatory_conflict(request, *, requester=None, previous_signers=()):
    """Add the standard SoD error and return whether the action is blocked."""
    if can_sign_without_conflict(
        request.user,
        requester=requester,
        previous_signers=previous_signers,
    ):
        return False

    messages.error(
        request,
        "Separation of duties prevents you from signing this form because "
        "you are the requester or have already signed it at another stage.",
    )
    return True


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
