"""Tests for the employee sign-in and sign-out pages."""

from collections.abc import Callable

import pytest
from django.test import Client
from django.urls import reverse

from employees.organisation_models import Employee

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery"  # noqa: S105


def with_password(employee: Employee) -> Employee:
    """Give an employee's account a known password."""
    employee.user.set_password(PASSWORD)
    employee.user.save(update_fields=("password",))
    return employee


def sign_in(client: Client, username: str, password: str = PASSWORD) -> str:
    """Post the login form and return where it redirects to."""
    response = client.post(
        reverse("login"), {"username": username, "password": password}
    )
    return str(response.headers.get("Location", ""))


def test_login_page_renders(client: Client) -> None:
    """The sign-in page uses the login template."""
    response = client.get(reverse("login"))

    assert response.status_code == 200
    assert any(
        template.name == "registration/login.html" for template in response.templates
    )


def test_manager_lands_on_overview(client: Client, manager: Employee) -> None:
    """Managers are taken to the operations overview."""
    with_password(manager)

    assert sign_in(client, "manager") == reverse("employees:dashboard")


def test_other_employees_land_on_home_page(
    client: Client, make_employee: Callable[..., Employee]
) -> None:
    """Employees without manager access go to the home page."""
    with_password(make_employee("priya"))

    assert sign_in(client, "priya") == reverse("intake:form_intake")


def test_wrong_password_is_refused(client: Client, manager: Employee) -> None:
    """A wrong password shows the error and does not sign in."""
    with_password(manager)

    response = client.post(
        reverse("login"), {"username": "manager", "password": "wrong-password"}
    )

    assert response.status_code == 200
    assert b"not recognised" in response.content
    assert "_auth_user_id" not in client.session


def test_manager_pages_send_visitors_to_login(client: Client) -> None:
    """Signed-out visitors are sent to the sign-in page, not the admin."""
    response = client.get(reverse("employees:dashboard"))

    assert response.status_code == 302
    assert str(response.headers["Location"]).startswith(reverse("login"))


def test_sign_out_returns_to_login(manager_client: Client) -> None:
    """Signing out ends the session and goes back to the sign-in page."""
    response = manager_client.post(reverse("logout"))

    assert response.headers["Location"] == reverse("login")
    assert "_auth_user_id" not in manager_client.session


def test_login_page_shows_site_branding_name(client: Client) -> None:
    """The page shows the configured site name, not the host name."""
    response = client.get(reverse("login"))

    assert b"<title>Sign in \xc2\xb7 Project</title>" in response.content
