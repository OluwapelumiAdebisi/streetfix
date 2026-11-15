"""Template tags for the manager pages' priority and status chips."""

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
def prio(priority: Priority | None) -> SafeString | str:
    """Render a priority as a coloured chip."""
    if priority is None:
        return ""
    return format_html(
        '<span class="prio" style="--c:{}">{}</span>',
        PRIORITY_COLOURS.get(priority.code, "#64748b"),
        priority.label,
    )


@register.simple_tag
def status(work_item: WorkItem) -> SafeString:
    """Render a work item's status as a coloured chip."""
    return format_html(
        '<span class="status s-{}">{}</span>',
        STATUS_STYLES.get(work_item.status.code, ""),
        work_item.status.label,
    )
