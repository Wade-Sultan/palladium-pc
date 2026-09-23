"""Map OpenDB records to the existing discovery approval contract.

Unknown is never false or zero. Unsupported values and missing required specs
stay visible as validation failures. No prices, benchmarks or image rights are
inferred from the source. This module needs neither credentials nor a database.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from typing import Any

from app.services.discovery.validate import validate_item

REPOSITORY = "https://github.com/buildcores/buildcores-open-db"
LICENSE = "https://opendatacommons.org/licenses/by/1-0/"
VERSION = "buildcores-v1"
CATEGORIES = {
    "CPU": "cpu",
    "GPU": "gpu_variant",
    "Motherboard": "motherboard",
    "RAM": "ram_kit",
    "Storage": "storage_drive",
    "PSU": "psu",
    "PCCase": "case",
    "CPUCooler": "cpu_cooler",
    "CaseFan": "fan",
}
FORM_FACTORS = {
    "ATX": "atx",
    "Micro ATX": "matx",
    "Mini-ITX": "itx",
    "EATX": "eatx",
    "SSI EEB": "ssi_eeb",
    "SSI CEB": "ssi_ceb",
}
CASE_SIZES = {
    "ATX Full Tower": "full_tower",
    "EATX Full Tower": "full_tower",
    "ATX Mid Tower": "mid_tower",
    "EATX Mid Tower": "mid_tower",
    "Micro ATX Mid Tower": "mid_tower",
    "ATX Mini Tower": "mini_tower",
    "Micro ATX Mini Tower": "mini_tower",
    "Mini ITX Tower": "sff",
    "Mini ITX Desktop": "sff",
    "Micro ATX Slim Tower": "sff",
}


def get(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def lower(value: str) -> str:
    return value.strip().lower()


def feature_present(value: str) -> bool:
    token = lower(value)
    if token in {"unknown", "unspecified", "n/a", "null"}:
        raise ValueError("Unknown feature availability")
    return token not in {"none", "no"}


def socket(value: str) -> str:
    return re.sub(r"^LGA\s+", "LGA", value.strip())


def present(value: Any) -> bool:
    return value is not None and value != "" and value != []


@dataclass
class ConvertedItem:
    id: str
    category: str
    extracted_fields: dict[str, Any]
    field_provenance: dict[str, Any]
    source_urls: list[str]
    validation_status: str
    validation_errors: list[dict[str, Any]] | None
    # Values that pass validation but look like source placeholders. They never
    # block manual approval; they only stop auto-approval (see auto_review.py).
    review_holds: list[str] = dataclass_field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Mapper:
    def __init__(self, record: dict[str, Any], directory: str, revision: str) -> None:
        self.record = record
        self.directory = directory
        self.category = CATEGORIES[directory]
        self.source_id = str(uuid.UUID(record["opendb_id"]))
        self.url = (
            f"{REPOSITORY}/blob/{revision}/open-db/{directory}/{self.source_id}.json"
        )
        self.fields: dict[str, Any] = {}
        self.provenance: dict[str, Any] = {}
        self.errors: list[dict[str, Any]] = []
        self.holds: list[str] = []
        self.source: dict[str, Any] = {
            "opendb_id": self.source_id,
            "revision": revision,
            "sha256": hashlib.sha256(
                json.dumps(record, sort_keys=True).encode()
            ).hexdigest(),
            "repository": REPOSITORY,
            "license": LICENSE,
            "converter": VERSION,
            "attribution": "Contains information from BuildCores OpenDB, available under ODC-By v1.0.",
        }

    def error(self, field: str, detail: str) -> None:
        self.errors.append({"field": field, "rule": "mapping", "detail": detail})

    def put(self, field: str, value: Any, path: str) -> None:
        if present(value):
            self.fields[field] = value
            self.provenance[field] = {
                "source_url": self.url,
                "snippet": f"{path}: {json.dumps(get(self.record, path))}",
            }

    def copy(
        self, field: str, path: str, transform: Callable[[Any], Any] | None = None
    ) -> None:
        value = get(self.record, path)
        if not present(value):
            return
        try:
            self.put(field, transform(value) if transform else value, path)
        except (TypeError, ValueError, AttributeError, KeyError):
            self.error(field, f"Unsupported {path}: {value!r}")

    def number(self, field: str, path: str, *, rounding: str | None = None) -> None:
        value = get(self.record, path)
        if value is None:
            return
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            self.error(field, f"Expected finite number at {path}")
        elif rounding == "up":
            self.put(field, math.ceil(value), path)
        elif rounding == "down":
            self.put(field, math.floor(value), path)
        elif float(value).is_integer():
            self.put(field, int(value), path)
        else:
            self.error(field, f"Fractional {path} cannot fit integer column: {value}")

    def boolean(self, field: str, path: str) -> None:
        value = get(self.record, path)
        if value is not None:
            if isinstance(value, bool):
                self.put(field, value, path)
            else:
                self.error(field, f"Expected boolean at {path}")

    def finish(self) -> ConvertedItem:
        # Discovery validation checks domain ranges; enforce the scalar shapes
        # and lengths of fields that otherwise bypass those range checks.
        for field, maximum in {
            "name": 255,
            "manufacturer": 255,
            "model_number": 255,
            "socket": 30,
            "chipset": 30,
            "series": 100,
            "color": 50,
            "pcie_power_pins": 50,
        }.items():
            value = self.fields.get(field)
            if value is not None and (
                not isinstance(value, str) or len(value) > maximum
            ):
                self.error(field, f"Expected string of at most {maximum} characters")
                del self.fields[field]
        status, errors = validate_item(self.category, self.fields)
        errors = (errors or []) + self.errors
        self.provenance["_buildcores"] = self.source
        return ConvertedItem(
            id=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL, f"{REPOSITORY}/{self.category}/{self.source_id}"
                )
            ),
            category=self.category,
            extracted_fields=self.fields,
            field_provenance=self.provenance,
            source_urls=[self.url],
            validation_status="failed" if errors else status,
            validation_errors=errors or None,
            review_holds=self.holds,
        )


def convert(record: dict[str, Any], directory: str, revision: str) -> ConvertedItem:
    m = Mapper(record, directory, revision)
    for field, path in {
        "name": "metadata.name",
        "manufacturer": "metadata.manufacturer",
    }.items():
        m.copy(field, path)
    m.number("year_released", "metadata.releaseYear")
    m.copy(
        "model_number",
        "metadata.part_numbers",
        lambda v: v[0] if isinstance(v, list) else None,
    )
    # Empty lighting arrays mean unspecified, not definitively unlit.
    if directory in {"RAM", "CPUCooler", "CaseFan"}:
        m.copy("has_rgb", "lighting", lambda v: bool(set(v) & {"RGB", "ARGB"}))

    if directory == "CPU":
        m.copy("brand", "metadata.manufacturer", lower)
        m.copy("socket", "socket", socket)
        for field, path in {
            "tdp_watts": "specifications.tdp",
            "cores": "cores.total",
            "threads": "cores.threads",
            "l3_cache_mb": "cache.l3",
            "max_memory_gb": "specifications.memory.maxSupport",
            "memory_channels": "specifications.memory.channels",
        }.items():
            m.number(field, path)
        m.copy(
            "has_igpu",
            "specifications.integratedGraphics.model",
            feature_present,
        )
        m.copy(
            "ddr_generation",
            "specifications.memory.types",
            lambda v: [lower(x) for x in v],
        )
        m.copy("base_clock_ghz", "clocks.performance.base")
        m.copy("boost_clock_ghz", "clocks.performance.boost")
        m.copy("series", "series")
        m.boolean("supports_ecc", "specifications.eccSupport")
    elif directory == "GPU":
        m.copy("brand", "chipset_manufacturer", lower)
        m.copy("chipset_name", "chipset")
        m.number("length_mm", "length", rounding="up")
        m.copy("width_slots", "total_slot_width")
        # OpenDB writes 0 where a value was never filled in. Two thirds of GPU
        # records carry memory_bus 0, and those records are the sparse ones.
        bus = record.get("memory_bus")
        if type(bus) is not int or bus <= 0:
            m.holds.append("GPU memory bus width is 0 or missing")
        connectors = get(record, "power_connectors")
        tdp = record.get("tdp")
        if isinstance(connectors, dict) and connectors:
            labels = {
                "pcie_6_pin": "6-pin",
                "pcie_8_pin": "8-pin",
                "pcie_12VHPWR": "12VHPWR",
                "pcie_12V_2x6": "12V-2x6",
            }
            # All zeros is the same placeholder. It only means "no connector"
            # when the board fits in the 75W a PCIe slot supplies.
            unfilled = not any(connectors.values()) and not (
                isinstance(tdp, int | float) and 0 < tdp <= 75
            )
            if unfilled:
                m.holds.append("GPU power connectors are all 0 above 75W")
            elif set(connectors) - set(labels):
                m.error(
                    "pcie_power_pins",
                    f"Unknown power connector keys: {sorted(set(connectors) - set(labels))}",
                )
            elif all(type(v) is int and v >= 0 for v in connectors.values()):
                m.put(
                    "pcie_power_pins",
                    ", ".join(f"{v}x {labels[k]}" for k, v in connectors.items() if v)
                    or "None",
                    "power_connectors",
                )
        # Chipset-level specs remain evidence for the reviewer. Board TDP and
        # factory clocks cannot safely become shared chipset specifications.
        m.source["chipset_evidence"] = {
            k: record.get(k)
            for k in (
                "chipset",
                "memory",
                "memory_type",
                "memory_bus",
                "tdp",
                "core_base_clock",
                "core_boost_clock",
            )
        }
    elif directory == "Motherboard":
        m.copy("socket", "socket", socket)
        m.copy("form_factor", "form_factor", FORM_FACTORS.__getitem__)
        m.copy("ddr_generation", "memory.ram_type", lower)
        m.number("memory_slots", "memory.slots")
        m.number("max_memory_gb", "memory.max")
        m.copy("chipset", "chipset")
        m.copy(
            "has_wifi",
            "wireless_networking",
            feature_present,
        )
        m.boolean("supports_ecc", "ecc_support")
        m.number("sata_ports", "storage_devices.sata_6_gb_s")
        slots = record.get("m2_slots")
        if isinstance(slots, list) and slots:
            # E-key WiFi slots are not drive sockets. Incomplete slot entries
            # cannot establish the number of usable storage sockets.
            if all(
                isinstance(s, dict) and s.get("key") in {"M", "B", "B+M", "E"}
                for s in slots
            ):
                m.put("m2_slots", sum(s["key"] != "E" for s in slots), "m2_slots")
    elif directory == "RAM":
        m.copy("ddr_generation", "ram_type", lower)
        for field, path in {
            "speed_mhz": "speed",
            "capacity_gb": "capacity",
            "modules": "modules.quantity",
            "module_capacity_gb": "modules.capacity_gb",
            "cas_latency": "cas_latency",
        }.items():
            m.number(field, path)
        m.number("height_mm", "height", rounding="up")
        m.copy("voltage", "voltage")
        m.copy("is_ecc", "ecc", {"ECC": True, "Non-ECC": False}.__getitem__)
        m.copy(
            "module_type",
            "registered",
            {
                "Unbuffered": "udimm",
                "Registered": "rdimm",
                "Load-Reduced": "lrdimm",
            }.__getitem__,
        )
        form = record.get("form_factor")
        if (
            not isinstance(form, str)
            or "DIMM" not in form
            or "SODIMM" in form
            or "SO-DIMM" in form
        ):
            m.error(
                "module_type",
                f"Unsupported or unknown desktop DIMM form factor: {form!r}",
            )
    elif directory == "Storage":
        m.number("capacity_gb", "capacity")
        m.copy("storage_type", "storage_type", lower)
        if record.get("storage_type") == "SSD" and record.get("nvme") is True:
            m.put("storage_type", "nvme", "nvme")
        m.copy(
            "form_factor",
            "form_factor",
            lambda v: {'2.5"': "2.5", '3.5"': "3.5"}.get(
                v, v.lower().replace("m.2-", "m2_")
            ),
        )
        interface = record.get("interface")
        if present(interface):
            match = re.search(r"PCIe ([345])\.0", str(interface), re.I)
            if match:
                m.put("interface", f"pcie_gen{match[1]}", "interface")
            elif interface in {"SATA 6.0 Gb/s", "SATA 6Gb/s", "M.2 SATA", "mSATA"}:
                m.put("interface", "sata3", "interface")
            else:
                m.error(
                    "interface",
                    f"Unsupported or unspecified interface generation: {interface}",
                )
        if record.get("storage_type") == "SSD" and record.get("nvme") is None:
            m.error("storage_type", "SSD protocol is unknown; nvme is not specified")
        # Legacy `type` is not the component category; never infer SSD/HDD
        # from it. Cache size also does not establish whether an SSD has DRAM.
    elif directory == "PSU":
        m.number("wattage", "wattage")
        m.copy("form_factor", "form_factor", lambda v: lower(v).replace("-", "_"))
        m.copy(
            "efficiency_rating",
            "efficiency_rating",
            lambda v: {
                "80+": "80plus",
                "80+ Bronze": "80plus_bronze",
                "80+ Silver": "80plus_silver",
                "80+ Gold": "80plus_gold",
                "80+ Platinum": "80plus_platinum",
                "80+ Titanium": "80plus_titanium",
            }[v],
        )
        m.copy(
            "modular",
            "modular",
            {"Full": "full", "Semi-Modular": "semi", "Non-Modular": "non"}.__getitem__,
        )
        m.number("depth_mm", "length", rounding="up")
        m.boolean("is_fanless", "fanless")
        for field, path in {
            "eps_connectors": "connectors.eps_8_pin",
            "pcie_8pin_connectors": "connectors.pcie_6_plus_2_pin",
            "pcie_16pin_connectors": "connectors.pcie_12vhpwr",
        }.items():
            m.number(field, path)
    elif directory == "PCCase":
        m.copy("size", "form_factor", CASE_SIZES.__getitem__)
        m.copy(
            "supported_mobo_form_factors",
            "supported_motherboard_form_factors",
            lambda v: [FORM_FACTORS[x] for x in v],
        )
        for field, path in {
            "max_gpu_length_mm": "max_video_card_length",
            "max_cooler_height_mm": "max_cpu_cooler_height",
            "max_psu_length_mm": "max_psu_length",
        }.items():
            m.number(field, path, rounding="down")
        m.number("drive_bays_35", "internal_3_5_bays")
        m.number("drive_bays_25", "internal_2_5_bays")
        m.copy("color", "color", lambda v: " / ".join(lower(x) for x in v))
        m.copy("weight_kg", "weight")
        # Transparent acrylic is not glass.
        m.copy(
            "has_glass_panel",
            "side_panel",
            {
                "Tempered Glass": True,
                "Tinted Tempered Glass": True,
                "Solid": False,
                "Acrylic": False,
                "Tinted Acrylic": False,
                "Mesh": False,
                "Aluminum": False,
                "Steel": False,
            }.__getitem__,
        )
    elif directory == "CPUCooler":
        m.copy("supported_sockets", "cpu_sockets", lambda v: [socket(x) for x in v])
        if record.get("water_cooled") is True:
            m.number("radiator_size_mm", "radiator_size")
            if "radiator_size_mm" in m.fields:
                m.put(
                    "cooler_type",
                    f"aio_{m.fields['radiator_size_mm']}",
                    "radiator_size",
                )
        elif record.get("water_cooled") is False:
            m.put("cooler_type", "air", "water_cooled")
            m.number("height_mm", "height", rounding="up")
        m.number("fan_count", "fan_quantity")
        m.number("fan_size_mm", "fan_size")
        m.copy(
            "noise_dba",
            "max_noise_level"
            if record.get("max_noise_level") is not None
            else "min_noise_level",
        )
    elif directory == "CaseFan":
        m.number("size_mm", "size")
        m.number("pack_count", "quantity")
        m.boolean("is_pwm", "pwm")
        m.copy(
            "airflow_cfm",
            "max_airflow" if record.get("max_airflow") is not None else "min_airflow",
        )
        m.copy(
            "noise_dba",
            "max_noise_level"
            if record.get("max_noise_level") is not None
            else "min_noise_level",
        )
    return m.finish()


def chipset_items(variants: list[ConvertedItem]) -> list[ConvertedItem]:
    """Build review candidates, never assign one board's power to a whole chip.

    VRAM capacity/type distinguish e.g. RTX 3060 8GB and 12GB. Conflicting TDP
    values deliberately leave the required field blank for chipset review.
    Variant chipset_name is updated to match the resulting group candidate.
    """
    groups: dict[str, list[ConvertedItem]] = {}
    for item in variants:
        if item.category != "gpu_variant":
            continue
        evidence = item.field_provenance["_buildcores"]["chipset_evidence"]
        chip, memory, memory_type = (
            evidence.get(k) for k in ("chipset", "memory", "memory_type")
        )
        if (
            not isinstance(chip, str)
            or not isinstance(memory, int | float)
            or isinstance(memory, bool)
            or not memory > 0
        ):
            continue
        name = f"{chip} {memory:g}GB {memory_type or ''}".strip()
        item.extracted_fields["chipset_name"] = name
        groups.setdefault(name, []).append(item)
    result = []
    for name, boards in sorted(groups.items()):
        evidence = boards[0].field_provenance["_buildcores"]["chipset_evidence"]
        fields = {"name": name, "vram_gb": evidence["memory"]}
        if evidence.get("memory_type"):
            fields["vram_type"] = lower(evidence["memory_type"])
        powers = {
            b.field_provenance["_buildcores"]["chipset_evidence"].get("tdp")
            for b in boards
        }
        if len(powers) == 1 and None not in powers:
            fields["tdp_watts"] = powers.pop()
        status, errors = validate_item("gpu_chipset", fields)
        if "tdp_watts" not in fields:
            errors = (errors or []) + [
                {
                    "field": "tdp_watts",
                    "rule": "mapping",
                    "detail": "Board TDP values differ or are missing; confirm the shared chipset power specification.",
                }
            ]
        urls = sorted({url for b in boards for url in b.source_urls})
        provenance: dict[str, Any] = {
            key: {
                "source_url": urls[0],
                "snippet": "Grouped by chipset, VRAM capacity and memory type. TDP retained only when all source boards agree.",
            }
            for key in fields
        }
        provenance["_buildcores"] = {
            "repository": REPOSITORY,
            "license": LICENSE,
            "converter": VERSION,
            "revision": boards[0].field_provenance["_buildcores"]["revision"],
            "board_ids": [
                b.field_provenance["_buildcores"]["opendb_id"] for b in boards
            ],
        }
        result.append(
            ConvertedItem(
                str(uuid.uuid5(uuid.NAMESPACE_URL, f"{REPOSITORY}/gpu_chipset/{name}")),
                "gpu_chipset",
                fields,
                provenance,
                urls,
                "failed" if errors else status,
                errors or None,
            )
        )
    return result
