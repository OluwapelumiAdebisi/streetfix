"""URL configuration for the employees application.

This module defines URL patterns for the employees app,
including the employee dashboard view.
"""

from django.urls import path

from .views import DispatchDetailView, DispatchListView, EmployeeDashboardView

app_name = "employees"

urlpatterns = [
    path("", EmployeeDashboardView.as_view(), name="dashboard"),
    path("dispatch/", DispatchListView.as_view(), name="dispatch"),
    path(
        "dispatch/<int:pk>/",
        DispatchDetailView.as_view(),
        name="dispatch_detail",
    ),
]
