from core.models import SystemActivity


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
