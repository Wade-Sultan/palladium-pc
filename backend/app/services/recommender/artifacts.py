"""Immutable DSPy JSON releases, fetched once and verified before serving."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import dspy

MODULES = {
    "extractprofile": "ExtractProfile",
    "decideddr": "DecideDDR",
    "decidecpu": "DecideCPU",
    "decidecpucooler": "DecideCPUCooler",
    "decidemotherboard": "DecideMotherboard",
    "decideram": "DecideRAM",
    "decidestorage": "DecideStorage",
    "decidegpu": "DecideGPU",
    "decidepsu": "DecidePSU",
    "decidecase": "DecideCase",
    "decidefans": "DecideFans",
    "followup": "FollowupLookup",
}


class ArtifactError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def schema_hash(program) -> str:
    # Instructions and field descriptions are deliberately excluded: GEPA is
    # allowed to optimize those. Names, roles, and types must remain compatible.
    shape = {
        name: [
            (
                key,
                str(field.annotation),
                field.json_schema_extra.get("__dspy_field_type"),
            )
            for key, field in pred.signature.fields.items()
        ]
        for name, pred in program.named_predictors()
    }
    return digest(json.dumps(shape, sort_keys=True).encode())


def new_program(name: str):
    if name == "followup":
        from app.services.recommender.discussion import FollowupProgram

        return FollowupProgram()
    module = importlib.import_module(f"app.services.recommender.components.{name}")
    return getattr(module, MODULES[name])()


def _read(uri: str, limit: int) -> bytes:
    if uri.startswith("gs://"):
        from google.cloud import storage

        parsed = urlparse(uri)
        data = (
            storage.Client()
            .bucket(parsed.netloc)
            .blob(parsed.path.lstrip("/"))
            .download_as_bytes(end=limit, timeout=60)
        )
    else:
        path = Path(uri)
        if path.stat().st_size > limit:
            raise ArtifactError("Artifact exceeds size limit")
        data = path.read_bytes()
    if len(data) > limit:
        raise ArtifactError("Artifact exceeds size limit")
    return data


@cache
def release() -> tuple[str, dict | None, dict[str, dict]]:
    uri = os.getenv("DSPY_ARTIFACT_URI", "")
    if not uri:
        # Baseline is an explicit release too; do not silently load stray files
        # left in an image by an old training run.
        return "builtin", None, {}
    raw = _read(uri, 1024 * 1024)
    actual = digest(raw)
    expected = os.getenv("DSPY_ARTIFACT_SHA256", "")
    if uri.startswith("gs://") and not expected:
        raise ArtifactError("GCS releases require DSPY_ARTIFACT_SHA256")
    if expected and expected != actual:
        raise ArtifactError("DSPy manifest checksum mismatch")
    manifest = json.loads(raw)
    if (
        manifest.get("format_version") != 1
        or manifest.get("dspy_version") != dspy.__version__
    ):
        raise ArtifactError("DSPy release format/version mismatch")
    from app.services.recommender.dspy_pipeline import RECOMMEND_MODEL

    if manifest.get("serving_model") != RECOMMEND_MODEL:
        raise ArtifactError(
            "DSPy release was not evaluated for the configured serving model"
        )
    entries = manifest.get("modules", {})
    if set(entries) != set(MODULES):
        raise ArtifactError(
            "Release must declare every module, including builtin modules"
        )
    states = {}
    base = uri.rsplit("/", 1)[0] if "/" in uri else "."
    for name, entry in entries.items():
        if entry.get("builtin") is True:
            continue
        data = _read(f"{base}/{name}.json", 20 * 1024 * 1024)
        if digest(data) != entry.get("sha256"):
            raise ArtifactError(f"Checksum mismatch for {name}")
        states[name] = json.loads(data)
    # Validate the entire bundle before any module can use it.
    for name, entry in entries.items():
        program = new_program(name)
        if schema_hash(program) != entry.get("schema_hash"):
            raise ArtifactError(f"Signature schema mismatch for {name}")
        if name in states:
            _load_state(program, states[name])
    return actual, manifest, states


def _load_state(program, state: dict):
    state = json.loads(json.dumps(state))
    expected = dict(program.named_parameters())
    if set(state) - {"metadata"} != set(expected):
        raise ArtifactError("Unexpected predictor structure")
    for name, predictor in expected.items():
        saved = state[name]
        if set(saved) - {"traces", "train", "demos", "signature", "lm", "config"}:
            raise ArtifactError("Unexpected predictor state")
        expected_fields = list(predictor.signature.fields)
        saved_fields = saved.get("signature", {}).get("fields", [])
        # DSPy stores field descriptors in declaration order.
        if len(saved_fields) != len(expected_fields):
            raise ArtifactError("Saved signature field count mismatch")
        saved["lm"] = None
    program.load_state(state)
    for _, predictor in program.named_predictors():
        predictor.lm = None  # session_lm controls endpoint, credentials and usage.
    return program


def load_artifact(program, name: str):
    _, _, states = release()
    return _load_state(program, states[name]) if name in states else program


def release_id() -> str:
    return release()[0]


def check_resume(release_value: str) -> None:
    if release_value != release_id():
        raise ArtifactError(
            "This paused build used a different DSPy release; start a new build"
        )
