from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import Profile


class ActiveUserBackend(ModelBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get("email") or "").strip()
        if not identifier or password is None:
            return None

        normalized = identifier.lower()
        user = Profile.objects.filter(
            Q(username__iexact=identifier) |
            Q(email__iexact=normalized) |
            Q(alternative_email__iexact=normalized) |
            Q(phone__iexact=identifier)
        ).first()

        if user is None:
            # Staff IDs belong to Employee, not Profile.
            from hr_apps.HRapp.employee_models import Employee
            employee = Employee.objects.select_related("user").filter(staff_id__iexact=identifier).first()
            user = employee.user if employee else None

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        is_active = super().user_can_authenticate(user)

        if not is_active:
            return False

        return True
