from django.conf import settings
from django.contrib.auth.views import redirect_to_login

from core.models import SystemActivity


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
                and request.method in {"POST", "PUT", "PATCH", "DELETE"}
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
