"""The rules that decide when a complete system is offered instead of a build.

Pure: no database. The fixtures mirror app/seeds/seed_systems.py closely
enough that a change to the rules shows up here the way it would in the chat.
"""

from dataclasses import replace

from app.schemas.chat import NO_BUDGET_CEILING, BuildProfile, LockedPart
from app.services.systems.fit import (
    DiscreteGpu,
    SystemOption,
    assess,
    estimate_discrete,
    memory_need_gb,
)

GB10_USES = ("llm_inference", "llm_training")
MAC_USES = ("llm_inference", "video_editing", "music_production")
STRIX_USES = ("llm_inference",)


def _system(name, family, backend, mem, gpu_mem, bw, dollars, uses, os="os"):
    return SystemOption(
        part_id=name,
        name=name,
        manufacturer=None,
        family_id=family,
        family_name=family,
        platform="x",
        gpu_backend=backend,
        os=os,
        chip="chip",
        unified_memory_gb=mem,
        gpu_memory_gb=gpu_mem,
        bandwidth_gbps=bw,
        storage_gb=1000,
        price_cents=dollars * 100,
        suited_for=uses,
    )


_LINUX = "DGX OS (Ubuntu)"
_MAC = "macOS"
_WIN = "Windows 11 or Linux"
SPARK = _system("GX10", "gb10", "cuda", 128, 120, 273, 3999, GB10_USES, _LINUX)
SPARK_FE = _system("Spark FE", "gb10", "cuda", 128, 120, 273, 4699, GB10_USES, _LINUX)
MAC_36 = _system("Mac 36", "m5max", "metal", 36, 24, 460, 2499, MAC_USES, _MAC)
MAC_48 = _system("Mac 48", "m5max", "metal", 48, 36, 614, 3099, MAC_USES, _MAC)
MAC_64 = _system("Mac 64", "m5max", "metal", 64, 48, 614, 3499, MAC_USES, _MAC)
MAC_128 = _system("Mac 128", "m5max", "metal", 128, 96, 614, 5099, MAC_USES, _MAC)
ULTRA_96 = _system("Ultra 96", "m5ultra", "metal", 96, 72, 1200, 5499, MAC_USES, _MAC)
STRIX = _system("Framework", "strix", "rocm", 128, 96, 256, 3449, STRIX_USES, _WIN)
SYSTEMS = [SPARK, SPARK_FE, MAC_36, MAC_48, MAC_64, MAC_128, ULTRA_96, STRIX]

GPUS = [
    DiscreteGpu("RTX 5060 Ti 16GB", 16, 59_000),
    DiscreteGpu("RTX 3090", 24, 150_000),
    DiscreteGpu("RTX 5090", 32, 449_999),
    DiscreteGpu("RTX Pro 6000 Blackwell", 96, 1_250_000),
]
PLATFORM = 150_000


def _ai(**overrides) -> BuildProfile:
    fields = {
        "primary_use": "ai",
        "budget_tier": "high",
        "ai_workload": "inference",
        "ai_model_scale": "large",
        "llm_quantization": "yes",
        "llm_context_tokens": "8k",
        "stated_budget_usd": 5000,
    }
    fields.update(overrides)
    return BuildProfile(**fields)


def _assess(profile: BuildProfile, **kwargs):
    kwargs.setdefault("budget_usd", profile.stated_budget_usd or NO_BUDGET_CEILING)
    kwargs.setdefault("platform_cents", PLATFORM)
    return assess(profile, SYSTEMS, GPUS, **kwargs)


# --- memory ---------------------------------------------------------------------


def test_large_quantized_model_offers_cheapest_system_that_holds_it():
    result = _assess(_ai())
    assert result is not None
    assert result.reason == "memory"
    assert result.memory_need_gb == 42  # 70B * 0.5 bytes * 1.2
    assert result.primary.name == "Framework"
    # One per family, cheapest variant of each, in price order.
    assert [a.name for a in result.alternates] == ["Mac 64", "GX10"]


def test_estimate_is_the_cheapest_discrete_setup_that_holds_the_model():
    result = _assess(_ai())
    assert result.estimate.gpu_name == "RTX 3090"
    assert result.estimate.gpu_count == 2
    assert result.estimate.gpu_memory_gb == 48


def test_small_model_that_fits_one_cheap_card_gets_no_offer():
    assert _assess(_ai(ai_model_scale="small")) is None


def test_training_only_considers_families_curated_for_it():
    result = _assess(_ai(ai_workload="training", ai_model_scale="medium"))
    assert result is not None
    assert all(
        "llm_training" in s.suited_for for s in [result.primary, *result.alternates]
    )


def test_curation_not_code_decides_training_eligibility():
    # The day ROCm fine-tuning is good enough, an admin edit is all it takes.
    trained_strix = replace(STRIX, suited_for=("llm_inference", "llm_training"))
    systems = [trained_strix if s is STRIX else s for s in SYSTEMS]
    result = assess(
        _ai(ai_workload="training", ai_model_scale="medium"),
        systems,
        GPUS,
        budget_usd=5000,
        platform_cents=PLATFORM,
    )
    assert result.primary.name == "Framework"


def test_naming_cuda_rules_out_other_backends():
    result = _assess(_ai(notes="our stack is all CUDA"))
    assert result.primary.name == "GX10"
    assert result.alternates == []


def test_naming_an_os_orders_by_it_but_does_not_filter():
    result = _assess(_ai(notes="I'd love to stay on macOS"))
    assert result.primary.os == "macOS"
    assert result.alternates  # the others are still offered

    result = _assess(_ai(notes="it has to run Ubuntu"))
    assert result.primary.os != "macOS"


def test_catalog_backends_are_respected():
    result = _assess(_ai(), catalog_floor_gb=48, catalog_backends={"cuda", "rocm"})
    assert all(
        s.gpu_backend in {"cuda", "rocm"} for s in [result.primary, *result.alternates]
    )


def test_catalog_floor_overrides_the_scale_table():
    assert memory_need_gb(_ai(ai_model_scale="small"), 90) == 90


def test_full_precision_and_long_context_raise_the_need():
    assert memory_need_gb(_ai(llm_quantization="no"), None) == 168
    assert memory_need_gb(_ai(llm_context_tokens="128k"), None) == 67


def test_nothing_offered_over_budget():
    assert _assess(_ai(stated_budget_usd=3000)) is None


def test_no_ceiling_budget_still_offers():
    result = _assess(_ai(budget_tier="custom", stated_budget_usd=None))
    assert result is not None and result.budget_usd is None


def test_a_model_no_system_holds_gets_no_offer():
    assert _assess(_ai(llm_quantization="no"), budget_usd=20000) is None


def test_system_much_dearer_than_discrete_is_not_offered():
    cheap_24 = [DiscreteGpu("RTX 3090", 24, 60_000)]
    profile = _ai(ai_model_scale="medium")  # 24GB need
    assert (
        assess(profile, SYSTEMS, cheap_24, budget_usd=5000, platform_cents=PLATFORM)
        is None
    )


def test_image_generation_is_never_offered_a_system():
    assert _assess(_ai(ai_workload="image_gen")) is None


# --- exclusions -------------------------------------------------------------------


def test_games_rule_out_families_not_curated_for_gaming():
    assert _assess(_ai(games=["Cyberpunk 2077"])) is None


def test_games_allow_a_family_curated_for_gaming():
    gaming_strix = replace(STRIX, suited_for=("llm_inference", "gaming"))
    result = assess(
        _ai(games=["Cyberpunk 2077"]),
        [*SYSTEMS, gaming_strix],
        GPUS,
        budget_usd=5000,
        platform_cents=PLATFORM,
    )
    assert result.primary is gaming_strix


def test_locked_parts_rule_out_any_offer():
    locked = LockedPart(role="gpu", name="RTX 5090")
    assert _assess(_ai(locked_parts=[locked])) is None


# --- creative -----------------------------------------------------------------------


def _video(**overrides) -> BuildProfile:
    fields = {
        "primary_use": "video_editing",
        "budget_tier": "high",
        "editing_resolution": "4k",
        "stated_budget_usd": 4000,
    }
    fields.update(overrides)
    return BuildProfile(**fields)


def test_4k_video_editing_offers_a_mac_that_covers_it():
    result = _assess(
        _video(), reference_total_cents=300_000, reference_gpu_cents=90_000
    )
    assert result.reason == "creative"
    assert result.primary.name == "Mac 48"
    assert result.alternates[0].name == "Mac 64"
    assert result.estimate.total_cents == 300_000


def test_heavy_6k_steps_up_to_128gb():
    result = _assess(
        _video(editing_resolution="6k_plus", workload_intensity="heavy"),
        budget_usd=6000,
    )
    assert result.primary.name == "Mac 128"
    assert result.alternates == []


def test_creative_offer_only_from_curated_families():
    assert (
        assess(_video(), [SPARK, STRIX], GPUS, budget_usd=6000, platform_cents=0)
        is None
    )


def test_music_production_offers_the_base_mac():
    result = _assess(_video(primary_use="music_production", editing_resolution=None))
    assert result.primary.name == "Mac 36"


def test_naming_cuda_rules_out_a_non_cuda_creative_offer():
    assert _assess(_video(notes="my plugins need CUDA")) is None


def test_other_uses_get_no_offer():
    assert _assess(_video(primary_use="software_dev")) is None


def test_estimate_discrete_takes_two_cheap_cards_over_one_dear_one():
    est = estimate_discrete(20, GPUS, PLATFORM)
    assert (est.gpu_name, est.gpu_count) == ("RTX 5060 Ti 16GB", 2)
    assert est.total_cents == 2 * 59_000 + PLATFORM


def test_estimate_discrete_single_card_when_multi_not_allowed():
    est = estimate_discrete(20, GPUS, PLATFORM, allow_multi=False)
    assert (est.gpu_name, est.gpu_count) == ("RTX 3090", 1)
