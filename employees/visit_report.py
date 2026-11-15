"""The officer's completion report: form, answer lists and checks.

The visit report table holds the main answers. The rest of the form
(further work, health and safety, confirmations) is kept in the report's
``extra_answers`` so no new tables are needed.
"""

import re
from typing import Any

from django import forms

from .forms import PhotoField
from .work_models import Priority, WorkItemPhoto, WorkItemReport

Outcome = WorkItemReport.Outcome

# Outcomes that need the further work section filled in.
FURTHER_WORK_OUTCOMES = {Outcome.TEMPORARY_FIX, Outcome.FURTHER_WORK, Outcome.NO_ACCESS}
# Outcomes where the officer must say why the job wasn't finished.
UNFINISHED_OUTCOMES = {Outcome.TEMPORARY_FIX, Outcome.NO_ACCESS}

FURTHER_REASONS = (
    "The original issue was more serious than initially reported",
    "Additional damage was discovered",
    "Specialist assistance is required",
    "Do not have the necessary equipment or materials",
    "The problem requires additional repairs",
    "The issue has reoccurred",
    "The original job description was inaccurate",
    "A follow-up visit is required",
    "The work cannot be completed within the available time",
    "Health and safety concern",
)

HAZARDS = (
    "Structural damage",
    "Electrical hazard",
    "Flooding or water damage",
    "Potential fire hazard",
    "Unsafe working environment",
    "Risk to members of the public",
    "Risk to employees",
    "Hazardous materials",
    "Other significant safety concern",
)

CONFIRMATIONS = (
    ("confirm_accurate", "The information provided is accurate"),
    ("confirm_recorded", "The work carried out has been recorded correctly"),
    ("confirm_outstanding", "Outstanding issues have been identified"),
    ("confirm_photos", "Required photographic evidence has been uploaded"),
    ("confirm_safety", "Any health and safety concerns have been reported"),
)

PHOTO_EXCEPTION_MIN_LENGTH = 15
VAGUE_WORK = re.compile(
    r"^(the\s+)?(job|work|task)?\s*(is\s+)?(done|complete|completed|fixed|sorted"
    r"|ok|okay|finished|all good|repaired)[.!\s]*$",
    re.IGNORECASE,
)

YES_NO = (("1", "Yes"), ("0", "No"))
YES_NO_FIELDS = (
    "additional_found",
    "outstanding",
    "further_specialist",
    "further_urgent",
    "safety_immediate",
)


def _text(**kwargs: Any) -> forms.CharField:
    return forms.CharField(required=False, max_length=4000, **kwargs)


def _yes_no() -> forms.ChoiceField:
    return forms.ChoiceField(choices=YES_NO, required=False, widget=forms.RadioSelect)


def _ticks(options: tuple[str, ...]) -> forms.MultipleChoiceField:
    return forms.MultipleChoiceField(
        choices=[(option, option) for option in options],
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class VisitReportForm(forms.ModelForm):  # type: ignore[type-arg]
    """The completion report, saved as a draft each time it is sent."""

    actions = _text()
    resolved = forms.ChoiceField(
        choices=(("yes", "Yes"), ("partly", "Partly"), ("no", "No")),
        required=False,
        widget=forms.RadioSelect,
    )
    additional_found = _yes_no()
    additional_text = _text()
    outstanding = _yes_no()
    outstanding_text = _text()
    further_reasons = _ticks(FURTHER_REASONS)
    further_explanation = _text()
    further_why_not = _text()
    further_next_steps = _text()
    further_suggested_priority = forms.ChoiceField(choices=(), required=False)
    further_specialist = _yes_no()
    further_specialist_text = _text()
    further_equipment = _text()
    further_urgent = _yes_no()
    further_site_safe = forms.ChoiceField(
        choices=(("yes", "Yes"), ("no", "No")),
        required=False,
        widget=forms.RadioSelect,
    )
    safety_report = forms.BooleanField(required=False)
    safety_hazards = _ticks(HAZARDS)
    safety_description = _text()
    safety_immediate = _yes_no()
    photo_exception = _text()
    confirm_accurate = forms.BooleanField(required=False)
    confirm_recorded = forms.BooleanField(required=False)
    confirm_outstanding = forms.BooleanField(required=False)
    confirm_photos = forms.BooleanField(required=False)
    confirm_safety = forms.BooleanField(required=False)
    photo = PhotoField()

    EXTRA_FIELDS = (
        "actions",
        "resolved",
        "additional_found",
        "additional_text",
        "outstanding",
        "outstanding_text",
        "further_reasons",
        "further_explanation",
        "further_why_not",
        "further_next_steps",
        "further_suggested_priority",
        "further_specialist",
        "further_specialist_text",
        "further_equipment",
        "further_urgent",
        "further_site_safe",
        "safety_report",
        "safety_hazards",
        "safety_description",
        "safety_immediate",
        "photo_exception",
        *(name for name, _ in CONFIRMATIONS),
    )

    class Meta:
        """Answers kept in the visit report table's own columns."""

        model = WorkItemReport
        fields = ("outcome", "findings", "work_done", "materials")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Fill in earlier answers and the priority choices."""
        super().__init__(*args, **kwargs)
        priority = self.fields["further_suggested_priority"]
        assert isinstance(priority, forms.ChoiceField)  # noqa: S101
        priority.choices = [("", "Choose…")] + [
            (option.code, option.label) for option in Priority.objects.all()
        ]
        saved = self.instance.extra_answers or {}
        for name in self.EXTRA_FIELDS:
            value = saved.get(name)
            if name in YES_NO_FIELDS and value is not None:
                value = "1" if value else "0"
            if value is not None:
                self.initial[name] = value

    def answer(self, name: str) -> Any:
        """Return a cleaned answer, with yes/no as true, false or None."""
        value = self.cleaned_data.get(name)
        if name in YES_NO_FIELDS:
            return None if value in (None, "") else value == "1"
        return value

    @property
    def needs_further_work(self) -> bool:
        """Return whether the further work section applies."""
        return bool(
            self.cleaned_data.get("outcome") in FURTHER_WORK_OUTCOMES
            or self.answer("outstanding")
            or self.answer("additional_found")
        )

    def save(self, commit: bool = True) -> WorkItemReport:
        """Keep the extra answers alongside the report."""
        report: WorkItemReport = super().save(commit=False)
        report.extra_answers = {name: self.answer(name) for name in self.EXTRA_FIELDS}
        report.further_work_needed = self.needs_further_work
        if commit:
            report.save()
        return report

    def problems(self, report: WorkItemReport) -> list[str]:
        """Return everything that must be fixed before submitting."""
        data = self.cleaned_data
        errors: list[str] = []

        def short(name: str, length: int) -> bool:
            return len((data.get(name) or "").strip()) < length

        outcome = data.get("outcome")
        if not outcome:
            return ["Select a job outcome."]
        if short("findings", 10):
            errors.append("Describe the original issue you found.")
        work = (data.get("work_done") or "").strip()
        if VAGUE_WORK.match(work) or len(work.split()) < 6 or len(work) < 25:
            errors.append(
                "Work carried out: be specific (at least 6 words). "
                '"Job completed" is not accepted.'
            )
        if short("materials", 2):
            errors.append('List materials/equipment used (or "None").')
        if not data.get("resolved"):
            errors.append("Was the original problem resolved?")
        for name, question, detail in (
            (
                "additional_found",
                "Were additional problems discovered?",
                "Describe the additional problems.",
            ),
            (
                "outstanding",
                "Is there outstanding work?",
                "Describe the outstanding work.",
            ),
        ):
            if self.answer(name) is None:
                errors.append(question)
            elif self.answer(name) and short(f"{name.split('_')[0]}_text", 10):
                errors.append(detail)
        if self.needs_further_work:
            errors += self._further_work_problems(outcome)
        if data.get("safety_report"):
            if not data.get("safety_hazards"):
                errors.append("H&S: choose the hazard type.")
            if short("safety_description", 10):
                errors.append("H&S: describe the hazard.")
            if self.answer("safety_immediate") is None:
                errors.append("H&S: is immediate intervention required?")
        errors += self._photo_problems(report, outcome)
        if not all(data.get(name) for name, _ in CONFIRMATIONS):
            errors.append("Tick all five confirmations.")
        return errors

    def _further_work_problems(self, outcome: str) -> list[str]:
        data = self.cleaned_data
        errors = []

        def short(name: str, length: int) -> bool:
            return len((data.get(name) or "").strip()) < length

        if not data.get("further_reasons"):
            errors.append("Further work: choose a reason.")
        if short("further_explanation", 20):
            errors.append("Further work: explain the issue in detail.")
        if outcome in UNFINISHED_OUTCOMES and short("further_why_not", 10):
            errors.append("Further work: why could it not be completed?")
        if short("further_next_steps", 10):
            errors.append("Further work: recommend next steps.")
        if not data.get("further_suggested_priority"):
            errors.append("Further work: suggest a priority.")
        if self.answer("further_specialist") is None:
            errors.append("Further work: specialist assistance needed?")
        if self.answer("further_urgent") is None:
            errors.append("Further work: is it urgent?")
        site_safe = data.get("further_site_safe")
        if not site_safe:
            errors.append("Further work: was the site left safe?")
        elif site_safe == "no" and not data.get("safety_report"):
            errors.append("Site not left safe — complete the Health & Safety section.")
        return errors

    def _photo_problems(self, report: WorkItemReport, outcome: str) -> list[str]:
        tags = set(report.photos.values_list("tag", flat=True))
        excused = (
            len((self.cleaned_data.get("photo_exception") or "").strip())
            >= PHOTO_EXCEPTION_MIN_LENGTH
        )
        if excused:
            return []
        if outcome == Outcome.FIXED and WorkItemPhoto.Tag.AFTER not in tags:
            return ["Add an AFTER photo — or give a photo exception reason."]
        if not tags:
            return [
                "Add a photo of the circumstances, "
                "or explain why you could not take one."
            ]
        return []
