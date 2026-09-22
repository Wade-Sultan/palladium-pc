"""Parts the user brought to the build, and whether we can honour them.

THE DECISION THIS MODULE OWNS. A user who says "I want a build around the RTX
5090" has already made the most consequential choice in the build. Asking a
model to make it again is worse than pointless: it costs an LLM call to either
rubber-stamp an answer we already had or to silently contradict the user. So a
pre-selected part short-circuits its own Decide* step entirely, see
`_locked_result` in dspy_pipeline, and this module decides which
pre-selections earn that.

THREE WAYS A LOCK IS REFUSED, and nothing else:

  unresolved    The catalog has no row for what they named. We cannot buy it,
                cannot price it and cannot check anything about it, so the step
                runs normally.
  unaffordable  Honouring it leaves too little for the slots that are still
                mandatory. A build that cannot be completed is not a build.
  overspec      The part clears the workload's measured floors by so much that
                the money above the cheapest sufficient option exceeds its
                whole slot budget. This is the "Rainbow Six at 1080p on a 5090"
                case.

`insufficient` is reported alongside those three and unlocks the step for the
same reason, but it is not a fourth policy: a part that cannot run the workload
is not a preference anyone can honour.

OVERSPEC ONLY FIRES WHEN THERE IS SOMETHING TO BE OVER. The efficiency term it
reads is computed against the cheapest candidate that would ALSO have been
sufficient. With no floors in the profile every candidate is trivially
sufficient, the cheapest part in the catalog becomes the yardstick, and every
enthusiast component on earth scores as waste. appropriateness.py already
reports that state as an uninformative score, and this module refuses to act on
one. The consequence is deliberate: a user who named a title we hold no
performance profile for keeps their part. Overriding somebody on the strength
of a measurement we do not have is the worst outcome available here, and it is
the one that would look most like a bug to the person it happened to.

NOTHING HERE RAISES. A lock is an enhancement over a pipeline that worked
without one, so every failure path ends in "run the step normally" rather than
in a failed build. The one asymmetry: a check that itself errors HONOURS the
lock rather than refusing it, because a refusal is an action taken against the
user's stated wish and needs positive evidence, while honouring is just doing
what they asked.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import components as crud_components
from app.schemas.chat import NO_BUDGET_CEILING, BuildRequest
from app.services.recommender.appropriateness import (
    Appropriateness,
    cpu_appropriateness,
    gpu_appropriateness,
)
from app.services.recommender.catalog_match import CatalogRequirements

logger = logging.getLogger(__name__)


# Slot -> the lookup category its parts are searched under. Values are
# EmbeddedEntity members, which is what discussion.find_part expects; the keys
# are the budget-slot names, so this table is also the list of lockable slots.
_CATEGORY: dict[str, str] = {
    "cpu": "cpu",
    "cooler": "cpu_cooler",
    "mobo": "motherboard",
    "ram": "ram_group",
    "storage": "storage_group",
    "gpu": "gpu_chipset",
    "psu": "psu_group",
    "case": "case",
    "fans": "fan",
}

# Slots whose Decide* step names a GROUP rather than an exact SKU. For these a
# lock carries both names: the group is what the step's output field would have
# held (and so what the gate has to produce), the exact is what the build is
# actually assembled and priced from.
_GROUPED = frozenset({"gpu", "ram", "psu", "storage"})

# How much of the budget has to survive the parts the user is still buying.
#
# A GUARDRAIL, NOT A COMPUTATION, and the distinction is worth stating because
# the honest version is tempting. Summing the cheapest viable candidate in every
# remaining slot would be exact, but those queries need a socket, a DDR
# generation and a form factor that have not been chosen yet. Locks must be
# judged BEFORE budget allocation, because allocation depends on their outcome.
# A flat reserve is the approximation that does not require the answer it is
# trying to produce.
_MIN_REMAINING_BUDGET_FRACTION = 0.25


@dataclass
class Lock:
    """One pre-selected part, resolved and judged.

    Kept a plain dataclass of JSON-safe scalars because the whole set is stored
    on DSPyBuildState, whose pause snapshot is driven off dataclass fields and
    drops anything that cannot survive a JSON round trip.
    """

    role: str
    stated: str
    owned: bool = False
    quantity: int = 1
    # What the step's output field would have held. For an ungrouped slot this
    # is just the part's catalog name.
    group_name: str | None = None
    exact_name: str | None = None
    # True when the user named something more specific than the group: a
    # particular board partner's card rather than just "RTX 5090". Only the GPU
    # path reads it, because only the GPU has a later step that would otherwise
    # pick a different member of the group on its own (see _resolve_gpu_variant).
    # For RAM, PSU and storage a group name is not something anyone types, so
    # the flag is almost always true there and means nothing.
    pinned_exact: bool = False
    price_usd: int | None = None
    honored: bool = False
    # None when honoured; otherwise one of unresolved / unaffordable /
    # insufficient / overspec.
    override: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _same(left: str | None, right: str | None) -> bool:
    """Compare two catalog names the way the rest of the catalog code does."""
    if not left or not right:
        return False
    return crud_components._normalize(left) == crud_components._normalize(right)


async def _group_name(session: AsyncSession, part: Any) -> str | None:
    """The group name for a grouped part, read without touching a relationship.

    Goes through the foreign key and a primary-key fetch rather than `part.group`
    for the same reason resolve_part_price_cents does: reading a relationship off
    a part loaded in an async session lazy-loads it, and lazy loading under
    asyncio raises rather than working slowly.
    """
    entry = crud_components.GROUP_PRICE_LOOKUP.get(getattr(part, "part_type", None))
    if entry is None:
        return None
    fk_attr, model = entry
    group_id = getattr(part, fk_attr, None)
    if group_id is None:
        return None
    group = await session.get(model, group_id)
    return getattr(group, "name", None) if group else None


async def _resolve_one(session: AsyncSession, lock: Lock) -> None:
    """Point a lock at a real catalog row, or mark it unresolved."""
    from app.services.recommender.discussion import find_part

    hit = await find_part(session, lock.stated, _CATEGORY[lock.role])
    if hit is None:
        lock.override = "unresolved"
        lock.reason = (
            f"We could not find {lock.stated} in our parts catalog, so this slot "
            f"was chosen the usual way."
        )
        return

    part = await crud_components.get_part_by_id(session, uuid.UUID(hit["part_id"]))
    if part is None:
        lock.override = "unresolved"
        lock.reason = (
            f"{lock.stated} matched a catalog entry that is no longer stocked, so "
            f"this slot was chosen the usual way."
        )
        return

    lock.exact_name = part.name
    lock.group_name = (
        await _group_name(session, part) if lock.role in _GROUPED else None
    ) or part.name
    # "RTX 5090" names a chipset and leaves the board open; "ASUS TUF RTX 5090"
    # names the board. The difference decides whether a later fit check is
    # allowed to substitute a different member of the same group.
    lock.pinned_exact = lock.role in _GROUPED and not _same(
        lock.stated, lock.group_name
    )

    cents = await crud_components.resolve_part_price_cents(session, part)
    # An unpriced part is resolvable and buildable, just not budgetable. It is
    # left at None rather than zero so the affordability check treats it as an
    # unknown cost instead of a free one.
    lock.price_usd = None if cents is None else round(cents / 100)


def _judge_affordability(locks: dict[str, Lock], budget_usd: int) -> None:
    """Refuse the fewest, most expensive locks that make the build unbuildable.

    Only parts the user still has to BUY are counted. One they already own is
    free to this build no matter what it cost them, and charging it against the
    budget would shrink every other slot to pay for hardware already on the
    desk.

    Most-expensive-first, because refusing one $2,000 card is a smaller
    intervention than refusing four cheaper locks that together cost the same,
    and the expensive lock is the one actually doing the damage.
    """
    if budget_usd == NO_BUDGET_CEILING or budget_usd <= 0:
        return

    def cost(lock: Lock) -> int:
        if lock.owned or lock.override is not None:
            return 0
        return (lock.price_usd or 0) * max(1, lock.quantity)

    affordable = int(budget_usd * (1 - _MIN_REMAINING_BUDGET_FRACTION))
    live = sorted(locks.values(), key=cost, reverse=True)
    committed = sum(cost(lock) for lock in live)
    for lock in live:
        if committed <= affordable:
            return
        spent = cost(lock)
        if spent <= 0:
            continue
        lock.override = "unaffordable"
        lock.reason = (
            f"{lock.exact_name or lock.stated} costs about ${spent:,}, which "
            f"leaves too little of a ${budget_usd:,} budget for the rest of the "
            f"machine. We picked this slot to fit the whole build instead."
        )
        committed -= spent


def _judge_overspec(
    lock: Lock, verdict: Appropriateness, slot_budget: int | None
) -> None:
    """Refuse a lock only when the waste is both measured and total."""
    if slot_budget is None or slot_budget == NO_BUDGET_CEILING:
        # Nothing to overspend. A user who said cost is not a constraint cannot
        # coherently be told they spent too much.
        return
    if not verdict.is_informative:
        # No floors resolved, so "cheapest sufficient" collapses to "cheapest"
        # and every good part scores as waste. Not a measurement; see the module
        # docstring.
        return
    if verdict.efficiency > 0:
        return
    lock.override = "overspec"
    lock.reason = verdict.feedback


async def _judge_gpu(
    session: AsyncSession,
    lock: Lock,
    request: BuildRequest,
    slot_budgets: dict[str, int],
    requirements: CatalogRequirements | None,
) -> None:
    from app.services.recommender.db.queries import get_gpu_chipset_candidates

    # Deliberately unfiltered by price: a locked card above its slot's natural
    # ceiling is exactly the case worth judging, and the budget-filtered set it
    # would otherwise be scored against does not contain it.
    rows = json.loads(
        await get_gpu_chipset_candidates(
            session,
            NO_BUDGET_CEILING,
            request.preferences,
            request.use_cases,
            request.answers,
        )
    )
    row = next((r for r in rows if _same(r.get("chipset"), lock.group_name)), None)
    if row is None:
        # Not in the candidate set at all, so there is nothing to compare it
        # against. The lock stands; the build steps below it still enforce fit.
        return

    if row.get("meets_performance_profile") is False:
        lock.override = "insufficient"
        shortfalls = ", ".join(row.get("profile_shortfalls") or []) or "the targets"
        lock.reason = (
            f"{lock.group_name} falls short of {shortfalls} for what you described, "
            f"so we chose a card that meets it instead."
        )
        return

    _judge_overspec(
        lock,
        gpu_appropriateness(
            rows,
            lock.group_name,
            min_vram_gb=getattr(requirements, "min_vram_gb", None),
            slot_budget_usd=slot_budgets.get("gpu"),
            matched_titles=getattr(requirements, "matched_names", None),
        ),
        slot_budgets.get("gpu"),
    )


async def _judge_cpu(
    session: AsyncSession,
    lock: Lock,
    request: BuildRequest,
    slot_budgets: dict[str, int],
    requirements: CatalogRequirements | None,
) -> None:
    from app.services.recommender.db.queries import get_cpu_candidates

    rows = json.loads(
        await get_cpu_candidates(
            session,
            NO_BUDGET_CEILING,
            request.preferences,
            request.use_cases,
            request.answers,
        )
    )
    row = next((r for r in rows if _same(r.get("name"), lock.group_name)), None)
    if row is None:
        return

    if row.get("meets_performance_profile") is False:
        lock.override = "insufficient"
        shortfalls = ", ".join(row.get("profile_shortfalls") or []) or "the targets"
        lock.reason = (
            f"{lock.group_name} falls short of {shortfalls} for what you described, "
            f"so we chose a processor that meets it instead."
        )
        return

    _judge_overspec(
        lock,
        cpu_appropriateness(
            rows,
            lock.group_name,
            min_cores=getattr(requirements, "min_cores", None),
            slot_budget_usd=slot_budgets.get("cpu"),
            matched_titles=getattr(requirements, "matched_names", None),
        ),
        slot_budgets.get("cpu"),
    )


# Slots we can judge against the profile rather than merely resolve. Both carry
# benchmark scores and an appropriateness metric; no other slot has either, so
# for the rest a lock is honoured on resolution and affordability alone and the
# downstream steps enforce physical fit as they always did.
_JUDGES = {"gpu": _judge_gpu, "cpu": _judge_cpu}


def _honoured_reason(lock: Lock) -> str:
    if lock.owned:
        return (
            f"You already have the {lock.exact_name}, so the build is built around it."
        )
    return f"You asked for the {lock.exact_name}, so we built around it."


async def resolve(
    session: AsyncSession,
    request: BuildRequest,
    slot_budgets: dict[str, int],
    requirements: CatalogRequirements | None = None,
) -> dict[str, dict]:
    """Resolve and judge every pre-selected part. Returns one entry per slot.

    `slot_budgets` is the allocation the build would have had with no locks at
    all. That is the right yardstick for the overspec test, "how far past this
    slot's natural share does the user's choice go", and using it avoids the
    circularity of needing the locked allocation to decide what to lock.
    """
    locks: dict[str, Lock] = {}
    for entry in request.locked_parts or []:
        if entry.role in locks:
            # One lock per slot. The profile merge already keeps only the newest
            # per role, so this is reachable only from a hand-built request.
            logger.warning(
                "duplicate locked part for slot %r; ignoring %r",
                entry.role,
                entry.name,
            )
            continue
        lock = Lock(
            role=entry.role,
            stated=entry.name,
            owned=entry.owned,
            quantity=max(1, entry.quantity),
        )
        try:
            await _resolve_one(session, lock)
        except Exception:
            logger.warning(
                "locked part %r could not be resolved; choosing this slot normally",
                entry.name,
                exc_info=True,
            )
            lock.override = "unresolved"
            lock.reason = (
                f"We could not look up {entry.name}, so this slot was chosen the "
                f"usual way."
            )
        locks[entry.role] = lock

    _judge_affordability(locks, request.budget_usd)

    for role, judge in _JUDGES.items():
        lock = locks.get(role)
        if lock is None or lock.override is not None:
            continue
        try:
            await judge(session, lock, request, slot_budgets, requirements)
        except Exception:
            # Honour it. A refusal acts against the user's stated wish and needs
            # evidence; a check that crashed produced none.
            logger.warning(
                "appropriateness check for the locked %s failed; honouring the lock",
                role,
                exc_info=True,
            )

    for lock in locks.values():
        if lock.override is None and lock.group_name:
            lock.honored = True
            lock.reason = lock.reason or _honoured_reason(lock)
        logger.info(
            "locked %s %r: %s (%s)",
            lock.role,
            lock.stated,
            "honoured" if lock.honored else f"overridden [{lock.override}]",
            lock.reason,
        )

    return {role: lock.to_dict() for role, lock in locks.items()}


def slot_costs(locked: dict[str, dict]) -> dict[str, int]:
    """What each honoured lock takes out of the budget, by slot.

    An owned part costs zero and still claims its slot. Both halves matter: the
    allocator has to stop handing that slot a share of the budget, or the money
    it was holding for a graphics card the user already owns simply goes
    unspent instead of buying more of the machine they are actually paying for.
    """
    costs: dict[str, int] = {}
    for role, lock in (locked or {}).items():
        if not lock.get("honored"):
            continue
        price = 0 if lock.get("owned") else (lock.get("price_usd") or 0)
        costs[role] = price * max(1, lock.get("quantity") or 1)
    return costs


def summary(locked: dict[str, dict]) -> str:
    """Prose for the shared use-case summary every Decide* step reads.

    Honoured locks are stated as settled facts, because to the remaining steps
    that is what they are. The PSU step sizing against a card the user already
    owns needs to know it is fixed, not that it was requested. Overridden locks
    are named too, with their reason, so a step does not re-propose the very
    part another check just rejected.
    """
    if not locked:
        return ""
    honoured = [lock for lock in locked.values() if lock.get("honored")]
    refused = [lock for lock in locked.values() if not lock.get("honored")]
    lines: list[str] = []
    if honoured:
        lines.append("Parts the user has already chosen, which are FIXED:")
        for lock in honoured:
            owned = " (they already own it)" if lock.get("owned") else ""
            quantity = lock.get("quantity") or 1
            count = f" x{quantity}" if quantity > 1 else ""
            lines.append(
                f"  - {lock['role']}: {lock.get('exact_name') or lock['stated']}"
                f"{count}{owned}. Do not choose a different one; choose the rest "
                f"of the build to work with it."
            )
    if refused:
        lines.append("The user asked for these, which we could not use:")
        for lock in refused:
            lines.append(f"  - {lock['stated']}: {lock.get('reason') or 'unavailable'}")
    return "\n".join(lines)
