"""Tests for a manager approving or sending back an officer's visit report."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from employees import approval, field_work
from employees.dispatch import assign_work
from employees.organisation_models import Employee
from employees.work_models import (
    WorkItem,
    WorkItemComment,
    WorkItemPhoto,
    WorkItemReport,
    WorkItemStatus,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings: Any, tmp_path: Path) -> None:
    """Keep uploaded test photos out of the project folder."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def officer(make_employee: Callable[..., Employee]) -> Employee:
    """Provide a Roads officer."""
    return make_employee("priya")


@pytest.fixture
def job(
    make_work_item: Callable[..., WorkItem], officer: Employee, manager: Employee
) -> WorkItem:
    """Provide fixed work waiting for the manager's approval."""
    item = make_work_item()
    item.transition_to(WorkItemStatus.objects.get(code="TRIAGED"))
    assign_work(item, officer, case_officer=True, dispatcher=manager)
    item.refresh_from_db()
    report = field_work.arrive(item, officer)
    field_work.add_photo(
        report,
        SimpleUploadedFile("site.jpg", b"fake-jpeg-bytes", content_type="image/jpeg"),
        tag=WorkItemPhoto.Tag.BEFORE,
        employee=officer,
    )
    field_work.start_work(report, officer)
    item.refresh_from_db()
    report.outcome = WorkItemReport.Outcome.FIXED
    report.work_done = "Cut out and filled the pothole with hot asphalt"
    report.save()
    field_work.submit_report(report, officer)
    item.refresh_from_db()
    return item


def test_fixed_work_waits_for_approval(job: WorkItem) -> None:
    """The officer's report leaves fixed work resolved, not closed."""
    assert job.status.code == "RESOLVED"
    assert approval.latest_report(job) is not None


def test_approving_closes_the_job(job: WorkItem, manager: Employee) -> None:
    """Approval closes the job, records who approved it and emails nobody."""
    approval.approve(job, manager, note="Looks good")

    job.refresh_from_db()
    assert job.status.code == "CLOSED"
    assert job.ended_at is not None
    change = job.status_history.last()
    assert change is not None
    assert change.changed_by == manager
    assert change.notes == "Approved by manager: Looks good"
    assert mail.outbox == []


def test_sending_back_reopens_the_report(
    job: WorkItem, manager: Employee, officer: Employee
) -> None:
    """The officer gets the job back with the report as a draft and a note."""
    approval.send_back(job, manager, note="After photo is missing")

    job.refresh_from_db()
    assert job.status.code == "IN_PROGRESS"
    assert field_work.draft_report(job, officer) is not None
    comment = WorkItemComment.objects.get(work_item=job)
    assert comment.author == manager
    assert "After photo is missing" in comment.content


def test_sending_back_needs_a_note(job: WorkItem, manager: Employee) -> None:
    """The officer must be told what to fix."""
    with pytest.raises(ValidationError):
        approval.send_back(job, manager, note="  ")


def test_only_resolved_work_can_be_reviewed(job: WorkItem, manager: Employee) -> None:
    """Closed work cannot be approved again."""
    approval.approve(job, manager)
    job.refresh_from_db()

    with pytest.raises(ValidationError):
        approval.approve(job, manager)


def test_job_page_shows_report_and_review(
    manager_client: Client, job: WorkItem
) -> None:
    """The manager sees the visit report and the review buttons."""
    response = manager_client.get(reverse("employees:dispatch_detail", args=[job.pk]))

    content = response.content.decode()
    assert "Visit report" in content
    assert "Cut out and filled the pothole" in content
    assert "Approve and close" in content


def test_approving_from_the_job_page(manager_client: Client, job: WorkItem) -> None:
    """Approving from the page closes the job and returns to dispatch."""
    response = manager_client.post(
        reverse("employees:dispatch_detail", args=[job.pk]), {"approve": ""}
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("employees:dispatch")
    job.refresh_from_db()
    assert job.status.code == "CLOSED"


def test_sending_back_without_a_note_shows_an_error(
    manager_client: Client, job: WorkItem
) -> None:
    """The page explains why the job was not sent back."""
    response = manager_client.post(
        reverse("employees:dispatch_detail", args=[job.pk]),
        {"send_back": "", "note": ""},
    )

    assert response.status_code == 200
    assert "Say what needs doing" in response.content.decode()
    job.refresh_from_db()
    assert job.status.code == "RESOLVED"
