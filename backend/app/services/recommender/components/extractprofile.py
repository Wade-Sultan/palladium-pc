from __future__ import annotations

from pathlib import Path

import dspy

from app.schemas.chat import LockedPart, ProfileUpdate
from app.services.recommender.artifacts import load_artifact
from app.services.recommender.optimizing import run_gepa

WEIGHTS_PATH = Path(__file__).parent / "weights" / "extractprofile.json"


class ProfileExtraction(dspy.Signature):
    """
    Extract a structured intent profile from a PC build consultation conversation.

    Infer the user's actual needs rather than echoing their words literally.
    Also report explicit changes in the LATEST USER message as profile_updates.
    Use set for a changed scalar, clear for a retracted preference or budget,
    and add/remove for individual games and workloads. Include an exact quote
    from that message as evidence. Do not turn assistant suggestions into user
    preferences. For "no case size preference anymore", clear form_factor.
    For "I no longer play Game A", remove Game A from games. An omitted field
    is not a retraction. If a numeric budget replaces an unlimited budget, set
    both stated_budget_usd and budget_tier. If money is no longer a constraint,
    clear stated_budget_usd and set budget_tier to custom.
    Report any specific component the user names for their own build as a
    locked_parts entry, with owned=true when they already have it and
    owned=false when they want us to buy it. A part they merely ask about,
    compare, or reject is not a locked part.
    Pick the most demanding use case when multiple are mentioned.
    Infer budget tier from context clues even when no dollar figure is given.
    Every use-case-specific field must be 'none' (or empty, for rendering_software)
    when it does not apply to the inferred primary_use or the conversation gives
    no basis to infer it yet.
    Output 'unknown' for primary_use or budget_tier ONLY when the conversation truly gives no
    basis to infer them yet — do not guess just to avoid 'unknown'.

    The preference fields (price_sensitivity, form_factor, color_theme, rgb_lighting,
    noise_tolerance) are reported ONLY when the user volunteered them. They are stated tastes,
    not things to deduce from the use case: a gamer has not asked for RGB, and a $900 budget is
    not thereby a firm one. Their 'none'/'no_preference'/empty values mean "the user has not
    said", which is a useful answer — the build has sensible defaults for each.
    """

    conversation: str = dspy.InputField(
        desc="Full conversation history, each turn prefixed with 'User:' or 'Assistant:'"
    )

    primary_use: str = dspy.OutputField(
        desc="Exactly one of: gaming, streaming, video_editing, 3d_rendering, ai, "
        "server, software_dev, music_production, general, unknown — "
        "'server' is a machine built to run workloads rather than to be sat at: "
        "multi-GPU AI training or serving, HPC/simulation, virtualization or a "
        "homelab, a render farm node, or heavy self-hosting. Prefer 'server' over "
        "'ai' when the user describes multiple GPUs, rack or headless operation, "
        "ECC memory, 24/7 uptime, or a workstation/server platform (Threadripper, "
        "Threadripper PRO, Xeon, EPYC); prefer 'ai' for a single-GPU desktop that "
        "happens to run models. "
        "'unknown' if the conversation gives no basis to infer a use case yet"
    )
    gaming_resolution: str = dspy.OutputField(
        desc="Exactly one of: 1080p, 1440p, 4k, none — target gaming resolution; "
        "'none' unless primary_use is gaming or streaming"
    )
    gaming_fps: str = dspy.OutputField(
        desc="Exactly one of: 60, 120, 144, 240, none — target frame rate, inferred from "
        "monitor refresh rate or competitive-play cues when not stated outright; "
        "'none' unless primary_use is gaming or streaming"
    )
    streaming_style: str = dspy.OutputField(
        desc="Exactly one of: while_gaming, camera_only, none — whether the user streams "
        "gameplay or only camera/IRL/chatting content; 'none' unless primary_use is streaming"
    )
    ai_workload: str = dspy.OutputField(
        desc="Exactly one of: inference, training, image_gen, none — the dominant AI workload; "
        "'none' unless primary_use is ai"
    )
    ai_model_scale: str = dspy.OutputField(
        desc="Exactly one of: small, medium, large, none — LLM size the user wants to run: "
        "small ≈8B params or less, medium ≈9-34B, large ≈70B+; "
        "'none' unless primary_use is ai and the workload involves LLMs"
    )
    llm_quantization: str = dspy.OutputField(
        desc="Exactly one of: yes, no, unsure, none — whether the user is willing to "
        "run the model quantized (compressed weights: q4/q8/GGUF/AWQ/GPTQ/4-bit). "
        "'yes' when they accept it or already run quantized models; 'no' when they "
        "want full precision (fp16/bf16) or say quality must not drop; 'unsure' when "
        "they were asked and did not know or had no preference — 'unsure' is a real "
        "answer and must be reported rather than downgraded to 'none'. "
        "'none' ONLY when the subject has not come up at all. "
        "'none' unless the build is for running or training LLMs"
    )
    llm_context_tokens: str = dspy.OutputField(
        desc="Exactly one of: 4k, 8k, 32k, 128k, unsure, none — the context window the "
        "user wants to serve, rounded UP to the nearest listed size. Infer from what "
        "they describe feeding the model (whole codebases or long documents imply 32k+; "
        "chat implies 8k). 'unsure' when they were asked and had no view. "
        "'none' unless the build is for running or training LLMs"
    )
    server_workload: str = dspy.OutputField(
        desc="Exactly one of: ai_training, ai_serving, hpc, virtualization, storage, "
        "render_farm, none — what the machine is being built to run; "
        "'none' unless primary_use is server"
    )
    server_gpu_count: str = dspy.OutputField(
        desc="Exactly one of: 0, 1, 2, 4, 8, none — how many GPUs the build must "
        "host, rounded to the nearest supported slot count. This is what decides "
        "whether the build needs a high-lane-count platform (Threadripper, Xeon W, "
        "EPYC) instead of a desktop one; '0' for a CPU-only server. "
        "'none' unless primary_use is server"
    )
    editing_resolution: str = dspy.OutputField(
        desc="Exactly one of: 1080p, 4k, 6k_plus, none — resolution of the footage the user "
        "edits; 'none' unless primary_use is video_editing"
    )
    rendering_software: str = dspy.OutputField(
        desc="The 3D software or renderer the user works in (e.g. Blender, V-Ray, Cinema 4D, "
        "Maya), or empty string if not mentioned; empty unless primary_use is 3d_rendering"
    )
    workload_intensity: str = dspy.OutputField(
        desc="Exactly one of: light, moderate, heavy, none — scale of the workload for "
        "software_dev (codebase size, VMs/containers) or music_production "
        "(track/plugin counts); 'none' for other use cases"
    )
    budget_tier: str = dspy.OutputField(
        desc="Exactly one of: entry, mid, high, elite, custom, unknown — "
        "entry ≈$1000-1500, mid ≈$1500-2300, high ≈$2300-3500, elite ≈$3500+ — "
        "'custom' ONLY when the user has said outright that there is no budget "
        "limit ('money is no object', 'budget is unlimited', 'spend whatever it "
        "takes', 'price doesn't matter'). A large number, an enthusiastic tone, "
        "a premium use case, or 'I want the best' are NOT 'custom' — 'the best "
        "under $5000' is elite, and a stated figure is always the tier that "
        "figure falls in, however large. When in doubt between 'custom' and "
        "'elite', choose 'elite'. "
        "'unknown' if no budget signal at all has been given"
    )
    stated_budget_usd: str = dspy.OutputField(
        desc="The dollar figure the user named for the WHOLE build, digits only and "
        "no currency symbol or separators ('$5k' -> '5000', 'about twenty-five "
        "hundred' -> '2500'); 'none' if they never named one. Report the number "
        "they said, not a rounding of it and not your own estimate of what their "
        "described machine costs. A range is its upper end ('$2000-2500' -> "
        "'2500'). A figure attached to a single part ('$800 on the GPU') is not a "
        "build budget — leave it 'none'. budget_tier still reports the band this "
        "figure falls in; this field is what preserves the figure itself."
    )
    price_sensitivity: str = dspy.OutputField(
        desc="Exactly one of: firm, flexible, stretch, none — how hard the stated budget is. "
        "'firm' when the user frames it as a ceiling they will not cross ('max', 'absolute "
        "limit', 'can't go over'); 'flexible' when the figure is a target they'd bend a little "
        "for ('around', 'ish', 'roughly'); 'stretch' when they say outright they would pay more "
        "for the right part ('could go higher if it's worth it'). This is about the FIRMNESS of "
        "the number, not its size — a $900 budget can be 'stretch' and a $5000 one 'firm'. "
        "'none' if budget_tier is unknown or the user gave no signal either way"
    )
    form_factor: str = dspy.OutputField(
        desc="Exactly one of: atx, matx, itx, no_preference — desired case/motherboard size. "
        "'itx' for small-form-factor cues (SFF, tiny, shoebox, travel/LAN builds), 'matx' for "
        "'compact but not tiny', 'atx' for full-size or 'big case' cues. 'no_preference' unless "
        "the user actually expressed one — do NOT infer a size from the use case"
    )
    color_theme: str = dspy.OutputField(
        desc="The case/build color scheme the user asked for (e.g. 'black', 'white', "
        "'black & red'), or empty string if not mentioned"
    )
    rgb_lighting: str = dspy.OutputField(
        desc="Exactly one of: yes, no, none — whether the user wants RGB lighting. 'no' only "
        "when they said they don't want it (which is a real preference worth honoring); "
        "'none' when they never raised the subject"
    )
    noise_tolerance: str = dspy.OutputField(
        desc="Exactly one of: quiet, normal, none — how much fan noise the user will accept. "
        "'quiet' for explicit silence cues (bedroom, recording, 'as quiet as possible'); "
        "'normal' when they say noise doesn't bother them; 'none' if not mentioned"
    )
    games: str = dspy.OutputField(
        desc="Comma-separated game titles the user mentioned, or empty string if none"
    )
    workloads: str = dspy.OutputField(
        desc="Comma-separated workload descriptions the user mentioned, or empty string if none"
    )
    notes: str = dspy.OutputField(
        desc="Any remaining constraints or preferences not captured above, or empty string"
    )

    locked_parts: list[LockedPart] = dspy.OutputField(
        desc="Specific components the user has chosen for THIS build, one entry "
        "per slot, or [] if none. role is one of cpu, cooler, mobo, ram, "
        "storage, gpu, psu, case, fans. name is the part exactly as they said "
        "it ('RTX 5090', 'my old 3080', '7800X3D'). owned is true only when "
        "they already have the part in hand ('I'm reusing my 3080', 'I already "
        "bought the case') and false when they want it bought for this build "
        "('I want a 5090', 'get me a 9800X3D') — the two sound alike and the "
        "difference decides whether the part is charged against their budget, "
        "so read the tense carefully and default to false when genuinely "
        "unclear. quantity is how many of that part, normally 1. evidence is "
        "an exact quote. A part the user asks ABOUT, compares, or turns down "
        "is NOT a locked part; only one they have settled on for this build. "
        "Do not invent a part from a use case or a budget, and never turn a "
        "part the ASSISTANT suggested into a locked part"
    )

    profile_updates: list[ProfileUpdate] = dspy.OutputField(
        desc="Explicit set/clear/add/remove operations grounded in the latest user message; [] if none"
    )


class ExtractProfile(dspy.Module):
    def __init__(self) -> None:
        self.predict = dspy.ChainOfThought(ProfileExtraction)

    def forward(self, conversation: str) -> dspy.Prediction:
        return self.predict(conversation=conversation)


def load_program() -> ExtractProfile:
    return load_artifact(ExtractProfile(), "extractprofile")


def optimize(
    trainset: list[dspy.Example],
    metric,
    save: bool = True,
    **gepa_kwargs,
) -> ExtractProfile:
    """
    Run GEPA to optimize the profile extraction prompt.

    Each Example in trainset should have:
        - conversation (str)      ← formatted "User: ...\nAssistant: ..." history
        - primary_use (str)       ← gold label
        - budget_tier (str)       ← gold label
        - gaming_resolution / gaming_fps / streaming_style / ai_workload /
          ai_model_scale / server_workload / server_gpu_count /
          editing_resolution / workload_intensity (str)
                                  ← gold labels, 'none' if N/A
        - rendering_software (str) ← gold label, empty string if N/A
        - price_sensitivity / rgb_lighting / noise_tolerance (str)
                                  ← gold labels, 'none' if the user never said
        - form_factor (str)       ← gold label, 'no_preference' if the user never said
        - color_theme (str)       ← gold label, empty string if N/A
        - locked_parts (list)     ← gold LockedPart entries, [] if the user
                                    named no component of their own
        - games (str)             ← comma-separated, or empty string
        - workloads (str)         ← comma-separated, or empty string
        - notes (str)

    The metric follows GEPA's protocol — (gold, pred, trace, pred_name,
    pred_trace) returning dspy.Prediction(score, feedback). The feedback string
    is what GEPA reflects on to rewrite this instruction, so returning a bare
    float reduces the optimizer to random search.

    Weight primary_use and budget_tier heavily — they drive all downstream
    routing, and an error in either is unrecoverable by any later step.
    """
    return run_gepa(
        ExtractProfile(), trainset, metric, WEIGHTS_PATH, save=save, **gepa_kwargs
    )
