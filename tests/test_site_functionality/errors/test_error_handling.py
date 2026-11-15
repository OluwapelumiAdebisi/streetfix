"""Testing for the project custom error handlers."""

import pytest
from django.test import Client
from django.utils.html import escape

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("test_url_path"),
]

# Handlers return correct status codes


@pytest.mark.parametrize(
    ("error_path", "expected_status"),
    [
        ("400", 400),
        ("403", 403),
        ("404", 404),
        ("500", 500),
    ],
)
def test_error_handler_returns_expected_status(
    error_path: str,
    expected_status: int,
) -> None:
    """Test that each error handler returns its expected status code."""
    # Use Client directly so 500 response can be inspected.
    response = Client(raise_request_exception=False).get(f"/{error_path}/")

    assert response.status_code == expected_status


# Error pages are rendered with correct content


@pytest.mark.parametrize(
    ("error_path", "status_code", "title", "message"),
    [
        (
            "400",
            "400",
            "Bad Request",
            "The request sent to the server was invalid or malformed.",
        ),
        (
            "403",
            "403",
            "Access Denied",
            "You do not have permission to view this resource.",
        ),
        (
            "path-that-doesn't-exist",
            "404",
            "Page Not Found",
            "The page you are looking for doesn't exist or has been moved.",
        ),
        (
            "500",
            "500",
            "Server Error",
            "Something went wrong on our server. Please try again later.",
        ),
    ],
)
def test_error_pages_display_correct_content(
    error_path: str,
    status_code: str,
    title: str,
    message: str,
) -> None:
    """Test that each error page displays its expected content."""
    response = Client(raise_request_exception=False).get(f"/{error_path}/")

    content = response.content.decode()

    assert status_code in content
    assert title in content
    assert escape(message) in content
    assert response.context["message"] == message
