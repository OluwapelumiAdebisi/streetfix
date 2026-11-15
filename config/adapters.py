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
