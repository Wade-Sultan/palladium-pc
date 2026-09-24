"""Whether a complete system fits a profile better than a custom PC.

THE DECISION IS ARITHMETIC AND RULES, NEVER A MODEL. This is the same split
`route` keeps for profile sufficiency: a model asked "would this box suit this
person?" says yes far too easily, and an offer made on a hallucinated fit costs
the user a detour. So every branch below is a rule a person can read, and the
model is only ever handed an Assessment to phrase.

NO PRODUCT FACTS LIVE IN THIS FILE. Which families are good for training, which
for video, which run Windows: all of that is true today and changes with a
driver release or a new chip, so it is catalog data (SystemFamily.suited_for,
.gpu_backend, .os), editable in admin without a deploy. The rules here only
say how to combine that data with what the user told us. A rule that needs to
know a brand name is a rule in the wrong place.

TWO REASONS TO OFFER:

  memory    Local LLM work, where the binding constraint is how much memory the
            GPU can address. Offered when a system that holds the model costs no
            more than the cheapest discrete-GPU PC that does (within
            _UNIFIED_PREMIUM), which is exactly when "buy a bigger card" stops
            being the answer. Whether that happens depends entirely on current
            prices, which is why both sides of the comparison are read from the
            catalog at request time.
  creative  Video editing or music production, for families curated as suited
            to it, when the budget covers the system outright.

ALWAYS RULED OUT: a profile with locked parts (the user is building a PC and
we do not second-guess that), a family not curated for the workload, and a
price we cannot confirm.

Everything here is pure: plain dataclasses in, an Assessment or None out. The
database and the graph live in app/services/systems/catalog.py.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.schemas.chat import NO_BUDGET_CEILING, BuildProfile

# A system is offered for memory when it costs at most this much more than the
# cheapest discrete-GPU PC that holds the same model. Above 1.0 because the
# discrete figure is a lower bound: it prices GPUs and the reference platform,
# and nothing a second card drags in with it (a bigger PSU, a board with two
# usable slots, airflow).
_UNIFIED_PREMIUM = 1.10

# Model memory when the catalog has no row for what the user named, by the same
# arithmetic as catalog_match._QUANTIZATION_PRIMER:
#   GB ~= params_billions * bytes_per_weight * 1.2
# The scale buckets are the extractor's vocabulary ("small" / "medium" /
# "large"), anchored at typical sizes for each. Only a fallback: a curated
# ai_workloads row always wins.
_SCALE_PARAMS_B = {"small": 8, "medium": 32, "large": 70}
_BYTES_QUANTIZED = 0.5  # q4, the default self-hosters run
_BYTES_FULL = 2.0  # fp16 / bf16
_OVERHEAD = 1.2
# Adapter fine-tuning (LoRA / QLoRA) on top of the frozen base: gradients,
# optimizer state and activations roughly double the inference figure. Full
# fine-tuning is far beyond this and beyond any desktop system; it is not
# modelled here, and the catalog floor covers it when a row exists.
_TRAINING_MULTIPLIER = 2.0

# KV cache grows with context and at long context rivals the weights.
_CONTEXT_MULTIPLIER = {"32k": 1.25, "128k": 1.6}

# Unified memory a creative workload needs before a system is worth offering.
# These describe the workload, not any product.
_VIDEO_MEMORY_GB = {"1080p": 32, "4k": 48, "6k_plus": 96}
_VIDEO_HEAVY_STEP = {32: 48, 48: 64, 64: 96, 96: 128}
_VIDEO_DEFAULT_GB = 48
_MUSIC_MEMORY_GB = 32

# SystemFamily.suited_for values, by the offer that reads them.
_AI_WORKLOAD = {"inference": "llm_inference", "training": "llm_training"}
_CREATIVE_WORKLOAD = {
    "video_editing": "video_editing",
    "music_production": "music_production",
}

# The user naming the stack outright. Definitional, not a claim about which
# tools support what: "CUDA" means NVIDIA's stack by name.
_NAMES_CUDA = re.compile(r"\b(cuda|nvidia)\b", re.I)

# Words a user might use for an OS, matched against both the profile and each
# family's free-text `os`. Used to order offers, never to filter them: "I'm
# moving off Windows" names Windows too, and a filter would get it backwards.
_OS_WORDS = {
    "macos": re.compile(r"\b(mac|macos|osx|apple)\b", re.I),
    "windows": re.compile(r"\bwindows\b", re.I),
    "linux": re.compile(r"\b(linux|ubuntu|debian|fedora)\b", re.I),
}


@dataclass(frozen=True)
class SystemOption:
    """One purchasable system, flattened with its family for the offer card."""

    part_id: str
    name: str
    manufacturer: str | None
    family_id: str
    family_name: str
    platform: str
    gpu_backend: str
    os: str
    chip: str
    unified_memory_gb: int
    gpu_memory_gb: int
    bandwidth_gbps: int
    storage_gb: int | None
    price_cents: int
    suited_for: tuple[str, ...] = ()
    image_url: str | None = None
    image_credit: str | None = None
    summary: str | None = None
    strengths: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        for key in ("suited_for", "strengths", "limitations"):
            out[key] = list(getattr(self, key))
        return out


@dataclass(frozen=True)
class DiscreteGpu:
    name: str
    vram_gb: int
    price_cents: int


@dataclass(frozen=True)
class CustomEstimate:
    """What the same job costs as a custom tower. Always an estimate.

    For a memory offer, the GPU line is the cheapest one-or-two-card setup that
    holds the model, and the rest is the reference build's non-GPU parts. For a
    creative offer, it is the reference build as a whole.
    """

    gpu_name: str | None
    gpu_count: int
    gpu_memory_gb: int | None
    gpu_cents: int
    platform_cents: int

    @property
    def total_cents(self) -> int:
        return self.gpu_cents + self.platform_cents

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "total_cents": self.total_cents}


@dataclass
class Assessment:
    reason: str  # "memory" | "creative"
    primary: SystemOption
    alternates: list[SystemOption] = field(default_factory=list)
    memory_need_gb: int | None = None
    estimate: CustomEstimate | None = None
    budget_usd: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "primary": self.primary.to_dict(),
            "alternates": [a.to_dict() for a in self.alternates],
            "memory_need_gb": self.memory_need_gb,
            "estimate": self.estimate.to_dict() if self.estimate else None,
            "budget_usd": self.budget_usd,
        }


def _profile_text(profile: BuildProfile) -> str:
    return " ".join(
        [
            profile.notes or "",
            profile.rendering_software or "",
            *(profile.workloads or []),
        ]
    )


def excluded(profile: BuildProfile) -> bool:
    """Profiles no system is offered to, whatever the catalog says."""
    return bool(profile.locked_parts)


def memory_need_gb(profile: BuildProfile, catalog_floor_gb: int | None) -> int | None:
    """GPU memory the user's models need, or None when nothing sizes it.

    The catalog floor wins when there is one: it is curated per model and
    precision. The arithmetic fallback covers models the catalog does not know.
    """
    if catalog_floor_gb:
        need = float(catalog_floor_gb)
    else:
        params = _SCALE_PARAMS_B.get(profile.ai_model_scale or "")
        if params is None or profile.ai_workload not in _AI_WORKLOAD:
            return None
        per_weight = (
            _BYTES_FULL if profile.llm_quantization == "no" else _BYTES_QUANTIZED
        )
        need = params * per_weight * _OVERHEAD
        if profile.ai_workload == "training":
            need *= _TRAINING_MULTIPLIER
    need *= _CONTEXT_MULTIPLIER.get(profile.llm_context_tokens or "", 1.0)
    return int(round(need))


def estimate_discrete(
    need_gb: int,
    gpus: list[DiscreteGpu],
    platform_cents: int,
    allow_multi: bool = True,
) -> CustomEstimate | None:
    """The cheapest one- or two-card configuration holding `need_gb`."""
    best: CustomEstimate | None = None
    for gpu in gpus:
        for count in (1, 2) if allow_multi else (1,):
            if gpu.vram_gb * count < need_gb:
                continue
            candidate = CustomEstimate(
                gpu_name=gpu.name,
                gpu_count=count,
                gpu_memory_gb=gpu.vram_gb * count,
                gpu_cents=gpu.price_cents * count,
                platform_cents=platform_cents,
            )
            if best is None or candidate.total_cents < best.total_cents:
                best = candidate
            break  # one card holds it; a second of the same only costs more
    return best


def _within_budget(price_cents: int, budget_usd: int) -> bool:
    return budget_usd == NO_BUDGET_CEILING or price_cents <= budget_usd * 100


def _cheapest_per_family(options: list[SystemOption]) -> list[SystemOption]:
    best: dict[str, SystemOption] = {}
    for option in options:
        current = best.get(option.family_id)
        if current is None or option.price_cents < current.price_cents:
            best[option.family_id] = option
    return sorted(best.values(), key=lambda o: o.price_cents)


def _named_oses(text: str) -> set[str]:
    return {os for os, pattern in _OS_WORDS.items() if pattern.search(text)}


def _order_by_named_os(options: list[SystemOption], text: str) -> list[SystemOption]:
    """Families running an OS the user named first, price order within that."""
    named = _named_oses(text)
    if not named:
        return options
    return sorted(
        options,
        key=lambda o: (not (_named_oses(o.os) & named), o.price_cents),
    )


def _backend_ok(option: SystemOption, backends: set[str]) -> bool:
    return not backends or option.gpu_backend in backends


def _assess_memory(
    profile: BuildProfile,
    systems: list[SystemOption],
    gpus: list[DiscreteGpu],
    catalog_floor_gb: int | None,
    catalog_backends: set[str],
    platform_cents: int,
    budget_usd: int,
) -> Assessment | None:
    workload = _AI_WORKLOAD.get(profile.ai_workload or "")
    if profile.primary_use != "ai" or workload is None:
        return None

    need = memory_need_gb(profile, catalog_floor_gb)
    if need is None:
        return None

    text = _profile_text(profile)
    backends = set(catalog_backends)
    if _NAMES_CUDA.search(text):
        backends = {"cuda"}

    fitting = [
        s
        for s in systems
        if workload in s.suited_for
        and s.gpu_memory_gb >= need
        and _backend_ok(s, backends)
        and _within_budget(s.price_cents, budget_usd)
    ]
    if not fitting:
        return None

    estimate = estimate_discrete(need, gpus, platform_cents)
    ranked = _cheapest_per_family(fitting)
    if estimate is not None:
        ceiling = estimate.total_cents * _UNIFIED_PREMIUM
        ranked = [s for s in ranked if s.price_cents <= ceiling]
        if not ranked:
            return None
    ranked = _order_by_named_os(ranked, text)

    return Assessment(
        reason="memory",
        primary=ranked[0],
        alternates=ranked[1:3],
        memory_need_gb=need,
        estimate=estimate,
        budget_usd=None if budget_usd == NO_BUDGET_CEILING else budget_usd,
    )


def _assess_creative(
    profile: BuildProfile,
    systems: list[SystemOption],
    reference_total_cents: int | None,
    reference_gpu_cents: int,
    budget_usd: int,
) -> Assessment | None:
    workload = _CREATIVE_WORKLOAD.get(profile.primary_use)
    if workload is None:
        return None
    if workload == "video_editing":
        target = _VIDEO_MEMORY_GB.get(
            profile.editing_resolution or "", _VIDEO_DEFAULT_GB
        )
        if profile.workload_intensity == "heavy":
            target = _VIDEO_HEAVY_STEP.get(target, target)
    else:
        target = _MUSIC_MEMORY_GB

    text = _profile_text(profile)
    backends = {"cuda"} if _NAMES_CUDA.search(text) else set()

    fitting = sorted(
        (
            s
            for s in systems
            if workload in s.suited_for
            and s.unified_memory_gb >= target
            and _backend_ok(s, backends)
            and _within_budget(s.price_cents, budget_usd)
        ),
        key=lambda s: s.price_cents,
    )
    if not fitting:
        return None
    fitting = _order_by_named_os(fitting, text)

    estimate = (
        CustomEstimate(
            gpu_name=None,
            gpu_count=1,
            gpu_memory_gb=None,
            gpu_cents=reference_gpu_cents,
            platform_cents=reference_total_cents - reference_gpu_cents,
        )
        if reference_total_cents
        else None
    )
    primary = fitting[0]
    # The useful alternates for creative work: the same family with more
    # memory for longer timelines, then the cheapest of any other family.
    alternates = [
        s
        for s in fitting[1:]
        if s.family_id == primary.family_id
        and s.unified_memory_gb > primary.unified_memory_gb
    ][:1]
    alternates += [
        s for s in _cheapest_per_family(fitting) if s.family_id != primary.family_id
    ][:1]
    return Assessment(
        reason="creative",
        primary=primary,
        alternates=alternates,
        memory_need_gb=None,
        estimate=estimate,
        budget_usd=None if budget_usd == NO_BUDGET_CEILING else budget_usd,
    )


def assess(
    profile: BuildProfile,
    systems: list[SystemOption],
    gpus: list[DiscreteGpu],
    *,
    budget_usd: int,
    catalog_floor_gb: int | None = None,
    catalog_backends: set[str] | None = None,
    platform_cents: int = 0,
    reference_total_cents: int | None = None,
    reference_gpu_cents: int = 0,
) -> Assessment | None:
    """The offer to make, or None to build a custom PC as usual.

    A profile that games is only offered families curated for gaming as well as
    for its main workload: a box that runs the model but not the user's games
    is not "the right fit", however it scores on memory.
    """
    if excluded(profile) or not systems:
        return None
    if profile.games or profile.primary_use in ("gaming", "streaming"):
        systems = [s for s in systems if "gaming" in s.suited_for]
        if not systems:
            return None
    return _assess_memory(
        profile,
        systems,
        gpus,
        catalog_floor_gb,
        catalog_backends or set(),
        platform_cents,
        budget_usd,
    ) or _assess_creative(
        profile, systems, reference_total_cents, reference_gpu_cents, budget_usd
    )
