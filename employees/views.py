"""Views for the employees application.

This module contains views for employee management,
dashboards, and related functionality.
"""

from typing import Any

from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.views.generic import TemplateView


class EmployeeDashboardView(TemplateView):
    """View for the employee dashboard.

    Displays an overview of employee information, tasks,
    and relevant metrics for employee management.
    """

    template_name = "employees/dashboard.html"


class SignInView(LoginView):
    """Sign employees in; managers land on the operations overview."""

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self) -> str:
        """Send managers to the overview and everyone else to the home page."""
        if self.request.user.has_perm("employees.add_workassignment"):
            return reverse("employees:dashboard")
        return reverse("intake:form_intake")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Use the site's branding name rather than the host name."""
        context = super().get_context_data(**kwargs)
        context.pop("site_name", None)
        return context
