"""Seed games that are not out on PC yet, with projected performance profiles.

Idempotent: games match by slug; a profile matches by (game, derivation_method,
resolution, target_fps) and is updated in place, so re-running syncs these
values. Re-running overwrites admin edits to the descriptive fields, the same
as seed_systems, with the two exceptions below.

RELEASE METADATA IS SET ON INSERT ONLY. release_status and pc_release_date
below are a dated snapshot, and this file is meant to be re-run (after the
benchmarks job, say). Writing them on every run would put a game that admin
has since marked dated or released back to "announced". Once a game is
released its projected profiles are left alone entirely: measured data
replaces them, and refreshing an estimate for a game people can benchmark is
the wrong direction.

AN INCOMPLETE PROJECTION IS NEVER ACTIVE. The recommender skips a floor that is
unset, and validation does not report the gap, so a profile with no GPU or CPU
floor would steer builds as if it had been checked against the console baseline
when nothing was checked. A refresh therefore requires the equivalent GPU's Time
Spy score and the equivalent CPU's Geekbench 6 single-core score:

  * new profile, baseline missing: inserted inactive (parked), so the next
    complete run can fill and activate it;
  * existing profile with complete floors, baseline missing: left exactly as
    it is (the last complete projection keeps serving);
  * existing active profile that is itself incomplete: deactivated;
  * complete baseline: floors refreshed. A parked profile is activated; one
    that admin deactivated with complete floors stays inactive.

A floor that has a value is never overwritten with null. Any failed refresh is
printed and the run exits non-zero, after committing everything that did
succeed.

WHY THE FLOORS ARE NOT NUMBERS IN THIS FILE. A console-parity profile says
"to match the consoles, a PC needs roughly this part". The curated judgement is
the equivalence (which chipset, which CPU), and that is what is written here.
The benchmark floors are copied at seed time from that part's own
`benchmark_scores` in whatever catalog this runs against, so they sit on the
same scale as the candidates they are compared with. If the part has no scores
yet (the local seed has none), the profile is not activated (see above): re-run
it after the benchmarks job has filled them in.

EVERYTHING BELOW IS A SNAPSHOT, checked on 2026-11-21:

Grand Theft Auto VI launched on PS5 and Xbox Series X|S on 2026-11-19. Rockstar
has announced no PC version and no PC date. A PC release in Q1 2027 has been
reported, not announced, so pc_release_date stays null. Rockstar's previous
three PC ports arrived 7 to 19 months after console.

Digital Foundry's launch analysis (via secondary coverage) puts both PS5 and
PS5 Pro at a ~1440p internal resolution and a 30 FPS target, with no 40 or 60
FPS mode. Only the Pro holds 30 steadily: the base PS5 drops into the low 20s
in heavy scenes, and only the Pro adds ray-traced shadows. So the parity target
is the *Pro* at 1440p/30 with RT off: matching the base PS5 would not hold 30.

  - GPU: the PS5 Pro's GPU is most often compared to an RX 7700 XT for raster
    (some estimates are lower, near an RX 6800).
  - CPU: both consoles run an 8-core Zen 2 at ~3.5 GHz. The catalog has no Zen
    2 desktop part, and PC ports of Rockstar games have needed more CPU than
    the console versions, so the researched floor was a Ryzen 5 5600X. The
    benchmarks job found no Geekbench 6 score for it, so the equivalent is the
    Ryzen 5 5500 (Zen 3, 6 cores, a little below a 5600X): the nearest part
    with a score. The Ryzen 5 7600 was the other option and sits about 30%
    above a 5600X, which would rule out every AM4 build. Switch back to the
    5600X once it has a score.
  - VRAM: the equivalent card's own VRAM (12GB on the RX 7700 XT).

Run: uv run python -m app.seeds.seed_projected_games
"""

import sys

from app.core.db import SessionLocal
from app.models.games_catalog import Game, GamePerformanceProfile, ReleaseStatus
from app.models.pcparts import CPU, GPUChipset

_SOURCES = [
    "https://www.gtaboom.com/digital-foundry-finds-that-gta-6-indeed-runs-best-on-ps5-pro-b72f",
    "https://twistedvoxel.com/gta-6-ps5-pro-vs-ps5-performance-analysis/",
    "https://www.altchar.com/game-news/gta-vi-dips-as-low-as-23fps-on-base-ps5-in-heavy-action-digital-foundry-finds-aJybE7x7IsZa",
    "https://www.bgr.com/2249912/amd-gpu-equivalent-to-playstation-5-pro/",
    "https://www.techradar.com/gaming/pc-gaming/how-to-build-a-ps5-pro-pc-equivalent-gaming-rig",
]

_GAMES: list[dict] = [
    {
        "game": {
            "title": "Grand Theft Auto VI",
            "slug": "grand-theft-auto-vi",
            # Matching folds case and spacing, so "GTA6" and "gta 6" are
            # already covered by "GTA 6".
            "aliases": ["GTA 6", "GTA VI", "Grand Theft Auto 6"],
            "genre": "aaa_open_world",
            "store_url": "https://www.rockstargames.com/VI",
            "release_status": "announced",
            "pc_release_date": None,
            "requirements_notes": (
                "Console-only at launch (2026-11-19). No PC version or PC "
                "requirements announced as of 2026-11-21."
            ),
        },
        "profiles": [
            {
                "fields": {
                    "resolution": "1440p",
                    "target_fps": 30,
                    "quality_preset": "high",
                    "ray_tracing_mode": "off",
                    "upscaling_mode": "native",
                    "frame_generation": False,
                    "min_ram_gb": 16,
                    "confidence": 0.3,
                    "sample_count": 0,
                    "derivation_method": "console_parity",
                    "source_urls": _SOURCES,
                    "notes": (
                        "Projected from PS5 Pro parity (1440p internal, 30 FPS, "
                        "RT off), not measured. GPU floor from an RX 7700 XT, "
                        "CPU floor from a Ryzen 5 5500. A 60 FPS target needs "
                        "well above this."
                    ),
                },
                "gpu_equivalent": "RX 7700 XT",
                "cpu_equivalent": "Ryzen 5 5500",
            },
        ],
    },
]


def _floors_from_equivalents(db, entry: dict) -> tuple[dict, list[str]]:
    """Benchmark/VRAM floors copied from the named parts. See the header."""
    floors: dict = {
        "min_gpu_raster_score": None,
        "min_gpu_modern_score": None,
        "min_cpu_single_score": None,
        "min_cpu_multi_score": None,
        "min_vram_gb": None,
    }
    missing: list[str] = []

    chipset = (
        db.query(GPUChipset).filter(GPUChipset.name == entry["gpu_equivalent"]).first()
    )
    if chipset is None:
        missing.append(f"GPU chipset {entry['gpu_equivalent']!r} not in catalog")
    else:
        scores = chipset.benchmark_scores or {}
        floors["min_gpu_raster_score"] = scores.get("timespy")
        floors["min_gpu_modern_score"] = scores.get("speed_way")
        floors["min_vram_gb"] = chipset.vram_gb
        if not scores.get("timespy"):
            missing.append(f"{chipset.name} has no Time Spy score")

    cpu = db.query(CPU).filter(CPU.name == entry["cpu_equivalent"]).first()
    if cpu is None:
        missing.append(f"CPU {entry['cpu_equivalent']!r} not in catalog")
    else:
        scores = cpu.benchmark_scores or {}
        floors["min_cpu_single_score"] = scores.get("geekbench_6_single")
        floors["min_cpu_multi_score"] = scores.get("geekbench_6_multi")
        if not scores.get("geekbench_6_single"):
            missing.append(f"{cpu.name} has no Geekbench 6 score")

    return floors, missing


# Set on insert only. See the header.
_INSERT_ONLY_GAME_FIELDS = frozenset({"release_status", "pc_release_date"})

# The baseline a projection cannot be active without. See the header.
_REQUIRED_FLOORS = ("min_gpu_raster_score", "min_cpu_single_score")


def _complete(floors: dict) -> bool:
    return all(floors.get(key) is not None for key in _REQUIRED_FLOORS)


def _upsert_game(db, fields: dict) -> Game:
    game = db.query(Game).filter_by(slug=fields["slug"]).first()
    if game is None:
        game = Game(**fields)
        db.add(game)
    else:
        for key, value in fields.items():
            if key not in _INSERT_ONLY_GAME_FIELDS:
                setattr(game, key, value)
    db.flush()
    return game


def plan_profile(existing: dict | None, fields: dict, floors: dict) -> dict | None:
    """What to write for one profile, or None to leave the row untouched.

    `existing` is the current row's columns (None when there is no row).
    Pure, so the rules in the header are testable without a database.
    """
    if _complete(floors):
        if existing is None:
            return {**fields, **floors, "is_active": True}
        merged = {
            key: value if value is not None else existing.get(key)
            for key, value in floors.items()
        }
        values = {**fields, **merged}
        if not existing.get("is_active") and not _complete(existing):
            values["is_active"] = True  # parked by an earlier incomplete run
        return values

    if existing is None:
        return {**fields, **floors, "is_active": False}
    if _complete(existing):
        return None  # keep the last complete projection serving
    if existing.get("is_active"):
        return {"is_active": False}
    return None


def _upsert_profile(db, game: Game, fields: dict, floors: dict) -> None:
    profile = (
        db.query(GamePerformanceProfile)
        .filter_by(
            game_id=game.id,
            derivation_method=fields["derivation_method"],
            resolution=fields["resolution"],
            target_fps=fields["target_fps"],
        )
        .first()
    )
    existing = None
    if profile is not None:
        existing = {key: getattr(profile, key) for key in (*floors, "is_active")}

    values = plan_profile(existing, fields, floors)
    if values is None:
        return
    if profile is None:
        db.add(GamePerformanceProfile(game_id=game.id, **values))
    else:
        for key, value in values.items():
            setattr(profile, key, value)


def seed_projected_games() -> int:
    """Returns a process exit code: 1 when any projection could not refresh."""
    failed = False
    db = SessionLocal()
    try:
        for entry in _GAMES:
            game = _upsert_game(db, entry["game"])
            if game.release_status == ReleaseStatus.RELEASED.value:
                print(f"  {game.title}: released, projected profiles not touched")
                continue
            for profile in entry["profiles"]:
                fields = profile["fields"]
                floors, missing = _floors_from_equivalents(db, profile)
                _upsert_profile(db, game, fields, floors)
                for problem in missing:
                    print(f"  {game.title}: {problem}")
                if not _complete(floors):
                    failed = True
                    print(
                        f"  {game.title} {fields['resolution']}/"
                        f"{fields['target_fps']}: REFRESH FAILED, baseline "
                        "incomplete. An earlier complete projection is kept; "
                        "otherwise the profile is inactive."
                    )
        db.commit()
        print(f"Seeded {len(_GAMES)} projected game(s).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(seed_projected_games())
