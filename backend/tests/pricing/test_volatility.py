"""Volatility from Google's price history, and the bins it assigns."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.services.pricing_etl import volatility as v

END = date(2026, 10, 19)


def _flat(merchant, cents, start=date(2025, 10, 20)):
    return [v.Point(merchant, start, cents)]


# --- as_of: what the stores were charging on a day -------------------------------


def test_as_of_takes_each_stores_latest_change_then_the_median():
    points = [
        v.Point("Newegg", date(2026, 10, 11), 38900),
        v.Point("Newegg", date(2026, 10, 12), 34800),
        v.Point("Best Buy", date(2026, 10, 1), 42000),
        v.Point("Walmart", date(2026, 9, 24), 41599),
    ]
    assert v.as_of(points, date(2026, 10, 12)) == 41599  # median of 348 / 420 / 415.99
    assert (
        v.as_of(points, date(2026, 10, 11)) == 41599
    )  # Newegg at 389, still the median store
    assert v.as_of(points, date(2026, 9, 1)) is None  # no store had a price yet


def test_as_of_with_two_stores_rounds_half_up():
    points = [v.Point("A", date(2026, 1, 1), 100), v.Point("B", date(2026, 1, 1), 101)]
    assert v.as_of(points, date(2026, 2, 1)) == 101


def test_last_change_is_the_most_recent_on_or_before_the_day():
    points = [v.Point("A", date(2026, 10, 1), 1), v.Point("B", date(2026, 10, 9), 2)]
    assert v.last_change_on_or_before(points, date(2026, 10, 5)) == date(2026, 10, 1)
    assert v.last_change_on_or_before(points, date(2026, 10, 9)) == date(2026, 10, 9)
    assert v.last_change_on_or_before(points, date(2026, 9, 1)) is None


# --- volatility ------------------------------------------------------------------


def test_a_price_that_never_moves_has_zero_volatility():
    vol, n = v.volatility(_flat("A", 40000) + _flat("B", 41000), END)
    assert vol == 0.0
    assert n == v.VOL_WEEKS


def test_a_price_swinging_every_week_is_volatile():
    points = []
    for w in range(14):
        day = END - timedelta(weeks=w)
        points.append(v.Point("A", day, 40000 if w % 2 else 44000))
    vol, _ = v.volatility(points, END)
    assert vol == pytest.approx(0.0953, abs=1e-3)  # |ln(44000/40000)| every week


def test_too_little_history_is_unknown_not_zero():
    """A part first listed three weeks ago cannot be called stable."""
    points = [v.Point("A", END - timedelta(weeks=3), 40000)]
    vol, n = v.volatility(points, END)
    assert vol is None
    assert n == 3


def test_volatility_follows_the_median_not_one_stores_flash_sale():
    """One store's one-week dip does not move a three-store median."""
    calm = _flat("A", 40000) + _flat("B", 41000) + _flat("C", 42000)
    sale = calm + [
        v.Point("A", END - timedelta(weeks=4), 30000),
        v.Point("A", END - timedelta(weeks=3), 40000),
    ]
    assert v.volatility(sale, END)[0] == 0.0


def test_sampling_does_not_depend_on_how_often_we_fetch():
    """The grid is weekly whatever the history density, so a daily-fetched
    part and a biweekly one are measured on the same terms."""
    weekly = [
        v.Point("A", END - timedelta(weeks=w), 40000 + 100 * (w % 2)) for w in range(14)
    ]
    daily_noise = weekly + [
        v.Point("A", END - timedelta(weeks=w, days=3), 99999) for w in range(1, 13)
    ]
    # The mid-week points are overwritten by the next week-end's change, so
    # the sampled series (and the volatility) is the same.
    assert v.weekly_series(daily_noise, END) == v.weekly_series(weekly, END)


# --- bins ------------------------------------------------------------------------


def _targets(n, *, unknown=0, bins=None, streaks=None):
    bins = bins or {}
    streaks = streaks or {}
    out = [
        v.TargetVol(
            key=("pc_part", uuid.UUID(int=i)),
            volatility=1.0 / (i + 1),  # i=0 most volatile
            current_bin=bins.get(i, "medium"),
            out_of_top_streak=streaks.get(i, 0),
        )
        for i in range(n)
    ]
    out += [
        v.TargetVol(
            key=("pc_part", uuid.UUID(int=10_000 + j)),
            volatility=None,
            current_bin="medium",
        )
        for j in range(unknown)
    ]
    return out


def _bins(assignments):
    counts = {"high": 0, "medium": 0, "low": 0}
    for a in assignments.values():
        counts[a.bin] += 1
    return counts


def test_five_high_a_hundred_medium_the_rest_low():
    result = v.assign_bins(_targets(170))
    assert _bins(result) == {"high": 5, "medium": 100, "low": 65}
    assert result[("pc_part", uuid.UUID(int=0))].bin == "high"
    assert result[("pc_part", uuid.UUID(int=0))].rank == 1
    assert result[("pc_part", uuid.UUID(int=169))].bin == "low"


def test_unknowns_are_medium_and_take_medium_slots_first():
    """The weekly load stays at 100 however many targets lack history."""
    result = v.assign_bins(_targets(150, unknown=30))
    counts = _bins(result)
    assert counts == {"high": 5, "medium": 100, "low": 75}
    assert all(
        result[("pc_part", uuid.UUID(int=10_000 + j))]
        == v.Assignment("medium", None, 0)
        for j in range(30)
    )


def test_an_incumbent_keeps_high_through_one_quiet_week():
    # Target 7 was high; it now ranks 8th: outside the top 5, inside the top 10.
    result = v.assign_bins(_targets(50, bins={7: "high"}))
    assert result[("pc_part", uuid.UUID(int=7))].bin == "high"
    assert result[("pc_part", uuid.UUID(int=7))].out_of_top_streak == 0
    assert _bins(result)["high"] == 5  # it took a seat; rank 5 waits


def test_an_incumbent_outside_the_top_ten_survives_one_week_then_drops():
    first = v.assign_bins(_targets(50, bins={30: "high"}))
    assert first[("pc_part", uuid.UUID(int=30))] == v.Assignment("high", 31, 1)

    second = v.assign_bins(_targets(50, bins={30: "high"}, streaks={30: 1}))
    assert second[("pc_part", uuid.UUID(int=30))].bin == "medium"


def test_an_incumbent_back_inside_the_top_ten_resets_its_streak():
    result = v.assign_bins(_targets(50, bins={8: "high"}, streaks={8: 1}))
    assert result[("pc_part", uuid.UUID(int=8))] == v.Assignment("high", 9, 0)


def test_ties_are_broken_deterministically():
    same = [
        v.TargetVol(
            key=("pc_part", uuid.UUID(int=i)), volatility=0.0, current_bin="medium"
        )
        for i in range(10)
    ]
    assert v.assign_bins(same) == v.assign_bins(list(reversed(same)))


def test_fewer_targets_than_slots():
    assert _bins(v.assign_bins(_targets(3))) == {"high": 3, "medium": 0, "low": 0}
