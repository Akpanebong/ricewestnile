from django.urls import resolve
from django.shortcuts import redirect
from django.contrib.auth import logout


class BlockExitedUserMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

        self.exempt_names = [
            "account_exit_process_update",
            "account_exit_process_hr_list",
            "login",
        ]

    def __call__(self, request):
        user = request.user

        if user.is_authenticated:

            if (
                not user.is_superuser and
                getattr(user, "status", None) == "Exit"
            ):

                try:
                    process = getattr(user, "exit_process", None)

                    if process and process.completion_percent >= 100:
                        logout(request)
                        return redirect("login")

                except Exception:
                    pass

                current_url_name = resolve(request.path_info).url_name

                if current_url_name not in self.exempt_names:

                    staff_slug = getattr(user, "slug", None)

                    if staff_slug:
                        return redirect(
                            "account_exit_process_update",
                            staff_slug=staff_slug
                        )

                    return redirect("account_exit_process_hr_list")

        return self.get_response(request)