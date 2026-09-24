"""The deterministic acceptance check on an assembled bill of materials.

The split that matters here is issues versus caveats. A build with an
inactive part, a missing price, or a socket mismatch is rejected outright; a
build that is over budget or below a game's published spec is returned with
that written on it. See the module docstring in recommender/validation.py for
why the second group is not a rejection.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.schemas.chat import NO_BUDGET_CEILING, BuildProfile
from app.services.recommender import validation
from app.services.recommender.validation import (
    BuildValidationError,
    check_game_performance_profiles,
    check_game_requirements,
    check_hardware,
    validate_build,
)


def _cpu(**kw):
    base = {
        "id": uuid.uuid4(),
        "part_type": "cpu",
        "name": "Ryzen 7 9800X3D",
        "manufacturer": "AMD",
        "is_active": True,
        "socket": "AM5",
        "tdp_watts": 120,
        "has_igpu": True,
        "ddr_generation": ["ddr5"],
        "max_memory_gb": 192,
        "supports_ecc": None,
        "benchmark_scores": {"cinebench_r24_single": 140},
    }
    return SimpleNamespace(**{**base, **kw})


def _cooler(**kw):
    base = {
        "id": uuid.uuid4(),
        "part_type": "cpucooler",
        "name": "Peerless Assassin",
        "manufacturer": "TR",
        "is_active": True,
        "supported_sockets": ["am5", "lga1700"],
        "cooler_type": "air",
        "max_tdp_watts": 250,
        "height_mm": 155,
        "radiator_size_mm": None,
    }
    return SimpleNamespace(**{**base, **kw})


def _board(**kw):
    base = {
        "id": uuid.uuid4(),
        "part_type": "motherboard",
        "name": "B650 Tomahawk",
        "manufacturer": "MSI",
        "is_active": True,
        "socket": "am5",
        "form_factor": "atx",
        "ddr_generation": "DDR5",
        "memory_slots": 4,
        "max_memory_gb": 256,
        "memory_module_types": None,
        "supports_ecc": None,
        "m2_slots": 3,
        "sata_ports": 4,
        "pcie_x16_slots": 2,
    }
    return SimpleNamespace(**{**base, **kw})


def _ram(**kw):
    group = SimpleNamespace(
        ddr_generation="ddr5",
        modules=2,
        capacity_gb=32,
        module_type="udimm",
        is_ecc=False,
        street_price_cents=10000,
    )
    base = {
        "id": uuid.uuid4(),
        "part_type": "ramkit",
        "name": "Vengeance 32GB",
        "manufacturer": "Corsair",
        "is_active": True,
        "group": group,
        "ram_group_id": uuid.uuid4(),
    }
    return SimpleNamespace(**{**base, **kw})


def _drive(**kw):
    group = SimpleNamespace(
        interface="pcie_gen4",
        form_factor="m2_2280",
        capacity_gb=2000,
        street_price_cents=12000,
    )
    base = {
        "id": uuid.uuid4(),
        "part_type": "storagedrive",
        "name": "SN850X 2TB",
        "manufacturer": "WD",
        "is_active": True,
        "group": group,
        "storage_group_id": uuid.uuid4(),
    }
    return SimpleNamespace(**{**base, **kw})


def _psu(**kw):
    group = SimpleNamespace(wattage=850, street_price_cents=13000)
    base = {
        "id": uuid.uuid4(),
        "part_type": "psu",
        "name": "RM850e",
        "manufacturer": "Corsair",
        "is_active": True,
        "group": group,
        "psu_group_id": uuid.uuid4(),
        "depth_mm": 140,
    }
    return SimpleNamespace(**{**base, **kw})


def _case(**kw):
    base = {
        "id": uuid.uuid4(),
        "part_type": "case",
        "name": "North",
        "manufacturer": "Fractal",
        "is_active": True,
        "supported_mobo_form_factors": ["atx", "micro_atx"],
        "max_gpu_length_mm": 355,
        "max_cooler_height_mm": 170,
        "max_radiator_front_mm": 360,
        "max_radiator_top_mm": 240,
        "max_psu_length_mm": 200,
        "drive_bays_25": 2,
        "drive_bays_35": 2,
        "max_fan_slots": 6,
        "included_fan_count": 2,
    }
    return SimpleNamespace(**{**base, **kw})


def _gpu(**kw):
    chipset = SimpleNamespace(
        tdp_watts=300,
        recommended_psu_watts=750,
        vram_gb=16,
        benchmark_scores={"timespy": 25000},
        street_price_cents=80000,
    )
    base = {
        "id": uuid.uuid4(),
        "part_type": "gpu",
        "name": "RTX 5080",
        "manufacturer": "ASUS",
        "is_active": True,
        "chipset": chipset,
        "gpu_chipset_id": uuid.uuid4(),
        "length_mm": 330,
        "width_slots": 2.5,
    }
    return SimpleNamespace(**{**base, **kw})


def _parts(**overrides):
    parts = {
        "cpu": [_cpu()],
        "cpucooler": [_cooler()],
        "motherboard": [_board()],
        "ramkit": [_ram()],
        "storagedrive": [_drive()],
        "psu": [_psu()],
        "case": [_case()],
        "gpu": [_gpu()],
    }
    parts.update(overrides)
    return parts


def _quantities(parts, **per_role):
    return {str(p.id): per_role.get(role, 1) for role, ps in parts.items() for p in ps}


# ------------------------------------------------------------- check_hardware --


def test_a_compatible_build_has_no_issues():
    parts = _parts()
    assert check_hardware(parts, _quantities(parts)) == []


def test_socket_and_generation_comparisons_ignore_case():
    """The catalog holds 'AM5' and 'am5', 'DDR5' and 'ddr5' side by side."""
    parts = _parts(cpu=[_cpu(socket="am5", ddr_generation=["DDR5"])])
    assert check_hardware(parts, _quantities(parts)) == []


def test_a_socket_mismatch_is_an_issue():
    parts = _parts(board=[_board()], cpu=[_cpu(socket="LGA1700")])
    parts["motherboard"] = [_board(socket="am5")]
    issues = check_hardware(parts, _quantities(parts))
    assert "CPU and motherboard sockets do not match" in issues


def test_missing_required_roles_short_circuit():
    parts = _parts()
    del parts["psu"]
    assert check_hardware(parts, _quantities(parts)) == [
        "Missing required component: psu"
    ]


def test_psu_headroom_counts_every_gpu():
    parts = _parts()
    # 120 + 100 + 2*300 = 820 * 1.2 = 984 > 850
    issues = check_hardware(parts, _quantities(parts, gpu=2))
    assert "PSU lacks required system power headroom" in issues


def test_air_cooler_taller_than_the_case_is_an_issue():
    parts = _parts(cpucooler=[_cooler(height_mm=180)])
    assert "Air cooler clearance cannot be verified" in check_hardware(
        parts, _quantities(parts)
    )


# ---------------------------------------------------------- game requirements --


def _requirement(role="gpu", score=30000, key="timespy"):
    return {
        "game": "Cyberpunk 2077",
        "role": role,
        "tier": "recommended",
        "alternatives": [{"name": "RTX 4070 Ti", "benchmark_scores": {key: score}}],
    }


def test_a_gpu_below_the_published_spec_is_a_caveat_not_a_rejection():
    parts = _parts()
    caveats = check_game_requirements(parts, [_requirement(score=30000)])
    assert len(caveats) == 1
    assert "Cyberpunk 2077" in caveats[0]
    assert "recommended" in caveats[0]


def test_a_gpu_meeting_the_published_spec_says_nothing():
    parts = _parts()
    assert check_game_requirements(parts, [_requirement(score=20000)]) == []


def test_missing_benchmarks_do_not_count_against_the_build():
    """No measurement means no evidence either way."""
    parts = _parts(gpu=[_gpu()])
    parts["gpu"][0].chipset.benchmark_scores = {}
    assert check_game_requirements(parts, [_requirement()]) == []


def _performance_profile(**overrides):
    return {
        "game": "Cyberpunk 2077",
        "resolution": "1440p",
        "target_fps": 60,
        "quality_preset": "ultra",
        "ray_tracing_mode": "high",
        "min_gpu_raster_score": 26000,
        "min_gpu_rt_score": 15000,
        "min_gpu_modern_score": None,
        "min_cpu_single_score": 2800,
        "min_cpu_multi_score": None,
        "confidence": 0.8,
        "match_notes": [],
        **overrides,
    }


def test_performance_profile_shortfalls_name_the_scenario_and_axes():
    parts = _parts()
    parts["gpu"][0].chipset.benchmark_scores["port_royal"] = 12000
    parts["cpu"][0].benchmark_scores["geekbench_6_single"] = 3000

    caveats = check_game_performance_profiles(parts, [_performance_profile()])

    assert len(caveats) == 1
    assert "1440p ultra at 60 FPS, RT high" in caveats[0]
    assert "raster, ray tracing" in caveats[0]
    assert "80% confidence" in caveats[0]


def test_performance_profile_reports_missing_measurements_and_closest_match():
    parts = _parts()
    parts["gpu"][0].chipset.benchmark_scores = {}
    parts["cpu"][0].benchmark_scores = {}
    profile = _performance_profile(
        match_notes=["requested 4k; closest profile is 1440p"]
    )

    caveats = check_game_performance_profiles(parts, [profile])

    assert len(caveats) == 2
    assert "benchmark data is missing" in caveats[0]
    assert "closest available performance profile" in caveats[1]


# ---------------------------------------------------------------- validate_build --


class _FakeDb:
    """Just enough of AsyncSession for validate_build: `get` on a group model."""

    def __init__(self, groups: dict):
        self.groups = groups

    async def get(self, model, key):
        return self.groups.get(key)


@pytest.fixture
def catalog(monkeypatch):
    """A catalog of the eight fixture parts, keyed by id, with group rows."""
    parts = _parts()
    by_id = {p.id: p for ps in parts.values() for p in ps}
    groups = {}
    for p in parts["gpu"]:
        groups[p.gpu_chipset_id] = p.chipset
    for p in parts["ramkit"]:
        groups[p.ram_group_id] = p.group
    for p in parts["psu"]:
        groups[p.psu_group_id] = p.group
    for p in parts["storagedrive"]:
        groups[p.storage_group_id] = p.group
    prices = {
        "cpu": 45000,
        "cpucooler": 3500,
        "motherboard": 20000,
        "case": 12000,
    }

    async def _get_part_by_id(_db, part_id):
        return by_id.get(part_id)

    async def _price(_db, part):
        if part.part_type == "gpu":
            return part.chipset.street_price_cents
        if hasattr(part, "group"):
            return part.group.street_price_cents
        return prices.get(part.part_type)

    monkeypatch.setattr(validation, "get_part_by_id", _get_part_by_id)
    monkeypatch.setattr(validation, "resolve_part_price_cents", _price)
    return SimpleNamespace(parts=parts, db=_FakeDb(groups), by_id=by_id)


def _build_dict(parts, **row_overrides):
    return {
        "label": "Custom Build",
        "description": "x",
        "total_approx": 0,
        "parts": [
            {
                "component": role,
                "brand": p.manufacturer,
                "model": p.name,
                "approx_price": None,
                "quantity": 1,
                "part_id": str(p.id),
                **row_overrides,
            }
            for role, ps in parts.items()
            for p in ps
        ],
    }


def _validate(catalog, build, **kw):
    kw.setdefault("budget_usd", NO_BUDGET_CEILING)
    kw.setdefault("profile", BuildProfile(primary_use="gaming", budget_tier="mid"))
    return asyncio.run(validate_build(catalog.db, build, **kw))


def test_a_complete_priced_build_passes_with_a_recomputed_total(catalog):
    out = _validate(catalog, _build_dict(catalog.parts))
    # 45000+3500+20000+10000+12000+13000+12000+80000
    assert out["total_approx"] == 195500
    assert out["caveats"] == []
    gpu_row = next(r for r in out["parts"] if r["component"] == "gpu")
    assert gpu_row["approx_price"] == 80000


def test_an_over_budget_build_is_returned_with_a_caveat(catalog):
    out = _validate(catalog, _build_dict(catalog.parts), budget_usd=1800)
    assert out["caveats"] == [
        "The parts total $1,955, which is $155 over the $1,800 budget"
    ]


def test_firm_budget_caveat_uses_the_buyers_stated_ceiling(catalog):
    profile = BuildProfile(
        primary_use="gaming",
        budget_tier="mid",
        stated_budget_usd=1800,
        price_sensitivity="firm",
    )
    out = _validate(
        catalog, _build_dict(catalog.parts), budget_usd=1620, profile=profile
    )
    assert out["caveats"] == [
        "The parts total $1,955, which is $155 over the $1,800 budget"
    ]


def test_a_part_without_a_catalog_id_is_rejected(catalog):
    build = _build_dict(catalog.parts)
    build["parts"][0]["part_id"] = ""
    with pytest.raises(BuildValidationError) as exc:
        _validate(catalog, build)
    assert "A selected component has no catalog ID" in exc.value.issues


def test_an_inactive_part_is_rejected(catalog):
    catalog.parts["gpu"][0].is_active = False
    with pytest.raises(BuildValidationError) as exc:
        _validate(catalog, _build_dict(catalog.parts))
    assert "A selected component is unavailable or inactive" in exc.value.issues


def test_a_part_with_no_current_price_is_rejected(catalog):
    catalog.parts["cpucooler"][0].part_type = "cpucooler"
    catalog.parts["case"][0].manufacturer = "Fractal"
    # Prices for non-grouped parts come from the fixture table; remove one.
    catalog.parts["case"][0].part_type = "case"
    build = _build_dict(catalog.parts)
    orig = validation.resolve_part_price_cents

    async def _no_case_price(db, part):
        return None if part.part_type == "case" else await orig(db, part)

    validation.resolve_part_price_cents = _no_case_price
    try:
        with pytest.raises(BuildValidationError) as exc:
            _validate(catalog, build)
    finally:
        validation.resolve_part_price_cents = orig
    assert any(i.startswith("No current catalog price") for i in exc.value.issues)


def test_bad_quantities_are_rejected(catalog):
    build = _build_dict(catalog.parts)
    next(r for r in build["parts"] if r["component"] == "ramkit")["quantity"] = 0
    with pytest.raises(BuildValidationError) as exc:
        _validate(catalog, build)
    assert "Invalid component quantity" in exc.value.issues


def test_a_build_with_no_graphics_output_is_rejected(catalog):
    catalog.parts["cpu"][0].has_igpu = False
    parts = {k: v for k, v in catalog.parts.items() if k != "gpu"}
    with pytest.raises(BuildValidationError) as exc:
        _validate(catalog, _build_dict(parts))
    assert "The build has no graphics output" in exc.value.issues


def test_published_requirement_shortfalls_ride_along_as_caveats(catalog):
    requirements = {
        "game_requirements": [_requirement(score=30000)],
        "min_ram_gb": 16,
        "min_storage_gb": 100,
        "min_vram_gb": 12,
    }
    out = _validate(catalog, _build_dict(catalog.parts), requirements=requirements)
    assert len(out["caveats"]) == 1
    assert out["caveats"][0].startswith("The GPU benchmarks below Cyberpunk 2077")


def test_insufficient_ram_for_the_workload_is_still_a_rejection(catalog):
    requirements = {"game_requirements": [], "min_ram_gb": 64}
    with pytest.raises(BuildValidationError) as exc:
        _validate(catalog, _build_dict(catalog.parts), requirements=requirements)
    assert "Insufficient RAM for the catalog workload requirements" in exc.value.issues
