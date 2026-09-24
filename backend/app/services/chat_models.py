from __future__ import annotations

import os


class ChatModelConfig:
    # Extraction uses DSPy. Keep its effective default aligned with the build
    # model; opt into a smaller model after checking extraction quality.
    EXTRACT_MODEL: str = os.getenv("CHAT_EXTRACT_MODEL") or os.getenv(
        "RECOMMEND_MODEL", "openrouter/google/gemma-4-31b-it"
    )
    # Keep the larger model for the recommendation (needs nuance and personality)
    RECOMMEND_MODEL: str = os.getenv("CHAT_RECOMMEND_MODEL", "google/gemma-4-31b-it")
    ELICIT_MODEL: str = os.getenv("CHAT_ELICIT_MODEL", "google/gemma-4-31b-it")
    # Question ordering only. The router returns a single integer index into a
    # list the caller already computed, so this is the smallest model in the
    # stack on purpose. It runs on every elicitation turn and it cannot decide
    # anything except which of several known-missing items to raise first.
    ROUTE_MODEL: str = os.getenv("CHAT_ROUTE_MODEL", "google/gemma-3-4b-it")
    # Qwen's /no_think switch is useful for this one-number decision on a local
    # reasoning model. Keep it opt-in so other models and OpenRouter prompts are
    # unchanged. The model still chooses among the same missing fields.
    ROUTE_NO_THINK: bool = os.getenv("CHAT_ROUTE_NO_THINK", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    # MiniMax M3 for parts-discovery spec extraction: multimodal (rasterized
    # PDF spec sheets) and cheap enough for 2-3 extraction calls per SKU.
    DISCOVERY_EXTRACT_MODEL: str = os.getenv(
        "DISCOVERY_EXTRACT_MODEL", "minimax/minimax-m3"
    )

    # --- Output token budgets -------------------------------------------------
    # Tight on purpose: the router returns one integer, the recommendation is a
    # sub-50-word lead-in, the question is one sentence. Every default here is
    # calibrated for a model that answers directly.
    #
    # A REASONING MODEL NEEDS ALL OF THESE RAISED, and the failure is silent
    # rather than loud. Thinking tokens are billed against the same budget as
    # the answer, so a model that spends ~1000 of them hits the cap mid-thought
    # and returns finish_reason=length with EMPTY content, not an error. The
    # router then falls back to missing[0], the question and the lead-in stream
    # as nothing, and extraction yields a profile of 'unknown' that
    # is_profile_complete() rejects forever, so the turn never reaches the
    # builder. Raise them via the env vars below when pointing LLM_BASE_URL at
    # a local reasoning model; see deploy/overlays/local/patches/config-local.yaml.
    ROUTE_MAX_TOKENS: int = int(os.getenv("CHAT_ROUTE_MAX_TOKENS", "8"))
    RECOMMEND_MAX_TOKENS: int = int(os.getenv("CHAT_RECOMMEND_MAX_TOKENS", "128"))
    ELICIT_MAX_TOKENS: int = int(os.getenv("CHAT_ELICIT_MAX_TOKENS", "256"))
    # The post-build Q&A answer (recommender/discussion.py). Larger than the
    # lead-in because it answers a question rather than introducing a card,
    # and it needs the same raise as the others under a reasoning model.
    DISCUSS_MAX_TOKENS: int = int(os.getenv("CHAT_DISCUSS_MAX_TOKENS", "700"))

    @classmethod
    def get_extract_model(cls) -> str:
        return cls.EXTRACT_MODEL

    @classmethod
    def get_recommend_model(cls) -> str:
        return cls.RECOMMEND_MODEL

    @classmethod
    def get_elicit_model(cls) -> str:
        return cls.ELICIT_MODEL

    @classmethod
    def get_route_model(cls) -> str:
        return cls.ROUTE_MODEL

    @classmethod
    def get_discovery_extract_model(cls) -> str:
        return cls.DISCOVERY_EXTRACT_MODEL
