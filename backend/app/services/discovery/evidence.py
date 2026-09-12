"""Fail-closed source and quotation checks for catalog discovery.

Search ranking and repeated reporting do not establish a product's existence.
Only official sources can supply catalog facts. Extend these domain lists when
onboarding another manufacturer/publisher; do not add news or rumor sites.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_SILICON_DOMAINS = {"amd.com", "intel.com", "nvidia.com"}
_HARDWARE_DOMAINS = _SILICON_DOMAINS | {
    "asus.com",
    "asrock.com",
    "msi.com",
    "gigabyte.com",
    "sapphiretech.com",
    "powercolor.com",
    "xfxforce.com",
    "pny.com",
    "zotac.com",
    "palit.com",
    "gainward.com",
    "evga.com",
    "corsair.com",
    "gskill.com",
    "kingston.com",
    "crucial.com",
    "micron.com",
    "samsung.com",
    "wd.com",
    "westerndigital.com",
    "sandisk.com",
    "seagate.com",
    "solidigm.com",
    "sabrent.com",
    "seasonic.com",
    "bequiet.com",
    "coolermaster.com",
    "thermaltake.com",
    "noctua.at",
    "arctic.de",
    "deepcool.com",
    "nzxt.com",
    "fractal-design.com",
    "lian-li.com",
    "antec.com",
    "phanteks.com",
    "silverstonetek.com",
    "adata.com",
    "xpg.com",
    "teamgroupinc.com",
    "lexar.com",
    "montechpc.com",
    "thermalright.com",
}
_GAME_DOMAINS = {
    "ea.com",
    "ubisoft.com",
    "playstation.com",
    "bethesda.net",
    "bethesda.com",
    "xbox.com",
    "blizzard.com",
    "battle.net",
    "riotgames.com",
    "rockstargames.com",
    "cdprojektred.com",
    "cyberpunk.net",
    "baldursgate3.game",
    "larian.com",
    "capcom.com",
    "bandainamcoent.com",
    "square-enix-games.com",
    "square-enix.com",
    "sega.com",
    "2k.com",
    "activision.com",
    "bungie.net",
}
_SPECULATION = re.compile(
    r"\b(?:rumou?rs?|rumou?red|leaks?|leaked|allegedly|reportedly|"
    r"unconfirmed|speculat\w*|predicted|prediction|unannounced|"
    r"expected to (?:launch|release|feature)|could (?:launch|feature)|"
    r"estimated (?:specs|specifications|requirements))\b",
    re.I,
)


def speculative(text: str) -> bool:
    return bool(_SPECULATION.search(text))


def official_source(url: str, category: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = unquote(parsed.path).lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    if speculative(path) or any(
        p in host.split(".") for p in ("forums", "forum", "community")
    ):
        return False
    if any(p in path.split("/") for p in ("forums", "forum", "community")):
        return False
    if category == "game":
        if host == "store.steampowered.com":
            return bool(re.match(r"/app/\d+(?:/|$)", path))
        if host == "store.epicgames.com":
            return bool(re.match(r"/(?:[a-z-]+/)?p/[^/]+", path))
        if host in ("gog.com", "www.gog.com"):
            return bool(re.match(r"/(?:[a-z-]+/)?game/[^/]+", path))
        domains = _GAME_DOMAINS
    elif category in ("cpu", "gpu_chipset"):
        domains = _SILICON_DOMAINS
    else:
        domains = _HARDWARE_DOMAINS
    return any(host == d or host.endswith("." + d) for d in domains)


def _text(value: str) -> str:
    return " ".join(value.casefold().split())


def grounded_quote(snippet: str | None, document: str | None) -> bool:
    if not snippet or not document or speculative(snippet):
        return False
    quote, source = _text(snippet), _text(document)
    offset = source.find(quote)
    if offset < 0:
        return False
    # Prevent cherry-picking "RTX ... has ..." from "Rumor: RTX ... has ...".
    context = source[max(0, offset - 100) : offset + len(quote) + 100]
    return not speculative(context)


def confirmation_error(category: str, fields: dict, provenance: dict) -> str | None:
    if category == "ai_model":  # structured Hugging Face path
        return None
    proof = provenance.get("confirmation_status") or {}
    if proof.get("verified") is not True:
        return "Source evidence has not passed verification"
    if fields.get("confirmation_status") not in ("released", "officially_announced"):
        return "No official release or announcement evidence"
    if not official_source(proof.get("source_url", ""), category):
        return "Confirmation must come from an approved official source"
    if not proof.get("snippet") or speculative(proof["snippet"]):
        return "Confirmation is missing or speculative"
    return None
