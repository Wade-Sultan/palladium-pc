"""A hand-written google_product response for the offer parser's tests.

Raw SerpApi responses are not committed (see .gitignore). This sample copies
only the SHAPE of the first real capture (2026-10-21, AMD Ryzen 7 7800X3D):
the field names the parser reads, and the figures the tests assert against.
Links, tokens, thumbnails, reviews and the rest of the response are left out.

What it preserves, because the parser's rules were written against it:
  - 3 stores per page, each with "additional_costs": "+tax" and shipping as
    its own field (why extracted_price is the pre-tax, shipping-free price)
  - a sale (original_price above price) and a free-gift line in
    details_and_offers, at the first store
  - price_range "$349-$416", with one live offer ($420) ABOVE its top: the
    evidence that the band is a typical-price band, not a live min/max
  - price_insights as dated per-store price changes ("Oct 12, 2026" format)

The real captures live in .local-seed/serpapi/ when present; the parser is also
run over those by test_offers_real_captures.py, which skips without them.
"""

from __future__ import annotations

import copy

_PRODUCT_7800X3D = {
    "search_metadata": {"id": "sample-0001", "status": "Success"},
    "search_parameters": {
        "engine": "google_product",
        "gl": "us",
        "hl": "en",
        "product_id": "14072215030660324520",
    },
    "product_results": {
        "title": "AMD Ryzen 7 7800X3D 8-Core Processor",
        "price_range": "$349-$416",
        "stores": [
            {
                "position": 1,
                "name": "Newegg.com",
                "title": "AMD Ryzen 7 7800X3D 8-Core 4.2 GHz Socket AM5 Desktop Processor",
                "tag": "Best price",
                "details_and_offers": [
                    "In stock online",
                    "Free delivery",
                    "30-day returns",
                    "Free ASRock Pro 850B Power Supply",
                ],
                "discount": "13% off",
                "price": "$389.00",
                "extracted_price": 389.0,
                "original_price": "$449.00",
                "extracted_original_price": 449.0,
                "additional_costs": "+tax",
                "shipping": "Free",
                "total": "$389.00",
                "extracted_total": 389.0,
                "merchant_id": "1000001",
            },
            {
                "position": 2,
                "name": "Best Buy",
                "title": "AMD Ryzen 7 7800X3D 8-Core 16-Thread Unlocked Desktop Processor",
                "details_and_offers": [
                    "In stock online",
                    "Free delivery by Fri",
                    "15-day returns",
                ],
                "discount": "6% off",
                "price": "$420.00",
                "extracted_price": 420.0,
                "original_price": "$449.00",
                "extracted_original_price": 449.0,
                "additional_costs": "+tax",
                "shipping": "Free",
                "total": "$420.00",
                "extracted_total": 420.0,
                "merchant_id": "1000002",
            },
            {
                "position": 3,
                "name": "Walmart",
                "title": "AMD Ryzen 7 7800X3D 8-Core 4.2 GHz Socket AM5 Desktop Processor",
                "details_and_offers": [
                    "In stock online",
                    "Free delivery between Wed - Fri",
                    "Free 90-day returns",
                ],
                "price": "$415.99",
                "extracted_price": 415.99,
                "additional_costs": "+tax",
                "shipping": "Free",
                "total": "$415.99",
                "extracted_total": 415.99,
                "merchant_id": "1000003",
            },
        ],
        "price_insights": {
            "price_history": True,
            "currency": "USD",
            "price_tracking_available": True,
            "stores": [
                {
                    "name": "Newegg.com",
                    "prices": [
                        {"date": "Oct 20, 2025", "price": 409.0},
                        {"date": "Sep 28, 2026", "price": 416.0},
                        {"date": "Oct 11, 2026", "price": 389.0},
                        {"date": "Oct 12, 2026", "price": 348.0},
                        {"date": "Oct 19, 2026", "price": 389.0},
                    ],
                },
                {
                    "name": "Best Buy",
                    "prices": [
                        {"date": "Oct 20, 2025", "price": 449.0},
                        {"date": "Aug 24, 2026", "price": 416.0},
                        {"date": "Sep 27, 2026", "price": 449.0},
                        {"date": "Oct 1, 2026", "price": 420.0},
                    ],
                },
                {
                    "name": "Walmart",
                    "prices": [
                        {"date": "Oct 20, 2025", "price": 389.0},
                        {"date": "Sep 24, 2026", "price": 415.99},
                        {"date": "Oct 16, 2026", "price": 348.0},
                        {"date": "Oct 18, 2026", "price": 415.99},
                    ],
                },
            ],
        },
    },
}


def product_7800x3d() -> dict:
    """A fresh copy, so a test editing one store cannot leak into another."""
    return copy.deepcopy(_PRODUCT_7800X3D)


# google_shopping for "AMD Ryzen 7 9800X3D", shaped on the real capture of
# 2026-10-21: no bare 9800X3D at all, sibling SKUs, and prebuilts built around
# the chip, one of which carries the exact model name (the case the identity
# rules cannot catch on their own). Ids and titles are trimmed; the traps are
# the real ones.
_SHOPPING_9800X3D_RESULTS = [
    {
        "position": 1,
        "title": "Elite Vector Gaming PC RX 9070XT 16GB | Ryzen 7 9800X3D | 32GB DDR5",
        "product_id": "9891712451573261353",
        "source": "Best Buy",
        "extracted_price": 2899.99,
    },
    {
        "position": 2,
        "title": "AMD Ryzen 7 7800X3D 8-Core Processor",
        "product_id": "14072215030660324520",
        "source": "Target",
        "extracted_price": 501.99,
        "multiple_sources": True,
    },
    {
        "position": 3,
        "title": "AMD Ryzen 7 9850X3D 8-Core Processor",
        "product_id": "14944560456875298988",
        "source": "Techinn.com",
        "extracted_price": 477.49,
        "multiple_sources": True,
    },
    {
        "position": 4,
        # Passes the model check: it IS a Ryzen 7 9800X3D, inside a desktop.
        "title": "ASUS ROG GM700 Gaming Desktop AMD Ryzen 7 9800X3D",
        "product_id": "7339108993938749717",
        "source": "Best Buy",
        "extracted_price": 2749.99,
        "multiple_sources": True,
    },
    {
        "position": 5,
        "title": "iBUYPOWER Trace Liquid Gaming R7 9800X3D 32GB",
        "product_id": "9288550374716871601",
        "source": "Best Buy",
        "extracted_price": 2149.99,
        "multiple_sources": True,
    },
]

# What a hit would look like had Google returned the CPU: its catalog title,
# the way the 7800X3D's appears above.
SHOPPING_9800X3D_TRUE_MATCH = {
    "position": 6,
    "title": "AMD Ryzen 7 9800X3D 8-Core, 16-Thread Desktop Processor",
    "product_id": "4300000000000000001",
    "source": "Newegg.com",
    "extracted_price": 459.0,
    "multiple_sources": True,
}


def shopping_9800x3d(*extra: dict) -> dict:
    """The search response, optionally with extra results appended."""
    results = copy.deepcopy(_SHOPPING_9800X3D_RESULTS)
    results.extend(copy.deepcopy(list(extra)))
    return {
        "search_metadata": {"id": "sample-0002", "status": "Success"},
        "search_parameters": {"engine": "google_shopping", "q": "AMD Ryzen 7 9800X3D"},
        "shopping_results": results,
    }
