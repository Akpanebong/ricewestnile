from django.contrib.auth.backends import ModelBackend


class ActiveUserBackend(ModelBackend):

    def user_can_authenticate(self, user):
        is_active = super().user_can_authenticate(user)

        if not is_active:
            return False

        return True
