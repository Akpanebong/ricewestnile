import traceback


class ErrorCaptureMiddleware:
    """Make the current exception available to Django's handler500 callback."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        request._error_report_context = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception) or "No exception message was provided.",
            "traceback": traceback.format_exc(),
        }
        return None
