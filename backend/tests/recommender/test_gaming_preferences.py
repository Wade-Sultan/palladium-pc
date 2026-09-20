from app.schemas.chat import ChatMessage
from app.services.chat_pipeline import _explicit_gaming_preferences


def _user(text: str) -> ChatMessage:
    return ChatMessage(role="user", content=text)


def test_explicit_path_tracing_and_quality_are_captured():
    preferences = _explicit_gaming_preferences(
        [_user("I want Cyberpunk at ultra settings with path tracing and DLSS Quality")]
    )

    assert preferences == {
        "gaming_quality": "ultra",
        "gaming_ray_tracing": "path_tracing",
        "gaming_upscaling": "quality",
    }


def test_explicit_opt_outs_override_earlier_preferences():
    preferences = _explicit_gaming_preferences(
        [
            _user("Ray tracing and frame generation are fine"),
            _user("Actually, ray tracing off and no frame generation"),
        ]
    )

    assert preferences["gaming_ray_tracing"] == "off"
    assert preferences["gaming_frame_generation"] == "no"


def test_unmentioned_fidelity_settings_are_not_invented():
    assert _explicit_gaming_preferences([_user("I play Cyberpunk")]) == {}
