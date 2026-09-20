"""Accept only complete, priced builds satisfying known catalog constraints.

Two kinds of finding come out of here, and the split is deliberate:

  issues   Facts that make the bill of materials unpresentable: a part with no
           catalog ID, an inactive or duplicated part, a bad quantity, no
           current price, or a physical/electrical incompatibility the catalog
           can prove. These raise BuildValidationError and the build is not
           shown.

  caveats  Constraints the build misses that the pipeline was never able to
           hold to exactly: the per-slot ceilings sum to more than the total
           budget by design (see dspy_pipeline._BUDGET_CEILINGS), so an
           over-budget total is expected sometimes, and a published game spec
           is a publisher's claim rather than a measurement. Rejecting a
           finished build over either would leave the user with nothing after
           a multi-minute pipeline; the honest answer is to present the build
           and say plainly what it misses. They ride along on the payload as
           `caveats` so both the lead-in prompt and the card can show them.
"""

from __future__ import annotations

import copy
import math
import uuid

from sqlalchemy import inspect
from sqlalchemy.orm.attributes import set_committed_value

from app.crud.components import (
    GROUP_PRICE_LOOKUP,
    get_part_by_id,
    resolve_part_price_cents,
)
from app.schemas.chat import NO_BUDGET_CEILING


class BuildValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def check_hardware(parts: dict, quantities: dict) -> list[str]:
    """Catalog objects only; no model output can override these checks."""
    issues = []
    for role in (
        "cpu",
        "cpucooler",
        "motherboard",
        "ramkit",
        "storagedrive",
        "psu",
        "case",
    ):
        if not parts.get(role):
            issues.append(f"Missing required component: {role}")
    if issues:
        return issues
    cpu, cooler, board, ram, psu, case = (
        parts[k][0]
        for k in ("cpu", "cpucooler", "motherboard", "ramkit", "psu", "case")
    )
    memory = ram.group
    supply = psu.group
    if not cpu.socket or cpu.socket.casefold() != board.socket.casefold():
        issues.append("CPU and motherboard sockets do not match")
    if cpu.socket.casefold() not in {
        s.casefold() for s in cooler.supported_sockets or []
    }:
        issues.append("Cooler does not support the CPU socket")
    if (
        board.ddr_generation.casefold()
        not in {g.casefold() for g in cpu.ddr_generation or []}
        or memory.ddr_generation.casefold() != board.ddr_generation.casefold()
    ):
        issues.append("CPU, motherboard and memory generations do not match")
    if board.form_factor.casefold() not in {
        f.casefold() for f in case.supported_mobo_form_factors or []
    }:
        issues.append("Motherboard does not fit the case")
    modules = sum(p.group.modules * quantities[str(p.id)] for p in parts["ramkit"])
    capacity = sum(p.group.capacity_gb * quantities[str(p.id)] for p in parts["ramkit"])
    if modules > board.memory_slots:
        issues.append("Memory exceeds the motherboard's slot count")
    for maximum in (cpu.max_memory_gb, board.max_memory_gb):
        if maximum is not None and capacity > maximum:
            issues.append("Memory exceeds the platform's capacity")
    for kit in parts["ramkit"]:
        if (
            board.memory_module_types
            and kit.group.module_type not in board.memory_module_types
        ):
            issues.append("Memory module type is unsupported by the motherboard")
        if kit.group.is_ecc and (
            cpu.supports_ecc is False or board.supports_ecc is False
        ):
            issues.append("ECC memory is unsupported by the platform")
    if cooler.max_tdp_watts is not None and cooler.max_tdp_watts < cpu.tdp_watts:
        issues.append("Cooler capacity is below CPU thermal power")
    if cooler.cooler_type == "air":
        if cooler.height_mm is None or cooler.height_mm > case.max_cooler_height_mm:
            issues.append("Air cooler clearance cannot be verified")
    elif cooler.radiator_size_mm is None or cooler.radiator_size_mm > max(
        case.max_radiator_front_mm or 0, case.max_radiator_top_mm or 0
    ):
        issues.append("Radiator does not fit the case")
    if (
        psu.depth_mm
        and case.max_psu_length_mm
        and psu.depth_mm > case.max_psu_length_mm
    ):
        issues.append("PSU is too long for the case")
    gpu_count = sum(quantities[str(p.id)] for p in parts.get("gpu", []))
    if (
        gpu_count
        and board.pcie_x16_slots is not None
        and gpu_count > board.pcie_x16_slots
    ):
        issues.append("GPU count exceeds motherboard slots")
    power = cpu.tdp_watts + 100
    for gpu in parts.get("gpu", []):
        count = quantities[str(gpu.id)]
        if gpu.length_mm > case.max_gpu_length_mm:
            issues.append("GPU is too long for the case")
        if gpu_count > 1 and (gpu.width_slots is None or gpu.width_slots > 2):
            issues.append("Multi-GPU clearance cannot be verified")
        power += (gpu.chipset.tdp_watts or 0) * count
        if gpu.chipset.tdp_watts is None:
            issues.append("GPU power requirement is missing")
        if (
            gpu.chipset.recommended_psu_watts
            and supply.wattage < gpu.chipset.recommended_psu_watts
        ):
            issues.append("PSU is below the GPU manufacturer's recommendation")
    if supply.wattage < math.ceil(power * 1.2):
        issues.append("PSU lacks required system power headroom")
    m2 = sata = bays25 = bays35 = 0
    for drive in parts["storagedrive"]:
        group = drive.group
        count = quantities[str(drive.id)]
        if "sata" in group.interface.casefold():
            sata += count
            if "2.5" in group.form_factor:
                bays25 += count
            if "3.5" in group.form_factor:
                bays35 += count
        else:
            m2 += count
    for used, maximum, label in (
        (m2, board.m2_slots, "M.2 slots"),
        (sata, board.sata_ports, "SATA ports"),
        (bays25, case.drive_bays_25, "2.5-inch bays"),
        (bays35, case.drive_bays_35, "3.5-inch bays"),
    ):
        if used and (maximum is None or used > maximum):
            issues.append(f"Insufficient verified {label}")
    fans = sum(
        quantities[str(p.id)] * (p.pack_count or 1) for p in parts.get("fan", [])
    )
    if fans and (
        case.max_fan_slots is None
        or fans + (case.included_fan_count or 0) > case.max_fan_slots
    ):
        issues.append("Added fans exceed verified case slots")
    return issues


def _attach(part, name: str, value) -> None:
    """Populate a loaded relationship without triggering async lazy IO.

    set_committed_value only works on mapped instances; tests hand in plain
    objects, which just take the attribute.
    """
    if inspect(type(part), raiseerr=False) is not None:
        set_committed_value(part, name, value)
    else:
        setattr(part, name, value)


def check_game_requirements(parts: dict, groups: list[dict]) -> list[str]:
    """Caveats, not issues: a published spec is a claim about a title at an
    unstated resolution and frame rate, not a measurement against the user's
    target, so falling short of it is worth saying and not worth rejecting."""
    caveats = []
    for requirement in groups:
        role = requirement["role"]
        hardware = parts.get(role, [])
        if not hardware:
            caveats.append(
                f"{requirement['game']} publishes a {role.upper()} requirement "
                "and this build has no such part"
            )
            continue
        selected = hardware[0] if role == "cpu" else hardware[0].chipset
        scores = selected.benchmark_scores or {}
        keys = (
            ("cinebench_r24_single", "geekbench_6_single")
            if role == "cpu"
            else ("timespy",)
        )
        comparisons = []
        for alternative in requirement["alternatives"]:
            baseline = alternative.get("benchmark_scores") or {}
            key = next(
                (
                    k
                    for k in keys
                    if isinstance(scores.get(k), float | int)
                    and isinstance(baseline.get(k), float | int)
                    and baseline[k] > 0
                ),
                None,
            )
            comparisons.append(None if key is None else scores[key] >= baseline[key])
        # Missing measurements do not establish that an alternative fails.
        if comparisons and all(value is False for value in comparisons):
            caveats.append(
                f"The {role.upper()} benchmarks below {requirement['game']}'s "
                f"published {requirement['tier']} spec ("
                + " or ".join(a["name"] for a in requirement["alternatives"])
                + "); expect to lower settings for that title"
            )
    return caveats


def check_game_performance_profiles(parts: dict, profiles: list[dict]) -> list[str]:
    """Compare selected hardware with versioned game-performance envelopes.

    A profile is an estimate with explicit confidence, so benchmark shortfalls
    are caveats rather than structural build failures. Feature/VRAM constraints
    are validated separately as hard floors in ``validate_build``.
    """
    caveats: list[str] = []
    cpu = (parts.get("cpu") or [None])[0]
    gpu_board = (parts.get("gpu") or [None])[0]
    gpu = getattr(gpu_board, "chipset", None)
    for profile in profiles or []:
        gpu_scores = getattr(gpu, "benchmark_scores", None) or {}
        cpu_scores = getattr(cpu, "benchmark_scores", None) or {}
        checks = [
            (label, gpu_scores.get(key), profile.get(field))
            for label, key, field in (
                ("raster", "timespy", "min_gpu_raster_score"),
                ("ray tracing", "port_royal", "min_gpu_rt_score"),
                ("modern rendering", "speed_way", "min_gpu_modern_score"),
            )
        ]
        checks.extend(
            (label, cpu_scores.get(key), profile.get(field))
            for label, key, field in (
                ("CPU single-thread", "geekbench_6_single", "min_cpu_single_score"),
                ("CPU multi-thread", "geekbench_6_multi", "min_cpu_multi_score"),
            )
        )

        missing = []
        below = []
        for label, actual, floor in checks:
            if not isinstance(floor, int | float) or floor <= 0:
                continue
            if not isinstance(actual, int | float) or actual <= 0:
                missing.append(label)
            elif actual < floor:
                below.append(label)

        scenario = (
            f"{profile.get('resolution')} {profile.get('quality_preset')} at "
            f"{profile.get('target_fps')} FPS, RT {profile.get('ray_tracing_mode')}"
        )
        confidence = profile.get("confidence")
        confidence_text = (
            f", {confidence:.0%} confidence"
            if isinstance(confidence, int | float)
            else ""
        )
        if below:
            caveats.append(
                f"The selected hardware is below {profile.get('game')}'s {scenario} "
                f"performance envelope on {', '.join(below)}{confidence_text}; "
                "expect to lower settings, resolution, or FPS."
            )
        elif missing:
            caveats.append(
                f"{profile.get('game')}'s {scenario} envelope could not be fully "
                f"verified because {', '.join(missing)} benchmark data is missing"
                f"{confidence_text}."
            )
        if profile.get("match_notes"):
            caveats.append(
                f"{profile.get('game')} uses the closest available performance "
                f"profile: {profile['match_notes']}."
            )
    return caveats


async def validate_build(
    db, build: dict, *, budget_usd: int, profile=None, requirements: dict | None = None
) -> dict:
    """The build with prices re-resolved and `caveats` attached, or raise.

    Raises BuildValidationError for anything under `issues` in the module
    docstring. Everything under `caveats` is returned on the payload instead.
    """
    result = copy.deepcopy(build)
    parts: dict[str, list] = {}
    quantities = {}
    issues = []
    caveats = []
    total = 0
    for row in result.get("parts", []):
        try:
            part_id = uuid.UUID(row.get("part_id", ""))
        except (ValueError, TypeError, AttributeError):
            issues.append("A selected component has no catalog ID")
            continue
        part = await get_part_by_id(db, part_id)
        quantity = row.get("quantity", 1)
        if type(quantity) is not int or not 1 <= quantity <= 12:
            issues.append("Invalid component quantity")
            continue
        # `part.id is None` is a pc_parts row with no subclass row (the
        # polymorphic outer join's null key wins): no specs to check, no
        # price to resolve, so it is unavailable in every sense that matters.
        if part is None or part.id is None or not part.is_active:
            issues.append("A selected component is unavailable or inactive")
            continue
        key = str(part.id)
        if key in quantities:
            issues.append("Duplicate component rows")
            continue
        quantities[key] = quantity
        if part.part_type in ("cpu", "cpucooler", "motherboard", "psu", "case") and (
            quantity != 1 or parts.get(part.part_type)
        ):
            issues.append(f"Multiple {part.part_type} components are unsupported")
        if part.part_type in GROUP_PRICE_LOOKUP:
            fk, model = GROUP_PRICE_LOOKUP[part.part_type]
            group = await db.get(model, getattr(part, fk))
            if group is None:
                issues.append("A component's specification group is missing")
                continue
            _attach(part, "chipset" if part.part_type == "gpu" else "group", group)
        parts.setdefault(part.part_type, []).append(part)
        price = await resolve_part_price_cents(db, part)
        if price is None or price <= 0:
            issues.append(f"No current catalog price for {part.name}")
            continue
        row.update(
            model=part.name,
            brand=part.manufacturer or "",
            approx_price=price,
            quantity=quantity,
        )
        total += price * quantity
    issues.extend(check_hardware(parts, quantities))
    if budget_usd != NO_BUDGET_CEILING and total > budget_usd * 100:
        over = total / 100 - budget_usd
        caveats.append(
            f"The parts total ${total / 100:,.0f}, which is ${over:,.0f} over the "
            f"${budget_usd:,} budget"
        )
    if profile is not None and parts.get("cpu"):
        gpu_count = sum(quantities[str(p.id)] for p in parts.get("gpu", []))
        if (
            not gpu_count
            and not parts["cpu"][0].has_igpu
            and profile.primary_use != "server"
        ):
            issues.append("The build has no graphics output")
        if profile.server_gpu_count is not None and gpu_count != int(
            profile.server_gpu_count
        ):
            issues.append("GPU count does not match the user's request")
    if requirements:
        caveats.extend(
            check_game_requirements(parts, requirements.get("game_requirements", []))
        )
        caveats.extend(
            check_game_performance_profiles(
                parts, requirements.get("game_performance_profiles", [])
            )
        )
        ram = sum(
            p.group.capacity_gb * quantities[str(p.id)] for p in parts.get("ramkit", [])
        )
        storage = sum(
            p.group.capacity_gb * quantities[str(p.id)]
            for p in parts.get("storagedrive", [])
        )
        vram = max((p.chipset.vram_gb or 0 for p in parts.get("gpu", [])), default=0)
        if requirements.get("supports_multi_gpu"):
            vram = sum(
                (p.chipset.vram_gb or 0) * quantities[str(p.id)]
                for p in parts.get("gpu", [])
            )
        for value, field, label in (
            (ram, "min_ram_gb", "RAM"),
            (storage, "min_storage_gb", "storage"),
            (vram, "min_vram_gb", "VRAM"),
        ):
            if requirements.get(field) and value < requirements[field]:
                issues.append(
                    f"Insufficient {label} for the catalog workload requirements"
                )
        required_features = set(requirements.get("required_features") or [])
        if "ray_tracing" in required_features and not any(
            p.chipset and p.chipset.has_ray_tracing for p in parts.get("gpu", [])
        ):
            issues.append("The requested game profile requires ray-tracing hardware")
    if issues:
        raise BuildValidationError(list(dict.fromkeys(issues)))
    result["total_approx"] = total
    result["caveats"] = list(dict.fromkeys(caveats))
    return result
