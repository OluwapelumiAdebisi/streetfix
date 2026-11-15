"""Tests for the dispatch pages and operations."""

from collections.abc import Callable

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from employees.dispatch import assign_work, dispatchable_work, remove_from_work
from employees.organisation_models import Employee
from employees.work_models import (
    Priority,
    WorkAssignment,
    WorkItem,
    WorkItemStatus,
)

pytestmark = pytest.mark.django_db

MakeEmployee = Callable[..., Employee]
MakeWorkItem = Callable[..., WorkItem]


def set_status(item: WorkItem, code: str) -> WorkItem:
    """Move a work item to a status directly, for test setup."""
    item.status = WorkItemStatus.objects.get(code=code)
    item.save(update_fields=("status",))
    return item


@pytest.fixture
def triaged(make_work_item: MakeWorkItem) -> MakeWorkItem:
    """Provide a factory for triaged work items."""

    def make(**kwargs: object) -> WorkItem:
        return set_status(make_work_item(**kwargs), "TRIAGED")

    return make


def open_rows(item: WorkItem) -> list[WorkAssignment]:
    """Return the work item's current assignments."""
    return list(item.assignments.filter(unassigned_at__isnull=True))


# Operations


def test_assigning_case_officer_marks_triaged_work_assigned(
    triaged: MakeWorkItem, make_employee: MakeEmployee, manager: Employee
) -> None:
    """The first case officer moves the job to Assigned, with history."""
    item = triaged()
    officer = make_employee("priya")

    assign_work(item, officer, case_officer=True, dispatcher=manager)
    item.refresh_from_db()

    assert item.status.code == "ASSIGNED"
    last_change = item.status_history.last()
    assert last_change is not None
    assert last_change.changed_by == manager


def test_adding_support_does_not_change_status(
    triaged: MakeWorkItem, make_employee: MakeEmployee, manager: Employee
) -> None:
    """Support alone does not make a job assigned."""
    item = triaged()

    assign_work(item, make_employee("dan"), case_officer=False, dispatcher=manager)
    item.refresh_from_db()

    assert item.status.code == "TRIAGED"


def test_cannot_assign_untriaged_work(
    make_work_item: MakeWorkItem, make_employee: MakeEmployee, manager: Employee
) -> None:
    """Submitted work must be triaged first."""
    with pytest.raises(ValidationError):
        assign_work(
            make_work_item(),
            make_employee("priya"),
            case_officer=True,
            dispatcher=manager,
        )


def test_cannot_assign_other_department(
    triaged: MakeWorkItem, make_employee: MakeEmployee, manager: Employee
) -> None:
    """Only the responsible department's employees can be assigned."""
    with pytest.raises(ValidationError):
        assign_work(
            triaged(),
            make_employee("lee", department="Parks"),
            case_officer=True,
            dispatcher=manager,
        )


def test_removing_last_case_officer_returns_work_to_triaged(
    triaged: MakeWorkItem, make_employee: MakeEmployee, manager: Employee
) -> None:
    """Work with nobody responsible shows up as needing someone again."""
    item = triaged()
    row = assign_work(
        item, make_employee("priya"), case_officer=True, dispatcher=manager
    )

    remove_from_work(row, dispatcher=manager, reason="Off sick")
    item.refresh_from_db()

    assert item.status.code == "TRIAGED"
    assert open_rows(item) == []


def test_dispatchable_work_is_departmental_and_most_pressing_first(
    triaged: MakeWorkItem, make_work_item: MakeWorkItem, manager: Employee
) -> None:
    """Other departments, untriaged and closed work are left out."""
    normal = triaged()
    critical = triaged()
    critical.priority = Priority.objects.get(code="CRITICAL")
    critical.save(update_fields=("priority",))
    triaged(issue_code="TREE", department="Parks")
    make_work_item()
    set_status(make_work_item(), "CLOSED")

    work = list(dispatchable_work(manager.department))

    assert work == [critical, normal]


# Pages


def test_dispatch_requires_sign_in(client: Client) -> None:
    """Anonymous visitors are sent to sign in."""
    response = client.get(reverse("employees:dispatch"))

    assert response.status_code == 302


def test_dispatch_requires_permission(
    client: Client, make_employee: MakeEmployee
) -> None:
    """Employees without the assign permission are refused."""
    client.force_login(make_employee("priya").user)

    response = client.get(reverse("employees:dispatch"))

    assert response.status_code == 403


def test_dispatch_list_splits_unassigned_and_assigned(
    manager_client: Client,
    triaged: MakeWorkItem,
    make_employee: MakeEmployee,
    manager: Employee,
) -> None:
    """The list shows what needs a case officer and what has one."""
    waiting = triaged()
    done = triaged()
    assign_work(done, make_employee("priya"), case_officer=True, dispatcher=manager)

    response = manager_client.get(reverse("employees:dispatch"))

    assert response.status_code == 200
    assert response.context["unassigned"] == [waiting]
    assert response.context["assigned"] == [done]
    assert b"Priya" in response.content


def test_sidebar_counts_jobs_needing_a_case_officer(
    manager_client: Client, triaged: MakeWorkItem
) -> None:
    """The manager sidebar links to Dispatch with the waiting count."""
    triaged()
    triaged()

    response = manager_client.get(reverse("employees:dispatch"))

    assert response.context["needs_case_officer"] == 2
    assert response.context["active"] == "dispatch"


def test_assign_page_assigns_case_officer(
    manager_client: Client, triaged: MakeWorkItem, make_employee: MakeEmployee
) -> None:
    """Posting the form puts the employee on the job."""
    item = triaged()
    officer = make_employee("priya")
    url = reverse("employees:dispatch_detail", args=[item.pk])

    response = manager_client.post(
        url, {"employee": officer.pk, "role": "case_officer", "reason": ""}
    )

    assert response.status_code == 302
    rows = open_rows(item)
    assert [(row.employee, row.is_case_officer) for row in rows] == [(officer, True)]


def test_assign_page_only_offers_department_employees(
    manager_client: Client, triaged: MakeWorkItem, make_employee: MakeEmployee
) -> None:
    """Employees from other departments cannot be chosen."""
    item = triaged()
    outsider = make_employee("lee", department="Parks")
    url = reverse("employees:dispatch_detail", args=[item.pk])

    response = manager_client.post(
        url, {"employee": outsider.pk, "role": "case_officer"}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["employee"]
    assert open_rows(item) == []


def test_remove_button_takes_employee_off(
    manager_client: Client,
    triaged: MakeWorkItem,
    make_employee: MakeEmployee,
    manager: Employee,
) -> None:
    """The remove button closes the assignment with its reason."""
    item = triaged()
    row = assign_work(
        item, make_employee("priya"), case_officer=True, dispatcher=manager
    )
    url = reverse("employees:dispatch_detail", args=[item.pk])

    manager_client.post(url, {"remove": "", "assignment": row.pk, "reason": "Off sick"})
    row.refresh_from_db()

    assert not row.is_open
    assert row.reason == "Off sick"


def test_other_department_work_is_not_found(
    manager_client: Client, triaged: MakeWorkItem
) -> None:
    """Dispatchers cannot open another department's job."""
    item = triaged(issue_code="TREE", department="Parks")

    response = manager_client.get(reverse("employees:dispatch_detail", args=[item.pk]))

    assert response.status_code == 404
