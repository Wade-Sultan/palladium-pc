"""The refresh rules in app/seeds/seed_projected_games.py's header.

Pure: plan_profile takes the existing row as a dict, and _upsert_game is
exercised against a stub session, so no database is needed.
"""

from types import SimpleNamespace

from app.seeds.seed_projected_games import _upsert_game, plan_profile

FIELDS = {"resolution": "1440p", "target_fps": 30, "notes": "new notes"}
EMPTY = {
    "min_gpu_raster_score": None,
    "min_gpu_modern_score": None,
    "min_cpu_single_score": None,
    "min_cpu_multi_score": None,
    "min_vram_gb": 12,
}
FULL = {
    **EMPTY,
    "min_gpu_raster_score": 17000,
    "min_gpu_modern_score": 3900,
    "min_cpu_single_score": 2200,
    "min_cpu_multi_score": 8800,
}


def test_new_profile_without_baseline_is_inserted_inactive() -> None:
    values = plan_profile(None, FIELDS, EMPTY)
    assert values is not None
    assert values["is_active"] is False


def test_new_profile_with_baseline_is_active() -> None:
    values = plan_profile(None, FIELDS, FULL)
    assert values is not None
    assert values["is_active"] is True
    assert values["min_gpu_raster_score"] == 17000


def test_failed_refresh_keeps_the_last_complete_projection() -> None:
    existing = {**FULL, "is_active": True}
    assert plan_profile(existing, FIELDS, EMPTY) is None


def test_failed_refresh_deactivates_an_incomplete_active_profile() -> None:
    existing = {**EMPTY, "is_active": True}
    assert plan_profile(existing, FIELDS, EMPTY) == {"is_active": False}


def test_failed_refresh_leaves_a_parked_profile_alone() -> None:
    existing = {**EMPTY, "is_active": False}
    assert plan_profile(existing, FIELDS, EMPTY) is None


def test_complete_refresh_activates_a_parked_profile() -> None:
    existing = {**EMPTY, "is_active": False}
    values = plan_profile(existing, FIELDS, FULL)
    assert values is not None
    assert values["is_active"] is True


def test_complete_refresh_respects_an_admin_deactivation() -> None:
    existing = {**FULL, "is_active": False}
    values = plan_profile(existing, FIELDS, FULL)
    assert values is not None
    assert "is_active" not in values


def test_refresh_never_overwrites_a_floor_with_null() -> None:
    existing = {**FULL, "is_active": True}
    floors = {**FULL, "min_gpu_modern_score": None, "min_cpu_single_score": 2300}
    values = plan_profile(existing, FIELDS, floors)
    assert values is not None
    assert values["min_gpu_modern_score"] == 3900
    assert values["min_cpu_single_score"] == 2300


class _StubSession:
    def __init__(self, game) -> None:
        self._game = game

    def query(self, _model):
        return self

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self._game

    def add(self, _obj) -> None:
        raise AssertionError("existing game should be updated, not added")

    def flush(self) -> None:
        pass


def test_rerun_does_not_revert_release_metadata() -> None:
    game = SimpleNamespace(
        slug="grand-theft-auto-vi",
        title="old title",
        release_status="released",
        pc_release_date="2027-03-01",
    )
    _upsert_game(
        _StubSession(game),
        {
            "slug": "grand-theft-auto-vi",
            "title": "Grand Theft Auto VI",
            "release_status": "announced",
            "pc_release_date": None,
        },
    )
    assert game.title == "Grand Theft Auto VI"
    assert game.release_status == "released"
    assert game.pc_release_date == "2027-03-01"
