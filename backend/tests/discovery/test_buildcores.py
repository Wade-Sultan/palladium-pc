from __future__ import annotations

import copy
import json
import subprocess
import uuid

import pytest

from app.services.buildcores.auto_review import Catalog, chip_key, decide
from app.services.buildcores.convert import CATEGORIES, chipset_items, convert
from app.services.buildcores.importer import read_snapshot

REVISION = "a" * 40


def record(**fields):
    return {
        "opendb_id": str(uuid.uuid4()),
        "metadata": {
            "name": "Example component",
            "manufacturer": "Intel",
            "part_numbers": ["EX-123"],
        },
        **fields,
    }


def test_cpu_nested_specs_and_unknown_graphics():
    source = record(
        socket="LGA 1700",
        cores={"total": 16, "threads": 24},
        specifications={
            "tdp": 125,
            "memory": {"types": ["DDR4", "DDR5"]},
            "integratedGraphics": {"model": "None"},
        },
    )
    item = convert(source, "CPU", REVISION)
    assert item.validation_status == "passed"
    assert item.extracted_fields["socket"] == "LGA1700"
    assert item.extracted_fields["has_igpu"] is False
    assert item.extracted_fields["ddr_generation"] == ["ddr4", "ddr5"]
    assert "msrp_cents" not in item.extracted_fields
    source["specifications"]["integratedGraphics"] = None
    assert convert(source, "CPU", REVISION).validation_status == "failed"


@pytest.mark.parametrize(
    "category,fields,expected",
    [
        (
            "Motherboard",
            {
                "socket": "AM5",
                "form_factor": "Micro ATX",
                "memory": {"ram_type": "DDR5", "slots": 4},
                "wireless_networking": "None",
            },
            {"form_factor": "matx", "has_wifi": False},
        ),
        (
            "RAM",
            {
                "ram_type": "DDR5",
                "speed": 6000,
                "capacity": 64,
                "modules": {"quantity": 2, "capacity_gb": 32},
                "registered": "Unbuffered",
                "ecc": "Non-ECC",
                "form_factor": "288-pin DIMM",
            },
            {"capacity_gb": 64, "module_capacity_gb": 32, "module_type": "udimm"},
        ),
        (
            "Storage",
            {
                "storage_type": "SSD",
                "capacity": 2000,
                "nvme": True,
                "interface": "M.2 PCIe 4.0 x4",
                "form_factor": "M.2-2280",
            },
            {
                "storage_type": "nvme",
                "interface": "pcie_gen4",
                "form_factor": "m2_2280",
            },
        ),
        (
            "PSU",
            {
                "wattage": 850,
                "form_factor": "SFX-L",
                "efficiency_rating": "80+ Gold",
                "modular": "Non-Modular",
            },
            {
                "form_factor": "sfx_l",
                "efficiency_rating": "80plus_gold",
                "modular": "non",
            },
        ),
        (
            "PCCase",
            {
                "form_factor": "ATX Mid Tower",
                "supported_motherboard_form_factors": ["ATX", "Micro ATX"],
                "max_video_card_length": 350.9,
                "max_cpu_cooler_height": 165.5,
            },
            {"max_gpu_length_mm": 350, "max_cooler_height_mm": 165},
        ),
        (
            "CPUCooler",
            {
                "water_cooled": True,
                "radiator_size": 360,
                "cpu_sockets": ["LGA 1700", "AM5"],
            },
            {"cooler_type": "aio_360", "supported_sockets": ["LGA1700", "AM5"]},
        ),
        (
            "CaseFan",
            {"size": 120, "pwm": False, "min_airflow": 50, "quantity": 3},
            {"size_mm": 120, "is_pwm": False, "airflow_cfm": 50, "pack_count": 3},
        ),
        (
            "GPU",
            {
                "chipset": "GeForce RTX 4070",
                "chipset_manufacturer": "NVIDIA",
                "length": 300.5,
                "total_slot_width": 2.5,
            },
            {"brand": "nvidia", "length_mm": 301, "width_slots": 2.5},
        ),
    ],
)
def test_category_mapping(category, fields, expected):
    item = convert(record(**fields), category, REVISION)
    assert item.validation_status == "passed", item.validation_errors
    assert item.extracted_fields.items() >= expected.items()


def test_unsupported_and_missing_values_remain_reviewable():
    board = convert(
        record(
            socket="AM5", form_factor="ATX", memory={"ram_type": "DDR5", "slots": 4}
        ),
        "Motherboard",
        REVISION,
    )
    assert "has_wifi" not in board.extracted_fields
    assert board.validation_status == "failed"
    cooler = convert(
        record(water_cooled=True, radiator_size=420, cpu_sockets=["AM5"]),
        "CPUCooler",
        REVISION,
    )
    assert cooler.validation_status == "failed"
    storage = convert(
        record(type="SSD", capacity=1000, interface="SAS 12.0 Gb/s"),
        "Storage",
        REVISION,
    )
    assert "storage_type" not in storage.extracted_fields
    assert "interface" not in storage.extracted_fields
    assert storage.validation_status == "failed"


def test_source_id_survives_rename_and_revision_with_pinned_provenance():
    source = record(size=120)
    original = convert(source, "CaseFan", REVISION)
    source["metadata"]["name"] = "Renamed fan"
    changed = convert(source, "CaseFan", "b" * 40)
    assert original.id == changed.id
    assert REVISION in original.source_urls[0]
    assert original.field_provenance["_buildcores"]["license"].endswith("/by/1-0/")
    assert (
        original.field_provenance["_buildcores"]["sha256"]
        != changed.field_provenance["_buildcores"]["sha256"]
    )


def test_gpu_groups_separate_memory_and_do_not_guess_shared_tdp():
    source = record(
        chipset="GeForce RTX 3060",
        chipset_manufacturer="NVIDIA",
        length=242,
        memory=12,
        memory_type="GDDR6",
        tdp=170,
    )
    first = convert(source, "GPU", REVISION)
    second_source = copy.deepcopy(source)
    second_source.update(opendb_id=str(uuid.uuid4()), tdp=180)
    second = convert(second_source, "GPU", REVISION)
    third_source = copy.deepcopy(source)
    third_source.update(opendb_id=str(uuid.uuid4()), memory=8)
    third = convert(third_source, "GPU", REVISION)
    groups = chipset_items([first, second, third])
    assert len(groups) == 2
    conflicted = next(g for g in groups if g.extracted_fields["vram_gb"] == 12)
    assert conflicted.validation_status == "failed"
    assert "tdp_watts" not in conflicted.extracted_fields
    assert (
        first.extracted_fields["chipset_name"]
        == second.extracted_fields["chipset_name"]
    )
    assert (
        first.extracted_fields["chipset_name"] != third.extracted_fields["chipset_name"]
    )


def test_laptop_ram_is_not_a_desktop_kit():
    item = convert(
        record(
            ram_type="DDR5",
            speed=5600,
            capacity=32,
            modules={"quantity": 2, "capacity_gb": 16},
            registered="Unbuffered",
            form_factor="262-pin SO-DIMM",
        ),
        "RAM",
        REVISION,
    )
    assert item.validation_status == "failed"
    assert any(e["field"] == "module_type" for e in item.validation_errors)


@pytest.mark.parametrize("unknown", ["Unknown", "N/A", "Unspecified"])
def test_unknown_wifi_is_not_treated_as_present(unknown):
    item = convert(
        record(
            socket="AM5",
            form_factor="ATX",
            memory={"ram_type": "DDR5", "slots": 4},
            wireless_networking=unknown,
        ),
        "Motherboard",
        REVISION,
    )
    assert "has_wifi" not in item.extracted_fields
    assert item.validation_status == "failed"


def test_snapshot_filters_peripherals_reports_bad_ids_and_rejects_dirty_data(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    fan = record(size=120)
    for category, data in [("CaseFan", fan), ("Mouse", record())]:
        directory = tmp_path / "open-db" / category
        directory.mkdir(parents=True)
        (directory / f"{data['opendb_id']}.json").write_text(json.dumps(data))
    bad = tmp_path / "open-db" / "CaseFan" / "invalid.json"
    bad.write_text("{}")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    _, items, rejected = read_snapshot(tmp_path, ["CaseFan"])
    assert len(items) == 1
    assert len(rejected) == 1
    assert "Mouse" not in CATEGORIES
    bad.write_text("[]")
    with pytest.raises(ValueError, match="local data changes"):
        read_snapshot(tmp_path, ["CaseFan"])


def gpu(**fields):
    return record(
        chipset="GeForce RTX 3080",
        chipset_manufacturer="NVIDIA",
        length=285,
        memory=10,
        memory_type="GDDR6X",
        memory_bus=320,
        tdp=320,
        power_connectors={"pcie_8_pin": 2, "pcie_6_pin": 0},
        **fields,
    )


def test_gpu_placeholder_zeros_hold_auto_review_but_not_validation():
    item = convert(gpu(), "GPU", REVISION)
    assert item.review_holds == []
    assert item.extracted_fields["pcie_power_pins"] == "2x 8-pin"
    incomplete = gpu()
    incomplete.update(memory_bus=0, power_connectors={"pcie_8_pin": 0})
    item = convert(incomplete, "GPU", REVISION)
    assert item.validation_status == "passed"
    assert item.review_holds == [
        "GPU memory bus width is 0 or missing",
        "GPU power connectors are all 0 above 75W",
    ]
    # A zero here is a placeholder, not proof the card needs no cable.
    assert "pcie_power_pins" not in item.extracted_fields
    slot_powered = gpu()
    slot_powered.update(tdp=30, power_connectors={"pcie_8_pin": 0})
    item = convert(slot_powered, "GPU", REVISION)
    assert item.review_holds == []
    assert item.extracted_fields["pcie_power_pins"] == "None"


def catalog(**groups):
    return Catalog(
        groups={
            "ram_kit": [],
            "storage_drive": [],
            "psu": [],
            "gpu_variant": [],
            **groups,
        },
        names={},
        part_types={
            "cpu": "cpu",
            "gpu_variant": "gpu",
            "ram_kit": "ramkit",
            "storage_drive": "storagedrive",
            "psu": "psu",
            "fan": "fan",
        },
    )


RAM = {
    "ram_type": "DDR5",
    "speed": 6000,
    "capacity": 32,
    "modules": {"quantity": 2, "capacity_gb": 16},
    "cas_latency": 36,
    "registered": "Unbuffered",
    "ecc": "Non-ECC",
    "form_factor": "288-pin DIMM",
}
RAM_GROUP = {
    "id": uuid.uuid4(),
    "name": "DDR5-6000 32GB (2x16)",
    "ddr_generation": "ddr5",
    "speed_mhz": 6000,
    "capacity_gb": 32,
    "modules": 2,
    "module_capacity_gb": 16,
    "cas_latency": 36,
    "voltage": 1.35,
    "is_ecc": False,
    "module_type": "udimm",
}


def test_grouped_parts_join_exactly_one_existing_group_or_wait():
    item = convert(record(**RAM), "RAM", REVISION)
    decision = decide(item, False, catalog(ram_kit=[RAM_GROUP]))
    assert decision.approve and decision.group_id == RAM_GROUP["id"]
    # Identity fields must match; CL30 is a different product tier.
    faster = convert(record(**{**RAM, "cas_latency": 30}), "RAM", REVISION)
    assert decide(faster, False, catalog(ram_kit=[RAM_GROUP])).reasons == [
        "no existing RAM group matches"
    ]
    # A known conflict on a non-identity field is also no fit.
    volts = convert(record(**{**RAM, "voltage": 1.25}), "RAM", REVISION)
    assert not decide(volts, False, catalog(ram_kit=[RAM_GROUP])).approve
    twins = catalog(ram_kit=[RAM_GROUP, {**RAM_GROUP, "id": uuid.uuid4()}])
    assert decide(item, False, twins).reasons == [
        "more than one existing RAM group matches"
    ]


def test_gpu_variant_joins_existing_chipset_by_chip_and_vram():
    chipsets = [
        {"id": uuid.uuid4(), "name": n, "vram_gb": v, "vram_type": "GDDR6X"}
        for n, v in [("RTX 3080 10GB", 10), ("RTX 3080 12GB", 12), ("RTX 3080 Ti", 12)]
    ]
    item = convert(gpu(), "GPU", REVISION)
    decision = decide(item, False, catalog(gpu_variant=chipsets))
    assert decision.approve and decision.group_id == chipsets[0]["id"]
    held = gpu()
    held["memory_bus"] = 0
    assert decide(
        convert(held, "GPU", REVISION), False, catalog(gpu_variant=chipsets)
    ).reasons == ["GPU memory bus width is 0 or missing"]
    assert chip_key("Intel Arc A750") == chip_key("Arc A750")


def test_duplicates_failures_and_new_chipsets_are_never_auto_approved():
    fan = convert(record(size=120), "CaseFan", REVISION)
    assert decide(fan, False, catalog()).approve
    assert (
        "possible duplicate of an existing catalog part"
        in decide(fan, True, catalog()).reasons
    )
    named = catalog()
    named.names["fan"] = {"example component"}
    assert decide(fan, False, named).reasons == ["a part with this name already exists"]
    broken = convert(record(), "CaseFan", REVISION)
    assert decide(broken, False, catalog()).reasons == ["failed validation"]
    chip = chipset_items([convert(gpu(), "GPU", REVISION)])[0]
    assert not decide(chip, False, catalog()).approve
