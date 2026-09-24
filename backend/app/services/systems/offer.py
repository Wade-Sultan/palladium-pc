"""Saving an offer and redeeming the user's answer to it, at most once.

An offer ends the turn the same way the case picker does: the choice arrives as
its own turn, possibly much later, possibly on another pod, possibly from a
guest with no checkpoint to read. So everything the answer needs (the profile
the offer was assessed on, and the systems it offered) is saved under the
token in paused_build's stores, and the answer claims it there. The claim is
what stops a double-click on "build me a custom PC" from running the pipeline
twice.

The event payload (`offer_data`) is what the card renders and what gets
persisted onto the message. The saved payload is what the server trusts. They
overlap, but the server never reads the client's copy back: a pick names a
token and a choice, and both are checked against the saved one.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.schemas.chat import BuildProfile
from app.services.systems.fit import Assessment

KIND = "system_offer"
CUSTOM = "custom"


def offer_data(token: str, assessment: Assessment) -> dict[str, Any]:
    return {"token": token, "chosen": None, **assessment.to_dict()}


async def save(
    conversation_id: str | None, profile: BuildProfile, assessment: Assessment
) -> str | None:
    """Persist an offer. Returns its token, or None if nothing could store it.

    None means the offer must not be shown: a card whose buttons cannot be
    redeemed is worse than no card.
    """
    from app.services import paused_build

    token = uuid.uuid4().hex
    stored = await paused_build.save(
        token,
        conversation_id,
        {
            "kind": KIND,
            "conversation_id": conversation_id,
            "profile": profile.model_dump(),
            "offer": offer_data(token, assessment),
        },
    )
    return token if stored else None


async def claim(token: str, conversation_id: str | None) -> dict | None:
    """The saved offer for `token`, claimed. None if it cannot be redeemed."""
    from app.services import paused_build

    return await paused_build.load_and_claim(token, conversation_id, kind=KIND)


def offered_system(offer: dict[str, Any], part_id: str) -> dict[str, Any] | None:
    """The offered system with this part id, or None if it was not offered."""
    for option in [offer.get("primary"), *(offer.get("alternates") or [])]:
        if isinstance(option, dict) and option.get("part_id") == part_id:
            return option
    return None


def proposed_system(system: dict[str, Any], profile: dict[str, Any]) -> dict:
    """An accepted system in the shape discussion reads as the proposed build.

    `kind` distinguishes it from a parts build everywhere a proposed build is
    read. No `parts` key on purpose: nothing may mistake this for a BuildCard
    payload and try to render or re-price it component by component.
    """
    return {
        "kind": "system",
        "label": system.get("name"),
        "total_approx": system.get("price_cents"),
        "system": system,
        "profile": profile,
    }


def open_offer_proposal(offer: dict[str, Any]) -> dict:
    """An offer still awaiting a click, as the proposal discussion reads.

    While the card is open, a typed question is about the offer, so the turn
    goes to discussion instead of back through intake, which would assess the
    same profile and show the same offer a second time.
    """
    return {
        "kind": "system_offer",
        "offer": {k: v for k, v in offer.items() if k != "token"},
    }


def proposal_from_offer(offer: dict[str, Any] | None) -> dict | None:
    """What an offer on a message proposes, or None once it proposes nothing.

    Open: the offer itself. Taken: the chosen system. Declined: nothing, the
    build that followed is the proposal and it lives on its own message.
    """
    if not isinstance(offer, dict) or not offer.get("token"):
        return None
    chosen = offer.get("chosen")
    if chosen is None:
        return open_offer_proposal(offer)
    if chosen == CUSTOM:
        return None
    system = offered_system(offer, str(chosen))
    return proposed_system(system, {}) if system else None
