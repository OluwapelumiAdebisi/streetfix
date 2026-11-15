"""Forms for the employees application."""

from typing import Any

from django import forms

from .organisation_models import Employee
from .work_models import WorkItem


class AssignWorkForm(forms.Form):
    """Choose who to put on a work item and in what role."""

    ROLE_CHOICES = (
        ("case_officer", "Case officer (responsible for the job)"),
        ("support", "Support"),
    )

    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        empty_label="Choose an employee",
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        initial="case_officer",
        widget=forms.RadioSelect,
    )
    reason = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.TextInput(attrs={"placeholder": "Optional, e.g. Priya off sick"}),
    )

    def __init__(self, *args: Any, work_item: WorkItem, **kwargs: Any) -> None:
        """Limit choices to active employees in the responsible department."""
        super().__init__(*args, **kwargs)
        employee_field = self.fields["employee"]
        assert isinstance(employee_field, forms.ModelChoiceField)  # noqa: S101
        employee_field.queryset = Employee.objects.filter(
            department_id=work_item.issue_type.department_id,
            user__is_active=True,
        )

    @property
    def as_case_officer(self) -> bool:
        """Return whether the chosen role is case officer."""
        return bool(self.cleaned_data["role"] == "case_officer")


class RemoveFromWorkForm(forms.Form):
    """Take someone off a work item, with an optional reason."""

    assignment = forms.IntegerField(widget=forms.HiddenInput)
    reason = forms.CharField(required=False, max_length=500)
