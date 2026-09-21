from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import Resolver404, resolve

from core.models import SystemActivity
from account.permissions import can_delete_or_trash, can_update_or_edit, consume_edit_access, expire_all_edit_access, expire_edit_access


class RequireLoginForModulesMiddleware:
    """
    Defense-in-depth login gate for whole subsystems.

    An audit found that most views under GARCIS (governance/audit/risk),
    M&E monitoring, and Assets never call @login_required or
    LoginRequiredMixin individually — confirmed live: `curl` with no
    session cookie returned real policy/audit/asset data with HTTP 200.
    Patching each view is still worth doing, but this middleware closes
    the hole immediately and protects any view added to these prefixes in
    the future that forgets the per-view check too.
    """

    PROTECTED_PREFIXES = ("/garcis/", "/mne/monitoring/", "/asset/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and request.path.startswith(self.PROTECTED_PREFIXES):
            return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)
        return self.get_response(request)


class EditDeleteAuthorizationMiddleware:
    """Restrict all routed update/edit/delete actions to superusers and ED."""

    # URL names are used instead of view function names so both function-based
    # and class-based views, including namespaced routes, are covered.
    ACTION_PATTERN = ("update", "edit", "delete", "trash")
    EXCLUDED_URL_NAMES = {
        "edit_access_apply",
        "edit_access_requests",
        "edit_access_decision",
        "update_employee",
        "profile_update",
        "po_update",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expire_all_edit_access()
        if request.user.is_authenticated:
            expire_edit_access(request.user)
        try:
            url_name = getattr(resolve(request.path_info), "url_name", "") or ""
        except Resolver404:
            url_name = ""
        is_delete_action = any(action in url_name.lower() for action in ("delete", "trash"))
        is_edit_action = (
            url_name not in self.EXCLUDED_URL_NAMES
            and not is_delete_action
            and any(action in url_name.lower() for action in ("update", "edit"))
        )
        is_protected_action = is_delete_action or is_edit_action
        has_action_access = (
            can_delete_or_trash(request.user)
            if is_delete_action
            else can_update_or_edit(request.user)
        ) if is_protected_action else True
        if is_protected_action and not has_action_access:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url=settings.LOGIN_URL)
            raise PermissionDenied("Only superusers and members of the ED group may edit or delete records.")

        response = self.get_response(request)
        if (
            is_edit_action
            and has_action_access
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and response.status_code in {201, 202, 204, 301, 302, 303, 307, 308}
        ):
            consume_edit_access(request.user)
        return response


class RequestAuditMiddleware:
    """Capture authenticated write requests without blocking the response path."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if (
                hasattr(request, "user")
                and request.user.is_authenticated
                and not request.path.startswith("/static/")
            ):
                SystemActivity.objects.create(
                    actor=request.user,
                    module=self._infer_module(request.path),
                    action=request.method,
                    object_repr=str(request.path)[:255],
                    path=str(request.path)[:255],
                    method=request.method,
                    status_code=getattr(response, "status_code", 200),
                )
        except Exception:
            pass

        return response

    @staticmethod
    def _infer_module(path):
        segment = path.strip("/").split("/", 1)[0]
        return segment or "core"
