"""Assemble, verify, and describe an immutable DSPy release bundle.

A release is a directory holding one JSON file per optimized module plus a
manifest.json. The manifest is what the runtime pins (DSPY_ARTIFACT_URI points
at it, DSPY_ARTIFACT_SHA256 is its digest), and it names every module the
runtime knows about, optimized ones by file hash, the rest as `builtin`, so a
bundle can never be silently partial. See app/services/recommender/artifacts.py
for what the runtime checks on load.

    # From a training run that saved modules with `program.save(path)`:
    uv run python scripts/export_dspy_release.py export \\
        --out releases/2026-09-12 \\
        --module decidecpu=runs/gepa-cpu/decidecpu.json \\
        --module extractprofile=runs/gepa-extract/extractprofile.json \\
        --eval runs/eval-summary.json

    # Load the bundle exactly the way the serving process will:
    uv run python scripts/export_dspy_release.py verify releases/2026-09-12/manifest.json

    # Publish (immutable path, one directory per release):
    gsutil -m cp -r releases/2026-09-12 gs://<bucket>/dspy-releases/

Then set DSPY_ARTIFACT_URI=gs://<bucket>/dspy-releases/2026-09-12/manifest.json
and DSPY_ARTIFACT_SHA256=<digest printed by export> in the deployment config.
Rolling back is pointing those two values at the previous directory.

`verify` also runs the module JSON through the same loader the runtime uses,
which is what enforces that serialized LM settings (api_base, model, keys)
cannot follow a bundle into production: artifacts._load_state nulls them.
"""

# ruff: noqa: T201. A CLI; its output is the point.
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

import dspy

from app.services.recommender.artifacts import (
    MODULES,
    ArtifactError,
    _load_state,
    digest,
    new_program,
    schema_hash,
)


def build_manifest(
    out: Path, modules: dict[str, Path], evaluation: dict | None
) -> tuple[dict, str]:
    """Copy each optimized module into `out`, validate it against the live
    signature, and write manifest.json. Returns (manifest, manifest sha256)."""
    from app.services.recommender.dspy_pipeline import RECOMMEND_MODEL

    unknown = set(modules) - set(MODULES)
    if unknown:
        raise ArtifactError(f"Unknown module(s): {', '.join(sorted(unknown))}")

    out.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict] = {}
    for name in MODULES:
        program = new_program(name)
        entry: dict = {"schema_hash": schema_hash(program)}
        source = modules.get(name)
        if source is None:
            entry["builtin"] = True
        else:
            raw = source.read_bytes()
            state = json.loads(raw)
            # Fail here, at export, rather than at pod startup.
            _load_state(program, state)
            target = out / f"{name}.json"
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
            entry["builtin"] = False
            entry["sha256"] = digest(raw)
        entries[name] = entry

    manifest = {
        "format_version": 1,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "dspy_version": dspy.__version__,
        "serving_model": RECOMMEND_MODEL,
        "modules": entries,
        "evaluation": evaluation or {},
    }
    raw = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    (out / "manifest.json").write_bytes(raw)
    return manifest, digest(raw)


def _export(args: argparse.Namespace) -> int:
    modules: dict[str, Path] = {}
    for spec in args.module or []:
        name, _, path = spec.partition("=")
        if not path:
            print(f"--module expects name=path, got {spec!r}", file=sys.stderr)
            return 2
        modules[name] = Path(path)
    evaluation = json.loads(Path(args.eval).read_text()) if args.eval else None
    manifest, sha = build_manifest(Path(args.out), modules, evaluation)
    optimized = sorted(n for n, e in manifest["modules"].items() if not e["builtin"])
    print(f"wrote {Path(args.out) / 'manifest.json'}")
    print(f"serving_model: {manifest['serving_model']}")
    print(f"dspy_version:  {manifest['dspy_version']}")
    print(f"optimized:     {', '.join(optimized) or '(none: baseline release)'}")
    print("\nPin in the deployment config:")
    print(
        f"  DSPY_ARTIFACT_URI=gs://<bucket>/dspy-releases/{Path(args.out).name}/manifest.json"
    )
    print(f"  DSPY_ARTIFACT_SHA256={sha}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    os.environ["DSPY_ARTIFACT_URI"] = args.manifest
    if args.sha256:
        os.environ["DSPY_ARTIFACT_SHA256"] = args.sha256
    else:
        os.environ.pop("DSPY_ARTIFACT_SHA256", None)
    from app.services.recommender import artifacts

    artifacts.release.cache_clear()
    try:
        release_id, manifest, states = artifacts.release()
    except ArtifactError as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"OK release {release_id}")
    print(f"  serving_model: {manifest['serving_model']}")
    print(f"  optimized modules: {', '.join(sorted(states)) or '(none)'}")
    for name in sorted(states):
        program = artifacts.load_artifact(new_program(name), name)
        for pname, predictor in program.named_predictors():
            print(f"  {name}.{pname}: {len(predictor.demos)} demos, lm={predictor.lm}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="assemble a release directory")
    export.add_argument("--out", required=True, help="release directory to write")
    export.add_argument(
        "--module",
        action="append",
        metavar="NAME=PATH",
        help="optimized module JSON (from program.save); repeatable. "
        f"Names: {', '.join(MODULES)}",
    )
    export.add_argument("--eval", help="JSON file of evaluation results to embed")
    export.set_defaults(func=_export)

    verify = sub.add_parser("verify", help="load a manifest the way the runtime does")
    verify.add_argument("manifest", help="path or gs:// URI of manifest.json")
    verify.add_argument(
        "--sha256", help="expected manifest digest (required for gs://)"
    )
    verify.set_defaults(func=_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
