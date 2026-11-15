"""Provide views and URL configuration for testing custom error handlers."""

from typing import NoReturn

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpRequest
from django.urls import include, path
from global_login_required import login_not_required


@login_not_required  # type: ignore[untyped-decorator]
def trigger_400(request: HttpRequest) -> NoReturn:
    """Trigger an intentional 400 error for testing."""
    raise SuspiciousOperation("Intentional 400 to test the error handler.")


@login_not_required  # type: ignore[untyped-decorator]
def trigger_403(request: HttpRequest) -> NoReturn:
    """Trigger an intentional 403 error for testing."""
    raise PermissionDenied("Intentional 403 to test the error handler.")


@login_not_required  # type: ignore[untyped-decorator]
def trigger_404(request: HttpRequest) -> NoReturn:
    """Trigger an intentional 404 error for testing."""
    raise Http404("Intentional 404 to test the error handler.")


@login_not_required  # type: ignore[untyped-decorator]
def trigger_500(request: HttpRequest) -> NoReturn:
    """Trigger an intentional 500 error for testing."""
    raise RuntimeError("Intentional 500 to test the error handler.")


urlpatterns = [
    path("", include("config.urls")),
    path("400/", trigger_400),
    path("403/", trigger_403),
    path("404/", trigger_404),
    path("500/", trigger_500),
]

handler400 = "config.error_handlers.handler400"
handler403 = "config.error_handlers.handler403"
handler404 = "config.error_handlers.handler404"
handler500 = "config.error_handlers.handler500"
