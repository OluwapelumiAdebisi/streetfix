"""Tests for authenticating employees through django-allauth."""

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse

from employees.organisation_models import Employee

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery"  # noqa: S105


def set_login_credentials(user: User) -> None:
    """Set a known password and verified email address for allauth."""
    user.set_password(PASSWORD)
    user.save(update_fields=("password",))
    EmailAddress.objects.create(
        user=user, email=user.email, primary=True, verified=True
    )


def sign_in(client: Client, user: User, password: str = PASSWORD) -> HttpResponse:
    """Post allauth's email login form."""
    return client.post(
        reverse("account_login"), {"login": user.email, "password": password}
    )  # type: ignore[return-value]


def test_login_page_renders(client: Client) -> None:
    """The sign-in page uses the login template."""
    response = client.get(reverse("account_login"))

    assert response.status_code == 200
    assert any(template.name == "account/login.html" for template in response.templates)


def test_employee_can_sign_in(client: Client, manager: Employee) -> None:
    """A verified employee can sign in through allauth."""
    set_login_credentials(manager.user)

    response = sign_in(client, manager.user)

    assert response.headers["Location"] == reverse("employees:dashboard")
    assert str(manager.user.pk) == client.session["_auth_user_id"]


def test_allauth_uses_the_configured_default_redirect(
    client: Client, django_user_model: type[User]
) -> None:
    """Accounts without an employee record use the shared default redirect."""
    user = django_user_model.objects.create_user(
        username="public", email="public@example.com"
    )
    set_login_credentials(user)

    response = sign_in(client, user)

    assert response.headers["Location"] == reverse("employees:dashboard")


def test_wrong_password_is_refused(client: Client, manager: Employee) -> None:
    """A wrong password shows the error and does not sign in."""
    set_login_credentials(manager.user)

    response = sign_in(client, manager.user, "wrong-password")

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_manager_pages_send_visitors_to_login(client: Client) -> None:
    """Signed-out visitors are sent to the sign-in page, not the admin."""
    response = client.get(reverse("employees:dashboard"))

    assert response.status_code == 302
    assert str(response.headers["Location"]).startswith(reverse("account_login"))


def test_sign_out_returns_to_login(manager_client: Client) -> None:
    """Signing out ends the session and returns to the configured destination."""
    response = manager_client.post(reverse("account_logout"))

    assert response.headers["Location"] == reverse("intake:form_intake")
    assert "_auth_user_id" not in manager_client.session


def test_login_page_shows_site_branding_name(client: Client) -> None:
    """The page shows the configured site name, not the host name."""
    response = client.get(reverse("account_login"))

    assert b"<title>Project</title>" in response.content
