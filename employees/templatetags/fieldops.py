"""Template tags for the priority and status chips on employee pages."""

from django import template
from django.utils.html import format_html
from django.utils.safestring import SafeString

from employees.work_models import Priority, WorkItem

register = template.Library()

PRIORITY_COLOURS = {
    "CRITICAL": "#d92d20",
    "HIGH": "#c27c00",
    "NORMAL": "#2563eb",
    "LOW": "#64748b",
}

# Status codes mapped onto the stylesheet's status colours.
STATUS_STYLES = {
    "SUBMITTED": "triage",
    "TRIAGED": "ready",
    "ASSIGNED": "assigned",
    "IN_PROGRESS": "in_progress",
    "AWAITING_INFORMATION": "requires_attention",
    "AWAITING_PARTS": "requires_attention",
    "ON_HOLD": "requires_attention",
    "RESOLVED": "completed",
    "CLOSED": "completed",
    "CANCELLED": "cancelled",
}


@register.simple_tag
def priority(option: Priority | None) -> SafeString | str:
    """Render a priority as a coloured chip."""
    if option is None:
        return ""
    return format_html(
        '<span class="priority" style="--c:{}">{}</span>',
        PRIORITY_COLOURS.get(option.code, "#64748b"),
        option.label,
    )


@register.simple_tag
def status(work_item: WorkItem) -> SafeString:
    """Render a work item's status as a coloured chip."""
    return format_html(
        '<span class="status s-{}">{}</span>',
        STATUS_STYLES.get(work_item.status.code, ""),
        work_item.status.label,
    )


# Officer steps mapped onto the phone stylesheet's status colours.
OFFICER_STEPS = ("assigned", "arrived", "in_progress")


@register.simple_tag
def officer_status(work_item: WorkItem) -> SafeString:
    """Render where the officer is with a job as a coloured chip.

    Arrived is the officer's own step rather than a work item status, so
    it is named here; the others show the status label from the admin.
    """
    step = getattr(work_item, "next_step", "")
    style = step if step in OFFICER_STEPS else ""
    label = "Arrived" if step == "arrived" else work_item.status.label
    return format_html('<span class="st s-{}">{}</span>', style, label)


@register.filter
def minutes(value: float | None) -> str:
    """Show a number of minutes as "45 min" or "1h 05m"."""
    total = round(value or 0)
    if total < 60:
        return f"{total} min"
    return f"{total // 60}h {total % 60:02d}m"
