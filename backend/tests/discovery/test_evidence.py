"""Synthetic source documents; no live products, prices, LLM or web calls."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.discovery import evidence, extract
from app.services.discovery.fetch import FetchedDoc


@pytest.mark.parametrize(
    "url,category",
    [
        ("https://www.amd.com/en/products/test.html", "cpu"),
        ("https://www.nvidia.com/en-us/geforce/graphics-cards/test/", "gpu_chipset"),
        ("https://store.steampowered.com/app/1234/Example_Quest/", "game"),
        ("https://store.epicgames.com/en-US/p/example-quest", "game"),
    ],
)
def test_official_product_sources(url, category):
    assert evidence.official_source(url, category)


@pytest.mark.parametrize(
    "url,category",
    [
        ("https://www.amd.com.attacker.example/product", "cpu"),
        ("https://amd.com@attacker.example/product", "cpu"),
        ("https://community.amd.com/product", "cpu"),
        ("https://www.nvidia.com/en-us/geforce/forums/rumor", "gpu_chipset"),
        ("https://store.steampowered.com/news/group/123", "game"),
        ("https://steamcommunity.com/app/123/discussions/0", "game"),
        ("https://news.example/officially-announced-cpu", "cpu"),
        ("http://www.amd.com/product", "cpu"),
    ],
)
def test_untrusted_sources_never_supply_catalog_facts(url, category):
    assert not evidence.official_source(url, category)


@pytest.mark.parametrize(
    "prefix",
    ["Rumor:", "Leaked:", "Reportedly", "Unconfirmed specs:", "Our prediction:"],
)
def test_quote_cannot_strip_speculative_context(prefix):
    assert not evidence.grounded_quote(
        "Example CPU has eight cores.", f"{prefix} Example CPU has eight cores."
    )


def test_fabricated_quote_is_not_evidence():
    assert not evidence.grounded_quote(
        "Example CPU is released", "An unrelated CPU is released"
    )


def game_payload():
    text = "Example Quest is officially announced. Minimum CPU: Intel Core i5-8400. Minimum GPU: NVIDIA GeForce GTX 1060."
    payload = {
        key: {"value": None, "snippet": None}
        for key in extract.GameExtraction.model_fields
    }
    payload.update(
        {
            "name": {
                "value": "Example Quest",
                "snippet": "Example Quest is officially announced.",
            },
            "confirmation_status": {
                "value": "officially_announced",
                "snippet": "Example Quest is officially announced.",
            },
            "requirements": {
                "value": [
                    {
                        "tier": "minimum",
                        "role": "cpu",
                        "published_name": "Intel Core i5-8400",
                        "snippet": "Minimum CPU: Intel Core i5-8400.",
                        "min_ram_gb": None,
                    },
                    {
                        "tier": "minimum",
                        "role": "gpu",
                        "published_name": "NVIDIA GeForce GTX 1060",
                        "snippet": "Minimum GPU: NVIDIA GeForce GTX 1060.",
                        "min_ram_gb": None,
                    },
                ],
                "snippet": "Minimum CPU: Intel Core i5-8400. Minimum GPU: NVIDIA GeForce GTX 1060.",
            },
        }
    )
    return text, payload


def run_extraction(
    monkeypatch,
    text,
    payload,
    url="https://store.steampowered.com/app/1234/Example_Quest/",
):
    response = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload)),
                finish_reason="stop",
            )
        ],
    )
    call = AsyncMock(return_value=response)
    monkeypatch.setattr(
        extract,
        "_get_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=call))
        ),
    )
    monkeypatch.setattr(extract, "_usage_from_openai", lambda usage: {})
    doc = FetchedDoc(url=url, kind="markdown", text=text)
    result = asyncio.run(
        extract.extract_from_source(doc, "game", "Example Quest", None, [])
    )
    return result, call


def test_confirmed_game_preserves_only_published_tier(monkeypatch):
    text, payload = game_payload()
    result, _ = run_extraction(monkeypatch, text, payload)
    assert result is not None
    fields, provenance = extract.unwrap(
        result, "https://store.steampowered.com/app/1234/"
    )
    assert len(fields["requirements"]) == 2
    assert {r["tier"] for r in fields["requirements"]} == {"minimum"}
    assert fields["requirements"][0]["published_name"] == "Intel Core i5-8400"
    assert provenance["requirements"]["snippet"]


@pytest.mark.parametrize(
    "mutation",
    [
        "unconfirmed",
        "invented_quote",
        "invented_model",
        "invented_game",
        "rumor_context",
    ],
)
def test_unsupported_extraction_is_discarded(monkeypatch, mutation):
    text, payload = game_payload()
    if mutation == "unconfirmed":
        payload["confirmation_status"]["value"] = "unconfirmed"
    elif mutation == "invented_quote":
        payload["confirmation_status"]["snippet"] = (
            "The publisher confirmed something not on the page."
        )
    elif mutation == "invented_model":
        payload["requirements"]["value"][0]["published_name"] = "Intel Core i5-9400"
    elif mutation == "invented_game":
        payload["name"]["value"] = "Example Quest 2"
    else:
        text = "Rumor: " + text
    result, _ = run_extraction(monkeypatch, text, payload)
    assert result is None


def test_unofficial_page_is_skipped_before_llm(monkeypatch):
    text, payload = game_payload()
    result, call = run_extraction(
        monkeypatch, text, payload, "https://news.example/predicted-game-specs"
    )
    assert result is None
    call.assert_not_awaited()


def test_staging_rejects_legacy_or_unverified_evidence():
    assert evidence.confirmation_error("cpu", {"name": "Example CPU"}, {})
    assert evidence.confirmation_error(
        "cpu",
        {"confirmation_status": "released"},
        {
            "confirmation_status": {
                "source_url": "https://amd.com/product",
                "snippet": "Released",
            }
        },
    )
