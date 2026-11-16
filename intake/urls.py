"""URL configuration for the intake application.

This module defines URL patterns for the intake app,
including the main form intake view and the public report chat.
"""

from django.urls import path

from .views import (
    CreateReportView,
    FormIntakeView,
    NearbyReportView,
    ReportChatView,
    ReportStatusView,
)

app_name = "intake"

urlpatterns = [
    path("", FormIntakeView.as_view(), name="form_intake"),
    path("report/", ReportChatView.as_view(), name="report_chat"),
    path("api/cases/", CreateReportView.as_view(), name="create_report"),
    path("api/cases/nearby/", NearbyReportView.as_view(), name="nearby_report"),
    path(
        "api/cases/<str:reference>/",
        ReportStatusView.as_view(),
        name="report_status",
    ),
]
