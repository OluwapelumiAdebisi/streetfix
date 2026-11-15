"""Figures for a department manager's operations overview."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from .organisation_models import Department, Employee
from .work_models import WorkAssignment, WorkItem

WAITING_TOO_LONG = timedelta(days=7)
PAUSED = ("AWAITING_INFORMATION", "AWAITING_PARTS", "ON_HOLD")
ENDED = ("CLOSED", "CANCELLED")


@dataclass(frozen=True)
class Stage:
    """A labelled count, optionally linked, with a tone for exceptions."""

    label: str
    count: int
    url_name: str | None = None
    tone: str = ""


@dataclass(frozen=True)
class WorkforceRow:
    """What one employee is doing right now."""

    employee: Employee
    open_jobs: int
    case_officer_jobs: int
    closed_today: int
    working_on: WorkItem | None

    @property
    def state(self) -> str:
        """Return working, assigned or free, for the status dot."""
        if self.working_on is not None:
            return "working"
        return "assigned" if self.open_jobs else "free"

    @property
    def progress(self) -> int:
        """Return the share of today's jobs that are closed, as a percentage."""
        total = self.closed_today + self.open_jobs
        return round(100 * self.closed_today / total) if total else 0


def _start_of_today() -> datetime:
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def _department_work(
    department: Department, *, with_case_officer: bool | None = None
) -> QuerySet[WorkItem]:
    """Return the department's work, optionally by whether it has a case officer."""
    work = WorkItem.objects.filter(issue_type__department=department)
    if with_case_officer is None:
        return work
    has_case_officer = Exists(
        WorkAssignment.objects.filter(
            work_item=OuterRef("pk"),
            is_case_officer=True,
            unassigned_at__isnull=True,
        )
    )
    return work.filter(has_case_officer if with_case_officer else ~has_case_officer)


def _unassigned(department: Department) -> QuerySet[WorkItem]:
    """Return triaged, unfinished work with no case officer."""
    return _department_work(department, with_case_officer=False).exclude(
        status__code__in=ENDED + ("SUBMITTED",)
    )


def needs_case_officer_count(department: Department) -> int:
    """Count triaged work waiting for a case officer."""
    return _unassigned(department).filter(status__code="TRIAGED").count()


def urgent_unassigned(department: Department, limit: int = 5) -> list[WorkItem]:
    """Return critical or emergency work with no case officer, oldest first."""
    return list(
        _unassigned(department)
        .filter(Q(priority__code="CRITICAL") | Q(urgency__code="EMERGENCY"))
        .select_related("issue_type", "priority", "urgency")
        .order_by("created_at")[:limit]
    )


def job_flow(department: Department) -> list[Stage]:
    """Count the department's jobs at each stage, left to right."""
    work = _department_work(department)
    return [
        Stage("Awaiting triage", work.filter(status__code="SUBMITTED").count()),
        Stage(
            "Needs a case officer",
            needs_case_officer_count(department),
            "employees:dispatch",
        ),
        Stage(
            "Assigned",
            work.filter(status__code="ASSIGNED").count(),
            "employees:dispatch",
        ),
        Stage("In progress", work.filter(status__code="IN_PROGRESS").count()),
        Stage("Paused", work.filter(status__code__in=PAUSED).count()),
        Stage("Resolved", work.filter(status__code="RESOLVED").count()),
        Stage(
            "Closed today",
            work.filter(status__code="CLOSED", ended_at__gte=_start_of_today()).count(),
        ),
    ]


def needs_attention(department: Department) -> list[Stage]:
    """Count the exceptions a manager should look at."""
    work = _department_work(department).exclude(status__code__in=ENDED)
    unassigned = _unassigned(department)
    return [
        Stage(
            "Critical or emergency with no case officer",
            unassigned.filter(
                Q(priority__code="CRITICAL") | Q(urgency__code="EMERGENCY")
            ).count(),
            "employees:dispatch",
            "danger",
        ),
        Stage(
            "Waiting over a week for a case officer",
            unassigned.filter(created_at__lt=timezone.now() - WAITING_TOO_LONG).count(),
            "employees:dispatch",
            "warning",
        ),
        Stage(
            "Paused (information, parts or on hold)",
            work.filter(status__code__in=PAUSED).count(),
            tone="warning",
        ),
        Stage(
            "Resolved, waiting to be closed",
            work.filter(status__code="RESOLVED").count(),
            tone="warning",
        ),
    ]


def workforce(department: Department) -> list[WorkforceRow]:
    """List the department's active employees and their current work."""
    open_rows = Q(
        work_assignments__unassigned_at__isnull=True,
    ) & ~Q(work_assignments__work_item__status__code__in=ENDED)
    employees = (
        Employee.objects.filter(department=department, user__is_active=True)
        .annotate(
            open_jobs=Count("work_assignments", filter=open_rows),
            case_officer_jobs=Count(
                "work_assignments",
                filter=open_rows & Q(work_assignments__is_case_officer=True),
            ),
            closed_today=Count(
                "work_assignments",
                filter=Q(
                    work_assignments__is_case_officer=True,
                    work_assignments__work_item__status__code="CLOSED",
                    work_assignments__work_item__ended_at__gte=_start_of_today(),
                ),
            ),
        )
        .order_by("-open_jobs", "name")
    )
    in_progress = {
        row.employee_id: row.work_item
        for row in WorkAssignment.objects.filter(
            employee__in=employees,
            unassigned_at__isnull=True,
            work_item__status__code="IN_PROGRESS",
        ).select_related("work_item__issue_type", "work_item__status")
    }
    return [
        WorkforceRow(
            employee=employee,
            open_jobs=employee.open_jobs,
            case_officer_jobs=employee.case_officer_jobs,
            closed_today=employee.closed_today,
            working_on=in_progress.get(employee.pk),
        )
        for employee in employees
    ]
