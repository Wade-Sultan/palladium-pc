from app.data.refbuilds import BUILDS, Build
from app.schemas.chat import BuildProfile


def resolve_build(profile: BuildProfile) -> tuple[str, Build]:
    """Map a BuildProfile to the best matching pre-defined build key."""

    use = profile.primary_use
    resolution = profile.gaming_resolution
    budget = profile.budget_tier  # entry | mid | high | elite

    # Local LLM / AI workloads
    if use == "local_llm":
        return "local_llm", BUILDS["local_llm"]

    # Video editing / content creation
    if use == "video_editing":
        return "creator_1080p_editing", BUILDS["creator_1080p_editing"]

    # Gaming resolution + budget ladder
    if use == "gaming":
        if budget == "entry":
            return "entry_gaming_1080p", BUILDS["entry_gaming_1080p"]
        if resolution == "1440p":
            if budget == "high" or budget == "elite":
                return "high_gaming_1440p", BUILDS["high_gaming_1440p"]
            return "mid_gaming_1440p", BUILDS["mid_gaming_1440p"]
        # Default 1080p mid
        return "mid_gaming_1080p", BUILDS["mid_gaming_1080p"]

    # Fallback
    return "budget_allrounder", BUILDS["budget_allrounder"]