"""Test authentication, view access, and authentication-specific UI behaviour."""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

# Authentication URL integration


def test_allauth_login_url_is_wired(client: Client) -> None:
    """Test the allauth login URL resolves successfully."""
    response = client.get(reverse("account_login"))

    assert response.status_code == 200


def test_allauth_signup_url_is_wired(client: Client) -> None:
    """Test the allauth signup URL resolves successfully."""
    response = client.get(reverse("account_signup"))

    assert response.status_code == 200


def test_allauth_logout_url_is_wired(client: Client) -> None:
    """Test that the allauth logout URL redirects successfully."""
    response = client.get(reverse("account_logout"))

    assert response.status_code == 302


# Access requirements and redirects


def test_unauthenticated_user_is_redirected_from_protected_view(client: Client) -> None:
    """Test that an unauthenticated user is redirected from a protected view."""
    response = client.get(reverse("employees:dashboard"))

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login/")


@pytest.mark.django_db
def test_authenticated_user_can_access_protected_view(manager_client: Client) -> None:
    """Test that an authenticated user can access a protected view."""
    response = manager_client.get(reverse("employees:dashboard"))

    assert response.status_code == 200


def test_unauthenticated_user_can_access_homepage(client: Client) -> None:
    """Test that the homepage is accessible without authentication."""
    response = client.get(reverse("intake:form_intake"))

    assert response.status_code == 200


# Authentication boundaries


def test_allauth_login_is_not_blocked_by_global_login_required(client: Client) -> None:
    """Test that the login view remains accessible without authentication."""
    response = client.get("/auth/login/")

    assert response.status_code == 200


def test_admin_access_is_handled_by_admin_authentication(
    client: Client,
) -> None:
    """Test that the admin URL is handled by its own authentication."""
    response = client.get("/site-admin/")

    assert response.status_code == 302
    assert "/auth/login/" not in response.headers["Location"]
    assert response.headers["Location"].startswith("/site-admin/login/")
