"""Custom account adapter to disable user signups."""

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest


class NoSignupAccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]
    """Account adapter that disables user signups."""

    def is_open_for_signup(self, request: HttpRequest) -> bool:
        """Disable new user registration.

        Django-allauth subsequently blocks access to the signup page,
            returning the signup_closed template instead.
        """
        return False

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        """Send each user to their own starting page after signing in.

        Managers land on the overview and officers on their jobs. Anyone
        else uses LOGIN_REDIRECT_URL. Only used when the sign-in link does
        not already say where to go.
        """
        from employees.views import home_url  # noqa: PLC0415

        url: str = home_url(request.user) or super().get_login_redirect_url(request)
        return url
