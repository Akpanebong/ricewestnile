import string
import secrets
from functools import wraps

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def generate_strong_password(length=10):
    """Generate a strong random password."""
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(chars) for _ in range(length))


def meal_team_required(allow_superuser=True, allow_other_departments=False):
    def check(user):
        if not user.is_authenticated:
            return False
        if allow_superuser and user.is_superuser:
            return True
        if user.groups.filter(name="MEAL").exists():
            return True
        return bool(allow_other_departments)

    return user_passes_test(check, login_url="login", redirect_field_name=None)


class MealTeamAccessMixin:
    allow_superuser = True
    allow_other_departments = False

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied("You must be logged in.")
        if self.allow_superuser and user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if user.groups.filter(name="MEAL").exists():
            return super().dispatch(request, *args, **kwargs)
        if self.allow_other_departments:
            return super().dispatch(request, *args, **kwargs)
        raise PermissionDenied("You do not have permission to access this page.")


def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not request.user.is_superuser:
            return redirect("monitoring:dashboard")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class SuperuserRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Login required.")
        if not request.user.is_superuser:
            raise PermissionDenied("Only MEAL Admin can access this page.")
        return super().dispatch(request, *args, **kwargs)
