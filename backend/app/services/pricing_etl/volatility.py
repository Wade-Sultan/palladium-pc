"""Volatility from Google's price history, and the bins it decides. Pure.

ONE SOURCE, ONE GRID, FOR EVERY TARGET. Volatility is computed only from
price_history_points (Google's dated per-store price changes, about a year
deep, delivered with every offers fetch), resampled to the same weekly grid
for every target. Two tempting alternatives are wrong in the same way:
  - Our own fetch estimates. A high-bin target is fetched daily and a low-bin
    one every two weeks, so the high one would show day-to-day offer churn the
    low one never could, look more volatile, and stay high because it is high.
  - Carried-forward daily rows. Zero change by construction, so a rarely
    fetched target looks stable because it is rarely fetched.
Google's history has neither problem: its density does not depend on our bin.

THE MEASURE. For each of the last VOL_WEEKS week-ends, the median across stores
of each store's price as of that day (its last change on or before it). Then
the mean absolute log change between consecutive weeks. The cross-store median
is what our own estimate tracks, so this is the volatility of the number we
publish, not of one store's flash sale. Mean rather than median of the changes,
because most weeks show no change at all and a median would tie almost every
part at zero.

BINS, re-ranked weekly over targets with a measurable volatility:
  high    the HIGH_SLOTS most volatile        fetched daily
  medium  the next MEDIUM_SLOTS               weekly
  low     everything else                     every two weeks
A target with too little history to measure is "unknown" and sits in medium
(it is fetched soon anyway, and its first fetch brings the history). Unknowns
take medium slots first, so the weekly load stays at MEDIUM_SLOTS.

HYSTERESIS on high only, the bin that costs a search a day: a high target keeps
its place while it ranks within HIGH_KEEP_RANK, and is demoted only after
HIGH_DEMOTE_STREAK consecutive weekly rankings outside it. One quiet week does
not bounce it, and the high bin can hold more than HIGH_SLOTS only through such
incumbents, never through new entries.
"""

from __future__ import annotations

import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

VOL_WEEKS = 12
# Below this many consecutive week-to-week changes, a target is "unknown".
MIN_CHANGES = 4

HIGH_SLOTS = 5
MEDIUM_SLOTS = 100
HIGH_KEEP_RANK = 10
HIGH_DEMOTE_STREAK = 2

BIN_INTERVALS = {
    "high": timedelta(days=1),
    "medium": timedelta(days=7),
    "low": timedelta(days=14),
}


@dataclass(frozen=True)
class Point:
    merchant: str
    day: date
    cents: int


def as_of(points: list[Point], day: date) -> int | None:
    """Median across stores of each store's latest price on or before `day`.
    None when no store had a price yet."""
    latest: dict[str, tuple[date, int]] = {}
    for p in points:
        if p.day <= day:
            held = latest.get(p.merchant)
            if held is None or p.day >= held[0]:
                latest[p.merchant] = (p.day, p.cents)
    if not latest:
        return None
    return math.floor(statistics.median(c for _, c in latest.values()) + 0.5)


def last_change_on_or_before(points: list[Point], day: date) -> date | None:
    """The most recent change any store made on or before `day`: when the
    as-of price was last updated."""
    days = [p.day for p in points if p.day <= day]
    return max(days) if days else None


def weekly_series(
    points: list[Point], end: date, weeks: int = VOL_WEEKS
) -> list[int | None]:
    """as_of at each of `weeks + 1` week-ends ending at `end`, oldest first."""
    return [as_of(points, end - timedelta(weeks=w)) for w in range(weeks, -1, -1)]


def volatility(points: list[Point], end: date) -> tuple[float | None, int]:
    """(mean absolute weekly log change, number of changes measured)."""
    series = weekly_series(points, end)
    changes = [
        abs(math.log(b / a))
        for a, b in zip(series, series[1:], strict=False)
        if a and b
    ]
    if len(changes) < MIN_CHANGES:
        return None, len(changes)
    return sum(changes) / len(changes), len(changes)


@dataclass
class TargetVol:
    key: tuple[str, uuid.UUID]
    volatility: float | None
    current_bin: str
    out_of_top_streak: int = 0


@dataclass(frozen=True)
class Assignment:
    bin: str
    rank: int | None
    out_of_top_streak: int


def assign_bins(targets: list[TargetVol]) -> dict[tuple[str, uuid.UUID], Assignment]:
    known = sorted(
        (t for t in targets if t.volatility is not None),
        # Most volatile first; ties broken by key so a re-run is identical.
        key=lambda t: (-t.volatility, t.key[0], str(t.key[1])),
    )
    rank = {t.key: i + 1 for i, t in enumerate(known)}
    out: dict[tuple[str, uuid.UUID], Assignment] = {}

    # Incumbents of high keep their seat while they rank within HIGH_KEEP_RANK,
    # or until they have been outside it HIGH_DEMOTE_STREAK weeks running.
    high: list[tuple[str, uuid.UUID]] = []
    streaks: dict[tuple[str, uuid.UUID], int] = {}
    for t in known:
        if t.current_bin != "high":
            continue
        inside = rank[t.key] <= HIGH_KEEP_RANK
        streak = 0 if inside else t.out_of_top_streak + 1
        streaks[t.key] = streak
        if streak < HIGH_DEMOTE_STREAK:
            high.append(t.key)
    for t in known:
        if len(high) >= HIGH_SLOTS:
            break
        if t.key not in high and rank[t.key] <= HIGH_SLOTS:
            high.append(t.key)
    high_set = set(high)

    unknown = [t for t in targets if t.volatility is None]
    medium_room = max(0, MEDIUM_SLOTS - len(unknown))
    rest = [t.key for t in known if t.key not in high_set]
    medium_set = set(rest[:medium_room])

    for t in known:
        if t.key in high_set:
            b = "high"
        elif t.key in medium_set:
            b = "medium"
        else:
            b = "low"
        out[t.key] = Assignment(
            b, rank[t.key], streaks.get(t.key, 0) if b == "high" else 0
        )
    for t in unknown:
        out[t.key] = Assignment("medium", None, 0)
    return out
