"""The DSPy stub answers each Decide* step with a real candidate.

With the bare "stub" placeholder, the CPU step could not resolve its answer
against the catalog, so every load-test build fell back to a reference build at
the first step without a dominant candidate, and a load test measured that
fast failure instead of the eleven-step pipeline.
"""

import json

from app.core.loadtest_stubs import _render_response


def _messages(outputs: list[tuple[str, str]], candidates: list[dict]) -> list[dict]:
    fields = "\n".join(
        f"{i}. `{name}` ({type_})" for i, (name, type_) in enumerate(outputs, 1)
    )
    system = f"Your output fields are:\n{fields}\n\nAll interactions will be..."
    user = (
        "[[ ## use_cases ## ]]\nUse cases: gaming\n\n"
        f"[[ ## candidates ## ]]\n{json.dumps(candidates)}\n\n"
        "Respond with the corresponding output fields, starting with ..."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _answers(reply: str) -> dict[str, str]:
    out = {}
    for chunk in reply.split("[[ ## ")[1:]:
        name, _, value = chunk.partition(" ## ]]")
        out[name] = value.strip()
    return out


def test_name_field_reads_the_first_candidates_name():
    reply = _render_response(
        _messages(
            [("reasoning", "str"), ("cpu_name", "str"), ("reason", "str")],
            [{"name": "Ryzen 7 7700X", "socket": "AM5"}, {"name": "Core i5-14600K"}],
        )
    )
    answers = _answers(reply)
    assert answers["cpu_name"] == "Ryzen 7 7700X"
    # Prose fields stay placeholders; only fields naming a candidate change.
    assert answers["reason"] == "stub"


def test_exact_and_suffix_and_plural_keys():
    rows = [{"ddr_gen": "DDR5", "chipset": "RTX 4070", "storage_group": "2TB nvme"}]
    answers = _answers(
        _render_response(
            _messages(
                [("ddr_gen", "str"), ("gpu_chipset", "str"), ("storage_groups", "str")],
                rows,
            )
        )
    )
    assert answers == {
        "ddr_gen": "DDR5",
        "gpu_chipset": "RTX 4070",
        "storage_groups": "2TB nvme",
        "completed": "",
    }


def test_case_options_are_three_different_rows():
    rows = [{"name": "H9 Flow"}, {"name": "H7 Flow"}, {"name": "H5 Flow"}]
    answers = _answers(
        _render_response(
            _messages(
                [("option_1", "str"), ("option_2", "str"), ("option_3", "str")], rows
            )
        )
    )
    assert [answers[f"option_{i}"] for i in (1, 2, 3)] == [
        "H9 Flow",
        "H7 Flow",
        "H5 Flow",
    ]


def test_gpu_step_gets_a_card():
    answers = _answers(
        _render_response(
            _messages(
                [
                    ("gpu_chipset", "str"),
                    ("gpu_count", "int"),
                    ("gpu_required", "bool"),
                ],
                [{"chipset": "RTX 4070"}],
            )
        )
    )
    assert answers["gpu_count"] == "1"
    assert answers["gpu_required"] == "true"


def test_no_candidates_keeps_the_generic_placeholders():
    system = "Your output fields are:\n1. `primary_use` (str)\n2. `notes` (str)\n\nAll"
    reply = _render_response(
        [{"role": "system", "content": system}, {"role": "user", "content": "hi"}]
    )
    assert _answers(reply) == {
        "primary_use": "gaming",
        "notes": "stub",
        "completed": "",
    }


def test_stubbed_extraction_is_a_complete_profile_that_builds(monkeypatch):
    """The real extraction, run against the stub, must yield a profile that goes
    straight to building. Anything is_profile_complete() still wants sends a
    load test down the question-asking path instead, which is how a stubbed
    price_sensitivity of "none" once turned every load-test turn into a single
    canned question with no build. And no field may carry the bare placeholder
    into a candidate filter: form_factor="stub" matched no motherboard at all."""
    import asyncio

    from app.core import loadtest_stubs
    from app.core.config import settings
    from app.core.loadtest import load_test_scope
    from app.schemas.chat import ChatMessage
    from app.services import chat_pipeline as cp

    monkeypatch.setattr(settings, "LOAD_TEST_SECRET", "s3cret", raising=False)
    monkeypatch.setattr(loadtest_stubs, "_DSPY_CALL_S", 0)

    with load_test_scope(True):
        profile = asyncio.run(
            cp.extract_profile([ChatMessage(role="user", content="gaming pc")])
        )

    assert cp.is_profile_complete(profile), cp._missing_fields(profile)
    assert profile.stated_budget_usd == 4000
    assert profile.form_factor is None
    assert profile.server_gpu_count is None
    assert "stub" not in profile.model_dump_json()
