"""Tests for job addresses and travel estimates."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.core.cache import cache

from employees import geo
from employees.work_models import WorkItem

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def birmingham_depot(settings: Any) -> None:
    """Start every day from a known depot."""
    settings.FIELD_DEPOT = {"name": "Depot", "lat": 52.4797, "lng": -1.9026}


def at(item: WorkItem, lat: str, lng: str) -> WorkItem:
    """Move a work item to a location."""
    item.latitude, item.longitude = Decimal(lat), Decimal(lng)
    item.save(update_fields=("latitude", "longitude"))
    return item


def test_distance_between_known_points() -> None:
    """Birmingham to London is roughly 163 km in a straight line."""
    assert geo.distance_km(52.4797, -1.9026, 51.5072, -0.1276) == pytest.approx(
        163, abs=2
    )


def test_day_plan_runs_from_depot_through_each_job(
    make_work_item: Callable[..., WorkItem],
) -> None:
    """Each job's ETA follows the previous job plus time on site."""
    first = at(make_work_item(), "52.4900", "-1.9026")
    second = at(make_work_item(), "52.5000", "-1.9026")

    plan = geo.plan_day([first, second])

    gap = plan.legs[second.pk].eta - plan.legs[first.pk].eta
    assert plan.legs[first.pk].km == pytest.approx(1.15 * geo.ROAD_FACTOR, abs=0.05)
    assert gap.total_seconds() / 60 == pytest.approx(
        geo.ON_SITE_MINUTES + plan.legs[second.pk].travel_minutes
    )
    assert plan.finish is not None
    assert plan.finish > plan.legs[second.pk].eta


def test_day_plan_starts_from_the_current_job(
    make_work_item: Callable[..., WorkItem],
) -> None:
    """When on site, the next job is reached from there, not the depot."""
    current = at(make_work_item(), "52.5000", "-1.9026")
    after = at(make_work_item(), "52.5000", "-1.9026")

    plan = geo.plan_day([current, after], on_site=current)

    assert plan.legs[current.pk].travel_minutes == 0
    assert plan.legs[after.pk].km == 0


def test_empty_day_has_no_finish() -> None:
    """With no jobs there is nothing to estimate."""
    assert geo.plan_day([]).finish is None


def test_address_falls_back_to_coordinates_when_lookups_are_off(
    make_work_item: Callable[..., WorkItem],
) -> None:
    """Tests and offline set-ups show the coordinates instead."""
    item = make_work_item()

    assert geo.street_address(item) == "51.500000, -0.120000"


def test_address_is_looked_up_once_and_cached(
    make_work_item: Callable[..., WorkItem],
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The address service is only asked once per location."""
    settings.REVERSE_GEOCODING = True
    cache.clear()
    calls: list[tuple[float, float]] = []

    def fake_lookup(lat: float, lng: float) -> str:
        calls.append((lat, lng))
        return "Kingstanding Road, Kingstanding, B44 9AA"

    monkeypatch.setattr(geo, "_lookup", fake_lookup)
    item = make_work_item()

    assert geo.street_address(item) == "Kingstanding Road, Kingstanding, B44 9AA"
    assert geo.street_address(item) == "Kingstanding Road, Kingstanding, B44 9AA"
    assert len(calls) == 1


def test_failed_lookup_shows_coordinates(
    make_work_item: Callable[..., WorkItem],
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the address service is down, the page still loads."""
    settings.REVERSE_GEOCODING = True
    cache.clear()

    def broken_lookup(lat: float, lng: float) -> str:
        raise OSError("no network")

    monkeypatch.setattr(geo, "_lookup", broken_lookup)

    assert geo.street_address(make_work_item()) == "51.500000, -0.120000"
