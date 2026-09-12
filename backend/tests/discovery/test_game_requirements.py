import asyncio
import importlib.util
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.discovery import extract
from app.services.discovery.dedup import CatalogCandidate
from app.services.discovery.game_requirements import match_reference
from app.services.discovery.validate import validate_item


@pytest.fixture
def runner(monkeypatch):
    # Import the actual orchestration with the database boundary replaced;
    # never construct a Cloud SQL connector or load a real session factory.
    @asynccontextmanager
    async def session():
        yield object()

    monkeypatch.setitem(
        sys.modules, "app.core.db", SimpleNamespace(AsyncSessionLocal=session)
    )
    spec = importlib.util.spec_from_file_location(
        "discovery_runner_test", Path(extract.__file__).with_name("runner.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def req(name, role="cpu", tier="minimum"):
    return {
        "published_name": name,
        "role": role,
        "tier": tier,
        "snippet": f"{tier}: {name}",
        "min_ram_gb": None,
    }


def test_reference_matching_never_uses_nearby_sku():
    candidate = CatalogCandidate(uuid.uuid4(), "NVIDIA GeForce RTX 5070 Ti")
    assert match_reference("RTX 5070", [candidate]) is None
    assert match_reference("RTX 5070 Ti", [candidate]) == candidate.id


def test_reference_matching_refuses_ambiguous_catalog_duplicates():
    candidates = [CatalogCandidate(uuid.uuid4(), "AMD Ryzen 5 3600") for _ in range(2)]
    assert match_reference("Ryzen 5 3600", candidates) is None


def test_game_accepts_minimum_only_and_cpu_alternatives():
    requirements = [
        req("Intel Core i5-8400"),
        req("AMD Ryzen 5 3600"),
        req("GTX 1060", "gpu"),
    ]
    assert validate_item(
        "game", {"name": "Example Quest", "requirements": requirements}
    ) == ("passed", None)


def test_game_without_published_hardware_fails():
    assert (
        validate_item("game", {"name": "Example Quest", "requirements": []})[0]
        == "failed"
    )


def test_dependencies_reuse_existing_and_stage_missing_once(runner, monkeypatch):
    cpu_id = uuid.uuid4()

    async def catalog(_db, category):
        return (
            [CatalogCandidate(cpu_id, "AMD Ryzen 5 3600")] if category == "cpu" else []
        )

    monkeypatch.setattr(runner.crud, "get_dedup_candidates", catalog)
    discovered_id = uuid.uuid4()
    discover = AsyncMock(return_value=runner._ItemOutcome(2, True, None, discovered_id))
    monkeypatch.setattr(runner, "_discover_one", discover)
    run_id = uuid.uuid4()
    requirements = [
        req("Ryzen 5 3600"),
        req("GTX 1060", "gpu"),
        req("GTX 1060", "gpu", "recommended"),
    ]
    dependencies, sources = asyncio.run(
        runner._game_dependencies(run_id, requirements, "session", [])
    )
    assert len(dependencies) == 2
    assert dependencies[0]["catalog_id"] == str(cpu_id)
    assert dependencies[1]["discovered_item_id"] == str(discovered_id)
    assert sources == 2
    discover.assert_awaited_once_with(
        run_id, "GTX 1060", "gpu_chipset", "session", [], reference_only=True
    )


def test_failed_dependency_stays_unresolved(runner, monkeypatch):
    monkeypatch.setattr(runner.crud, "get_dedup_candidates", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        runner,
        "_discover_one",
        AsyncMock(return_value=runner._ItemOutcome(0, False, "no official evidence")),
    )
    dependencies, _ = asyncio.run(
        runner._game_dependencies(uuid.uuid4(), [req("Example CPU")], "session", [])
    )
    assert dependencies[0]["catalog_id"] is None
    assert dependencies[0]["discovered_item_id"] is None
    assert dependencies[0]["error"] == "no official evidence"


def test_inactive_parts_are_included_in_discovery_dedup(runner):
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(
        all=lambda: [(uuid.uuid4(), "Old CPU", None)]
    )
    candidates = asyncio.run(runner.crud.get_dedup_candidates(db, "cpu"))
    assert len(candidates) == 1
    statement = str(db.execute.call_args.args[0])
    assert "is_active" not in statement


def test_stage_rejects_unconfirmed_before_any_database_call(runner):
    with pytest.raises(ValueError, match="verification"):
        asyncio.run(
            runner._stage(
                uuid.uuid4(),
                "cpu",
                {"name": "Rumored CPU"},
                {},
                None,
                [],
                "Rumored CPU",
            )
        )
