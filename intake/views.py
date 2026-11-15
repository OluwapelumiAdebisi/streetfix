"""Views for the intake application.

This module contains views for handling form intake processes
and related functionality.
"""

from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from global_login_required import login_not_required


@method_decorator(login_not_required, name="dispatch")
class FormIntakeView(TemplateView):
    """View for the form intake landing page.

    Displays the main intake form or dashboard for submitting
    and managing form submissions.
    """

    template_name = "intake/form_intake.html"
