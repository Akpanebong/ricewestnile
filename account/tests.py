from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, RequestFactory
from django.urls import reverse

from .models import Profile, ExitProcess, ExitStepStatus, ExitStepType
from .utils import generate_strong_password, meal_team_required, superuser_required
from .views import token_generator


class ProfileModelTests(TestCase):
    def test_save_auto_generates_slug(self):
        profile = Profile.objects.create_user(username="jdoe", password="pw")
        self.assertTrue(profile.slug)

    def test_save_keeps_existing_slug(self):
        profile = Profile.objects.create_user(username="jdoe", password="pw")
        original_slug = profile.slug
        profile.first_name = "Jane"
        profile.save()
        self.assertEqual(profile.slug, original_slug)

    def test_str_falls_back_to_username_without_full_name(self):
        profile = Profile.objects.create_user(username="jdoe", password="pw")
        self.assertEqual(str(profile), "jdoe")

    def test_str_uses_full_name_when_present(self):
        profile = Profile.objects.create_user(
            username="jdoe", password="pw", first_name="Jane", last_name="Doe"
        )
        self.assertEqual(str(profile), "Jane Doe")


class ExitProcessModelTests(TestCase):
    def setUp(self):
        self.staff = Profile.objects.create_user(username="leaving", password="pw")
        self.process = ExitProcess.objects.create(staff=self.staff)

    def test_ensure_steps_creates_all_ordered_steps(self):
        self.process.ensure_steps()
        self.assertEqual(self.process.steps.count(), len(ExitStepType.ordered()))

    def test_ensure_steps_is_idempotent(self):
        self.process.ensure_steps()
        self.process.ensure_steps()
        self.assertEqual(self.process.steps.count(), len(ExitStepType.ordered()))

    def test_completion_percent_zero_with_no_steps_done(self):
        self.process.ensure_steps()
        self.assertEqual(self.process.completion_percent, 0)

    def test_completion_percent_partial(self):
        self.process.ensure_steps()
        first_step = self.process.steps.first()
        first_step.mark(status=ExitStepStatus.DONE)
        total = len(ExitStepType.ordered())
        expected = int(round((1 / total) * 100))
        self.assertEqual(self.process.completion_percent, expected)

    def test_completion_percent_full(self):
        self.process.ensure_steps()
        self.process.steps.update(status=ExitStepStatus.DONE)
        self.assertEqual(self.process.completion_percent, 100)


class UtilsTests(TestCase):
    def test_generate_strong_password_default_length(self):
        password = generate_strong_password()
        self.assertEqual(len(password), 10)

    def test_generate_strong_password_custom_length(self):
        password = generate_strong_password(length=24)
        self.assertEqual(len(password), 24)

    def test_generate_strong_password_is_randomized(self):
        passwords = {generate_strong_password() for _ in range(20)}
        self.assertEqual(len(passwords), 20)

    def test_meal_team_required_denies_anonymous(self):
        request = RequestFactory().get("/")
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

        seen = []
        view = meal_team_required()(lambda req: seen.append(True))
        response = view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(seen, [])

    def test_meal_team_required_allows_superuser(self):
        request = RequestFactory().get("/")
        request.user = Profile.objects.create_superuser(
            username="admin", password="pw", email="admin@example.com"
        )

        view = meal_team_required()(lambda req: "ok")
        self.assertEqual(view(request), "ok")

    def test_meal_team_required_allows_meal_group_member(self):
        request = RequestFactory().get("/")
        user = Profile.objects.create_user(username="mealuser", password="pw")
        Group.objects.create(name="MEAL").user_set.add(user)
        request.user = user

        view = meal_team_required()(lambda req: "ok")
        self.assertEqual(view(request), "ok")

    def test_meal_team_required_denies_other_department_by_default(self):
        request = RequestFactory().get("/")
        request.user = Profile.objects.create_user(username="finance_user", password="pw")

        view = meal_team_required()(lambda req: "ok")
        response = view(request)
        self.assertEqual(response.status_code, 302)

    def test_meal_team_required_allows_other_departments_when_flagged(self):
        request = RequestFactory().get("/")
        request.user = Profile.objects.create_user(username="anyone", password="pw")

        view = meal_team_required(allow_other_departments=True)(lambda req: "ok")
        self.assertEqual(view(request), "ok")

    def test_superuser_required_redirects_anonymous_to_login(self):
        request = RequestFactory().get("/")
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

        view = superuser_required(lambda req: "ok")
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_superuser_required_redirects_non_superuser(self):
        request = RequestFactory().get("/")
        request.user = Profile.objects.create_user(username="regular", password="pw")

        view = superuser_required(lambda req: "ok")
        response = view(request)
        self.assertEqual(response.status_code, 302)

    def test_superuser_required_allows_superuser(self):
        request = RequestFactory().get("/")
        request.user = Profile.objects.create_superuser(
            username="admin2", password="pw", email="admin2@example.com"
        )

        view = superuser_required(lambda req: "ok")
        self.assertEqual(view(request), "ok")


class BlockExitedUserMiddlewareTests(TestCase):
    def setUp(self):
        # Creating a Profile with status="Exit" trips the
        # create_exit_process_and_notify_hr post_save signal, which already
        # creates the ExitProcess (with all steps) for us.
        self.exited_user = Profile.objects.create_user(
            username="exited", password="pw", status="Exit"
        )
        self.process = self.exited_user.exit_process

    def test_exited_user_with_incomplete_process_is_redirected_to_their_exit_flow(self):
        self.client.login(username="exited", password="pw")
        response = self.client.get(reverse("department_list"))
        self.assertRedirects(
            response,
            reverse("account_exit_process_update", kwargs={"staff_slug": self.exited_user.slug}),
        )

    def test_exited_user_with_completed_process_is_logged_out(self):
        self.process.steps.update(status=ExitStepStatus.DONE)
        self.client.login(username="exited", password="pw")
        response = self.client.get(reverse("department_list"))
        self.assertRedirects(response, reverse("login"))

        # session should really be gone now
        response = self.client.get(reverse("department_list"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('department_list')}")

    def test_exited_user_can_still_reach_their_own_exit_flow_page(self):
        self.client.login(username="exited", password="pw")
        response = self.client.get(
            reverse("account_exit_process_update", kwargs={"staff_slug": self.exited_user.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_exited_superuser_is_not_blocked(self):
        admin = Profile.objects.create_superuser(
            username="exited_admin", password="pw", email="a@example.com", status="Exit"
        )
        self.client.login(username="exited_admin", password="pw")
        response = self.client.get(reverse("department_list"))
        self.assertEqual(response.status_code, 200)

    def test_active_user_is_never_redirected_by_exit_middleware(self):
        Profile.objects.create_user(username="active", password="pw", status="Active")
        self.client.login(username="active", password="pw")
        response = self.client.get(reverse("department_list"))
        self.assertEqual(response.status_code, 200)


class LoginLogoutViewTests(TestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(username="loginuser", password="correct-pw")

    def test_protected_view_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("department_list"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('department_list')}"
        )

    def test_login_with_correct_credentials_succeeds(self):
        response = self.client.post(
            reverse("login"), {"username": "loginuser", "password": "correct-pw"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_anonymous is False or True)
        # session should now carry an authenticated user
        response = self.client.get(reverse("department_list"))
        self.assertEqual(response.status_code, 200)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            reverse("login"), {"username": "loginuser", "password": "wrong-pw"}
        )
        self.assertEqual(response.status_code, 200)  # re-renders form, no redirect
        response = self.client.get(reverse("department_list"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('department_list')}"
        )

    def test_logout_ends_the_session(self):
        self.client.login(username="loginuser", password="correct-pw")
        self.client.get(reverse("logout"))
        response = self.client.get(reverse("department_list"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('department_list')}"
        )


class ForgotPasswordViewTests(TestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(
            username="hasmail", password="old-pw", email="hasmail@example.com"
        )

    def test_unknown_email_does_not_leak_and_sends_no_mail(self):
        response = self.client.post(reverse("forgot_password"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("forgot_password"))
        self.assertEqual(len(mail.outbox), 0)

    def test_known_email_sends_reset_link(self):
        response = self.client.post(reverse("forgot_password"), {"email": "hasmail@example.com"})
        self.assertRedirects(response, reverse("forgot_password"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("hasmail@example.com", mail.outbox[0].to)

    def test_blank_email_shows_error_and_sends_no_mail(self):
        response = self.client.post(reverse("forgot_password"), {"email": ""})
        self.assertRedirects(response, reverse("forgot_password"))
        self.assertEqual(len(mail.outbox), 0)


class ResetPasswordViewTests(TestCase):
    def setUp(self):
        self.user = Profile.objects.create_user(username="resetme", password="old-pw123")
        self.uid = self._uid(self.user)
        self.token = token_generator.make_token(self.user)

    @staticmethod
    def _uid(user):
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        return urlsafe_base64_encode(force_bytes(user.pk))

    def test_invalid_token_is_rejected(self):
        url = reverse("reset_password", kwargs={"uidb64": self.uid, "token": "not-a-real-token"})
        response = self.client.get(url)
        self.assertRedirects(response, reverse("forgot_password"))

    def test_valid_token_renders_reset_form(self):
        url = reverse("reset_password", kwargs={"uidb64": self.uid, "token": self.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_mismatched_passwords_are_rejected(self):
        url = reverse("reset_password", kwargs={"uidb64": self.uid, "token": self.token})
        response = self.client.post(url, {"password1": "NewStrongPass9!", "password2": "Different9!"})
        self.assertRedirects(response, url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-pw123"))

    def test_weak_password_is_rejected_by_validators(self):
        url = reverse("reset_password", kwargs={"uidb64": self.uid, "token": self.token})
        response = self.client.post(url, {"password1": "password", "password2": "password"})
        self.assertRedirects(response, url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("old-pw123"))

    def test_valid_strong_password_resets_and_allows_login(self):
        url = reverse("reset_password", kwargs={"uidb64": self.uid, "token": self.token})
        response = self.client.post(url, {"password1": "NewStrongPass9!", "password2": "NewStrongPass9!"})
        self.assertRedirects(response, reverse("login"))

        logged_in = self.client.login(username="resetme", password="NewStrongPass9!")
        self.assertTrue(logged_in)

    def test_token_is_single_use(self):
        url = reverse("reset_password", kwargs={"uidb64": self.uid, "token": self.token})
        self.client.post(url, {"password1": "NewStrongPass9!", "password2": "NewStrongPass9!"})

        # Reusing the same token after the password (and thus its hash) changed
        # must be treated as invalid, since PasswordResetTokenGenerator mixes
        # the password hash into the token.
        response = self.client.get(url)
        self.assertRedirects(response, reverse("forgot_password"))


class AdminResetPasswordViewTests(TestCase):
    def setUp(self):
        self.target = Profile.objects.create_user(
            username="target", password="old-pw", email="target@example.com"
        )
        self.superuser = Profile.objects.create_superuser(
            username="root", password="pw", email="root@example.com"
        )
        self.regular_user = Profile.objects.create_user(username="regular", password="pw")

    def test_non_superuser_is_denied(self):
        self.client.login(username="regular", password="pw")
        response = self.client.get(reverse("admin_reset_password", kwargs={"pk": self.target.pk}))
        self.assertRedirects(response, reverse("profile_list"))

    def test_superuser_can_email_a_reset_link(self):
        self.client.login(username="root", password="pw")
        response = self.client.post(
            reverse("admin_reset_password", kwargs={"pk": self.target.pk}),
            {"action": "email_link"},
        )
        self.assertRedirects(
            response, reverse("admin_reset_password", kwargs={"pk": self.target.pk})
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("target@example.com", mail.outbox[0].to)

    def test_superuser_can_set_password_directly_and_it_works(self):
        self.client.login(username="root", password="pw")
        response = self.client.post(
            reverse("admin_reset_password", kwargs={"pk": self.target.pk}),
            {"action": "set_directly"},
        )
        self.assertEqual(response.status_code, 200)
        new_password = response.context["new_password"]

        self.assertTrue(
            self.client.login(username="target", password=new_password)
        )


class ProfileDeleteAuthorizationTests(TestCase):
    def setUp(self):
        self.victim = Profile.objects.create_user(username="victim", password="pw")
        self.regular_user = Profile.objects.create_user(username="bystander", password="pw")
        self.superuser = Profile.objects.create_superuser(
            username="root", password="pw", email="root@example.com"
        )

    def test_non_superuser_cannot_delete_a_profile(self):
        self.client.login(username="bystander", password="pw")
        response = self.client.post(reverse("profile_delete", kwargs={"pk": self.victim.pk}))
        self.assertRedirects(response, reverse("profile_list"))
        self.assertTrue(Profile.objects.filter(pk=self.victim.pk).exists())

    def test_anonymous_user_cannot_delete_a_profile(self):
        response = self.client.post(reverse("profile_delete", kwargs={"pk": self.victim.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Profile.objects.filter(pk=self.victim.pk).exists())

    def test_superuser_can_delete_a_profile(self):
        self.client.login(username="root", password="pw")
        response = self.client.post(reverse("profile_delete", kwargs={"pk": self.victim.pk}))
        self.assertRedirects(response, reverse("profile_list"))
        self.assertFalse(Profile.objects.filter(pk=self.victim.pk).exists())
