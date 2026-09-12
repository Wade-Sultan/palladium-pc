"""Adjacent SKUs must not pass just because almost all title tokens match."""

import pytest

from app.services.pricing_etl import product_identity as identity
from app.services.pricing_etl import stats, title_match


@pytest.mark.parametrize(
    "query,title",
    [
        ("NVIDIA GeForce RTX 5070", "NVIDIA GeForce RTX 5070 Ti"),
        ("NVIDIA GeForce RTX 5070 Ti", "NVIDIA GeForce RTX 5070"),
        ("NVIDIA GeForce RTX 5070", "NVIDIA GeForce RTX 5080"),
        ("NVIDIA GeForce RTX 5080", "NVIDIA GeForce RTX 5090"),
        ("MSI RTX 4070 Ti", "MSI RTX 4070 Ti SUPER"),
        ("MSI RTX 4070 SUPER", "MSI RTX 4070 Ti"),
        ("GeForce GTX 1080", "GeForce GTX 1080Ti"),
        ("Radeon RX 9070", "Radeon RX 9070XT"),
        ("Radeon RX 7900 XT", "Radeon RX 7900 XTX"),
        ("Radeon RX 7900 XT", "Radeon RX 7900 GRE"),
        ("Intel Arc B580", "Intel Arc B570"),
        ("AMD Ryzen 7 9800X3D", "AMD Ryzen 7 7800X3D"),
        ("AMD Ryzen 7 9700X", "AMD Ryzen 7 9700"),
        ("AMD Ryzen 5 5600", "AMD Ryzen 5 5600G"),
        ("Intel Core i7-14700K", "Intel Core i7-14700KF"),
        ("Intel Core i7-14700K", "Intel Core i7-14700"),
        ("Intel Core Ultra 7 265K", "Intel Core Ultra 7 265KF"),
        ("AMD Ryzen Threadripper PRO 7995WX", "AMD Ryzen Threadripper PRO 7985WX"),
        ("NVIDIA GeForce RTX 5070", "NVIDIA GeForce RTX 5070 / RTX 5070 Ti"),
    ],
)
def test_adjacent_models_rejected_despite_high_similarity(query, title):
    score = title_match.similarity(query, title)
    assert score >= title_match.SIMILARITY_THRESHOLD
    assert (
        title_match.exclusion_reason(score, title, part_title=query)
        == identity.REASON_MODEL_MISMATCH
    )


@pytest.mark.parametrize(
    "query,title",
    [
        ("NVIDIA GeForce RTX 5070", "MSI GeForce RTX 5070 Gaming X OC"),
        ("NVIDIA GeForce RTX 5070 Ti", "MSI geforce RTX5070TI Gaming Trio"),
        ("NVIDIA GeForce RTX 5070 Ti", "NVIDIA GeForce RTX™ 5070 Ti"),
        ("RTX 4070 Ti SUPER", "ASUS GeForce RTX-4070-Ti-Super OC"),
        ("RTX 5070 Ti", "NVIDIA GeForce RTX 5070‑Ti"),
        ("Radeon RX 9070 XT", "Sapphire Radeon RX9070XT NITRO+"),
        ("Intel Arc B580", "ASRock Intel ARC-B580 Challenger"),
        ("AMD Ryzen 7 9800X3D", "AMD Ryzen 7 9800 X3D 8-Core Processor"),
        ("Intel Core i7-14700K", "Intel Core i7 14700k Processor"),
        ("Intel Core Ultra 7 265K", "Intel Core Ultra 7 265 K Processor"),
        ("Samsung 990 Pro 2TB", "Samsung 990 PRO 2 TB NVMe SSD"),
        (
            "Corsair DDR5 32GB (2x16GB) 6000MHz CL30",
            "Corsair DDR5-6000 32 GB (2 × 16 GB) CL30",
        ),
        ("Corsair DDR5 32GB (2x16GB)", "Corsair DDR5 (2x16GB) RAM"),
        ("Corsair DDR5 32GB 6000MHz", "Corsair DDR5-6000 32GB 6000 MT/s"),
        (
            "NZXT H9 Flow ATX Mid-Tower Case Black",
            "NZXT H9 Flow ATX Mid-Tower Case Black",
        ),
    ],
)
def test_same_product_accepts_formatting_and_board_names(query, title):
    score = title_match.similarity(query, title)
    assert title_match.exclusion_reason(score, title, part_title=query) is None


@pytest.mark.parametrize(
    "query,title,reason",
    [
        ("RTX 5070", "NVIDIA GeForce Graphics Card", identity.REASON_MODEL_MISSING),
        ("RTX 5070", "GeForce RTX 50700", identity.REASON_MODEL_MISSING),
        (
            "Samsung 990 Pro 2TB",
            "Samsung 990 Pro 4TB",
            identity.REASON_CAPACITY_MISMATCH,
        ),
        (
            "Samsung 990 Pro 2TB",
            "Samsung 990 Pro SSD",
            identity.REASON_CAPACITY_MISSING,
        ),
        (
            "Samsung 990 Pro 2TB",
            "Samsung 990 Pro 1TB / 2TB / 4TB",
            identity.REASON_CAPACITY_MISMATCH,
        ),
        ("RTX 5060 Ti 16GB", "RTX 5060 Ti 8GB", identity.REASON_CAPACITY_MISMATCH),
        (
            "Corsair DDR5 32GB (2x16GB)",
            "Corsair DDR5 64GB (2x32GB)",
            identity.REASON_CAPACITY_MISMATCH,
        ),
        (
            "Corsair DDR5 32GB (2x16GB)",
            "Corsair DDR5 32GB (1x32GB)",
            identity.REASON_MEMORY_SPEC_MISMATCH,
        ),
        (
            "Corsair DDR5 32GB",
            "Corsair DDR4 32GB",
            identity.REASON_MEMORY_SPEC_MISMATCH,
        ),
        (
            "Corsair DDR5-6000 32GB",
            "Corsair DDR5-5200 32GB",
            identity.REASON_MEMORY_SPEC_MISMATCH,
        ),
        (
            "Corsair DDR5 32GB 6000MHz CL30",
            "Corsair DDR5 32GB 6000MHz CL36",
            identity.REASON_MEMORY_SPEC_MISMATCH,
        ),
    ],
)
def test_missing_identity_or_conflicting_specs(query, title, reason):
    assert identity.exclusion_reason(query, title) == reason


def test_wrong_model_majority_cannot_set_the_price():
    query = "NVIDIA GeForce RTX 5070"
    offers = [
        ("NVIDIA GeForce RTX 5070", 549),
        ("MSI GeForce RTX 5070 OC", 559),
        ("ASUS GeForce RTX 5070", 569),
        ("NVIDIA GeForce RTX 5070 Ti", 799),
        ("MSI GeForce RTX 5070 Ti OC", 819),
        ("ASUS GeForce RTX 5070 Ti", 839),
        ("Gigabyte GeForce RTX 5070 Ti", 849),
    ]
    accepted = [
        price
        for title, price in offers
        if title_match.exclusion_reason(
            title_match.similarity(query, title), title, part_title=query
        )
        is None
    ]
    result = stats.compute_stats(accepted)
    assert result is not None
    assert result.n_kept == 3
    assert result.applied_cents == 55900


def test_wrong_models_cannot_satisfy_minimum_sample_size():
    query = "RTX 5070"
    titles = ["RTX 5070", "RTX 5070 Ti", "RTX 5080"]
    accepted = [
        549
        for title in titles
        if title_match.exclusion_reason(
            title_match.similarity(query, title), title, part_title=query
        )
        is None
    ]
    result = stats.compute_stats(accepted)
    assert result is not None
    assert result.n_kept == 1
    assert result.applied_cents is None
