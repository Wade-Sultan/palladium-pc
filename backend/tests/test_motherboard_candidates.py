"""A soft board slot budget must not erase every compatible motherboard."""

import asyncio
from types import SimpleNamespace

from app.crud.components import get_motherboard_candidates


class _Session:
    def __init__(self, boards):
        self.boards = boards

    async def execute(self, _query):
        return self

    def scalars(self):
        return self

    def all(self):
        return self.boards


def _board(name, socket, price_cents, ddr="ddr5"):
    return SimpleNamespace(
        name=name,
        socket=socket,
        ddr_generation=ddr,
        form_factor="atx",
        street_price_cents=price_cents,
    )


def _candidates(boards, ceiling):
    return asyncio.run(
        get_motherboard_candidates(
            _Session(boards),
            cpu_socket="AM5",
            ddr_gens=["ddr5"],
            budget_ceiling_usd=ceiling,
            form_factor="no_preference",
            wifi_required=False,
        )
    )


def test_only_affordable_compatible_boards_are_sent_when_available():
    boards = [
        _board("affordable", "AM5", 15_000),
        _board("expensive", "AM5", 32_000),
        _board("wrong socket", "LGA1700", 10_000),
    ]

    assert [b.name for b in _candidates(boards, 162)] == ["affordable"]


def test_cheapest_compatible_boards_keep_a_sparse_catalog_usable():
    boards = [
        _board("premium", "AM5", 80_000),
        _board("mid", "AM5", 39_000),
        _board("base", "AM5", 32_000),
        _board("wrong socket", "LGA1700", 10_000),
        _board("unpriced", "AM5", None),
    ]

    assert [b.name for b in _candidates(boards, 162)] == [
        "base",
        "mid",
        "premium",
    ]
