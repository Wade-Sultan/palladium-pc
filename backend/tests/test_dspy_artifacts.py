"""The DSPy release loader: what it accepts, what it refuses, what it strips.

A release is only ever loaded whole. A manifest that names a module the
runtime does not have, omits one it does, or carries a module whose signature
no longer matches the code is rejected before any module is used, because
serving half a release is the kind of drift the manifest exists to prevent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.services.recommender import artifacts
from app.services.recommender.components.decidecpu import DecideCPU

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_dspy_release import build_manifest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_release(monkeypatch):
    monkeypatch.delenv("DSPY_ARTIFACT_URI", raising=False)
    monkeypatch.delenv("DSPY_ARTIFACT_SHA256", raising=False)
    artifacts.release.cache_clear()
    yield
    artifacts.release.cache_clear()


def _optimized_cpu(tmp_path: Path) -> Path:
    """A DecideCPU whose instructions GEPA 'rewrote', saved like a training
    run would, with an LM baked in. The thing the loader must strip."""
    program = DecideCPU()
    for _, predictor in program.named_predictors():
        predictor.signature = predictor.signature.with_instructions(
            "OPTIMIZED: pick the CPU with the best single-core score under budget."
        )
    state = program.dump_state()
    for name in state:
        state[name]["lm"] = {
            "model": "openai/attacker-model",
            "api_base": "http://evil.example/v1",
            "api_key": "sk-leaked",
            "model_type": "chat",
        }
    state["metadata"] = {"dependency_versions": {}}
    path = tmp_path / "decidecpu.json"
    path.write_text(json.dumps(state))
    return path


def _pin(monkeypatch, out: Path, sha: str | None):
    monkeypatch.setenv("DSPY_ARTIFACT_URI", str(out / "manifest.json"))
    if sha is not None:
        monkeypatch.setenv("DSPY_ARTIFACT_SHA256", sha)
    artifacts.release.cache_clear()


def test_no_pin_means_the_builtin_release():
    release_id, manifest, states = artifacts.release()
    assert release_id == "builtin"
    assert manifest is None and states == {}
    assert artifacts.release_id() == "builtin"


def test_an_exported_release_round_trips_through_the_loader(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    _, sha = build_manifest(out, {"decidecpu": _optimized_cpu(tmp_path)}, None)
    _pin(monkeypatch, out, sha)

    release_id, manifest, states = artifacts.release()

    assert release_id == sha
    assert set(states) == {"decidecpu"}
    assert set(manifest["modules"]) == set(artifacts.MODULES)
    loaded = artifacts.load_artifact(DecideCPU(), "decidecpu")
    ((_, predictor),) = loaded.named_predictors()
    assert predictor.signature.instructions.startswith("OPTIMIZED:")


def test_serialized_lm_settings_never_reach_the_program(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    _, sha = build_manifest(out, {"decidecpu": _optimized_cpu(tmp_path)}, None)
    _pin(monkeypatch, out, sha)

    loaded = artifacts.load_artifact(DecideCPU(), "decidecpu")

    for _, predictor in loaded.named_predictors():
        assert predictor.lm is None


def test_a_module_not_in_the_release_stays_builtin(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    _, sha = build_manifest(out, {"decidecpu": _optimized_cpu(tmp_path)}, None)
    _pin(monkeypatch, out, sha)

    from app.services.recommender.components.decidegpu import DecideGPU

    fresh = DecideGPU()
    assert artifacts.load_artifact(fresh, "decidegpu") is fresh


def test_a_tampered_manifest_is_refused(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    _, sha = build_manifest(out, {"decidecpu": _optimized_cpu(tmp_path)}, None)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["serving_model"] = "somebody/else"
    (out / "manifest.json").write_text(json.dumps(manifest))
    _pin(monkeypatch, out, sha)

    with pytest.raises(artifacts.ArtifactError, match="checksum"):
        artifacts.release()


def test_a_tampered_module_file_is_refused(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    _, sha = build_manifest(out, {"decidecpu": _optimized_cpu(tmp_path)}, None)
    (out / "decidecpu.json").write_text((out / "decidecpu.json").read_text() + "\n")
    _pin(monkeypatch, out, sha)

    with pytest.raises(
        artifacts.ArtifactError, match="Checksum mismatch for decidecpu"
    ):
        artifacts.release()


def test_a_release_for_another_serving_model_is_refused(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    build_manifest(out, {}, None)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["serving_model"] = "openrouter/other/model"
    raw = json.dumps(manifest).encode()
    (out / "manifest.json").write_bytes(raw)
    _pin(monkeypatch, out, artifacts.digest(raw))

    with pytest.raises(artifacts.ArtifactError, match="serving model"):
        artifacts.release()


def test_a_release_missing_a_module_is_refused(tmp_path, monkeypatch):
    out = tmp_path / "rel"
    build_manifest(out, {}, None)
    manifest = json.loads((out / "manifest.json").read_text())
    del manifest["modules"]["decidefans"]
    raw = json.dumps(manifest).encode()
    (out / "manifest.json").write_bytes(raw)
    _pin(monkeypatch, out, artifacts.digest(raw))

    with pytest.raises(artifacts.ArtifactError, match="every module"):
        artifacts.release()


def test_a_signature_change_since_export_is_refused(tmp_path, monkeypatch):
    """The schema hash covers field names, roles and types. The shape GEPA
    must not change, and a bundle exported against an older shape is stale."""
    out = tmp_path / "rel"
    build_manifest(out, {}, None)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["modules"]["decidecpu"]["schema_hash"] = "0" * 64
    raw = json.dumps(manifest).encode()
    (out / "manifest.json").write_bytes(raw)
    _pin(monkeypatch, out, artifacts.digest(raw))

    with pytest.raises(artifacts.ArtifactError, match="schema mismatch for decidecpu"):
        artifacts.release()


def test_a_paused_build_from_another_release_cannot_resume():
    with pytest.raises(artifacts.ArtifactError, match="different DSPy release"):
        artifacts.check_resume("deadbeef")
    artifacts.check_resume("builtin")


def test_the_export_refuses_an_unknown_module_name(tmp_path):
    with pytest.raises(artifacts.ArtifactError, match="Unknown module"):
        build_manifest(tmp_path / "rel", {"decidewidget": tmp_path / "x.json"}, None)


# --- releases exported under an older DSPy ---------------------------------
#
# A real release, exported by scripts/export_dspy_release.py under dspy 3.2.1
# with an optimized DecideCPU (rewritten instructions and one demo), committed
# with the prompt 3.2.1 rendered from it. It is what pins made before the 3.5
# upgrade look like, and it is the evidence behind LOADABLE_DSPY_VERSIONS.

RELEASE_3_2_1 = Path(__file__).parent / "fixtures" / "dspy_release_3_2_1"


def _messages(prompt) -> list[dict]:
    """ChatAdapter.format output as role/content dicts on any DSPy version.

    3.2.1 returns that list; 3.5 returns an lm15 Prompt carrying the same text.
    """
    if isinstance(prompt, list):
        return prompt
    system = [{"role": "system", "content": prompt.system}] if prompt.system else []
    return system + [
        {"role": m.role, "content": "".join(part.text for part in m.parts)}
        for m in prompt.messages
    ]


def _pin_3_2_1(monkeypatch):
    raw = (RELEASE_3_2_1 / "manifest.json").read_bytes()
    _pin(monkeypatch, RELEASE_3_2_1, artifacts.digest(raw))
    return json.loads(raw)


def test_a_3_2_1_release_loads_and_renders_the_prompt_it_was_scored_on(monkeypatch):
    """Loading is not enough: the instructions GEPA scored were scored inside a
    3.2.1 prompt, so the prompt this runtime sends must be that prompt."""
    import dspy

    from app.services.recommender import dspy_pipeline

    manifest = _pin_3_2_1(monkeypatch)
    assert manifest["dspy_version"] == "3.2.1"
    monkeypatch.setattr(dspy_pipeline, "RECOMMEND_MODEL", manifest["serving_model"])

    loaded = artifacts.load_artifact(DecideCPU(), "decidecpu")

    ((_, predictor),) = loaded.named_predictors()
    assert predictor.signature.instructions.startswith("OPTIMIZED")
    assert len(predictor.demos) == 1
    inputs = {k: f"q-{k}" for k in predictor.signature.input_fields}
    rendered = dspy.ChatAdapter().format(predictor.signature, predictor.demos, inputs)
    expected = json.loads((RELEASE_3_2_1 / "decidecpu.prompt.json").read_text())
    assert _messages(rendered) == expected


def test_a_release_from_an_unverified_dspy_version_is_refused(monkeypatch, tmp_path):
    """The allowlist is the policy, not "any older version": a version nobody
    checked could load cleanly and still send a different prompt."""
    from app.services.recommender import dspy_pipeline

    manifest = json.loads((RELEASE_3_2_1 / "manifest.json").read_text())
    manifest["dspy_version"] = "3.0.0"
    monkeypatch.setattr(dspy_pipeline, "RECOMMEND_MODEL", manifest["serving_model"])
    out = tmp_path / "rel"
    out.mkdir()
    (out / "decidecpu.json").write_bytes(
        (RELEASE_3_2_1 / "decidecpu.json").read_bytes()
    )
    raw = json.dumps(manifest).encode()
    (out / "manifest.json").write_bytes(raw)
    _pin(monkeypatch, out, artifacts.digest(raw))

    with pytest.raises(artifacts.ArtifactError, match="dspy 3.0.0"):
        artifacts.release()


def test_every_loadable_version_has_a_committed_release():
    """An allowlist entry without a fixture is an unchecked claim."""
    for version in artifacts.LOADABLE_DSPY_VERSIONS:
        fixture = Path(__file__).parent / "fixtures"
        fixture /= f"dspy_release_{version.replace('.', '_')}"
        manifest = json.loads((fixture / "manifest.json").read_text())
        assert manifest["dspy_version"] == version
