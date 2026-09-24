"""Seed the complete-system catalog: GB10 boxes, Mac Studio, Strix Halo.

Idempotent: families match by name, systems by pc_parts.name; existing rows are
updated in place, so re-running syncs the curated numbers.

Prices are US list prices as checked on 2026-09-23 and go in msrp_cents only.
Street prices are the pricing ETL's job, and these move fast: LPDDR5x supply
pushed the DGX Spark from $3,999 to $4,699 in February 2026 and every Strix
Halo box up by a third. A variant whose price could not be confirmed is seeded
with msrp None, which keeps it in the catalog but out of offers
(app/services/systems/fit.py skips anything it cannot price).

EVERYTHING BELOW IS A SNAPSHOT, checked on 2026-09-23, and the fit rules read
it as data precisely so that it can be corrected without a deploy. Re-check it
before re-running this against a catalog admin has already edited: re-running
overwrites those edits with these values.

suited_for is the curated judgement of what each family may be offered for
(see SystemWorkload). As of the check date: GB10 is the only family with the
full CUDA training stack; Strix Halo is left off training because ROCm
fine-tuning support was still patchy; only the Macs carry the creative
workloads, for their media engines and Final Cut / Logic. Revisit all three as
the software moves.

gpu_addressable_memory_gb is the figure a model actually gets, not the
headline pool, as of the check date:
  - macOS wires at most ~75% of unified memory to the GPU by default (~67% at
    36GB and below). It can be raised by hand; offers do not assume that.
  - Strix Halo: 96GB is the largest BIOS carve-out every vendor exposes on
    both Windows and Linux. Linux can map more through GTT; again, not assumed.
  - GB10 shares the full pool; ~8GB is held back for the OS.

Run: uv run python -m app.seeds.seed_systems
"""

from app.core.db import SessionLocal
from app.models.systems import System, SystemFamily

_FAMILIES: list[dict] = [
    {
        "family": {
            "name": "DGX Spark (GB10)",
            "platform": "nvidia_gb10",
            "gpu_backend": "cuda",
            "os": "DGX OS (Ubuntu)",
            "suited_for": ["llm_inference", "llm_training"],
            "summary": (
                "NVIDIA's Grace Blackwell desktop: 128GB of memory shared by CPU "
                "and GPU, with the full CUDA stack preinstalled."
            ),
            "strengths": [
                "128GB usable by the GPU, enough for 70B models at 8-bit or 120B+ at 4-bit",
                "Full CUDA: PyTorch, vLLM, TensorRT-LLM and fine-tuning all work as on a datacenter GPU",
                "Two units link over the built-in 200Gb ConnectX-7 port",
                "Silent and palm-sized, around 240W at the wall",
            ],
            "limitations": [
                "273 GB/s memory bandwidth: large models fit but generate tokens slowly",
                "Arm Linux only. Not a gaming or Windows machine",
                "No internal upgrades",
            ],
        },
        "systems": [
            {
                "name": "NVIDIA DGX Spark Founders Edition 128GB 4TB",
                "manufacturer": "NVIDIA",
                "msrp_cents": 469_900,
                "chip": "GB10 Grace Blackwell",
                "cpu_cores": 20,
                "unified_memory_gb": 128,
                "gpu_addressable_memory_gb": 120,
                "memory_bandwidth_gbps": 273,
                "storage_gb": 4000,
                "tdp_watts": 240,
            },
            {
                "name": "ASUS Ascent GX10 128GB 1TB",
                "manufacturer": "ASUS",
                "model_number": "GX10-GG0010BN",
                "msrp_cents": 399_999,
                "chip": "GB10 Grace Blackwell",
                "cpu_cores": 20,
                "unified_memory_gb": 128,
                "gpu_addressable_memory_gb": 120,
                "memory_bandwidth_gbps": 273,
                "storage_gb": 1000,
                "tdp_watts": 240,
            },
            {
                "name": "Dell Pro Max with GB10 128GB 2TB",
                "manufacturer": "Dell",
                "msrp_cents": 568_818,
                "chip": "GB10 Grace Blackwell",
                "cpu_cores": 20,
                "unified_memory_gb": 128,
                "gpu_addressable_memory_gb": 120,
                "memory_bandwidth_gbps": 273,
                "storage_gb": 2000,
                "tdp_watts": 240,
            },
        ],
    },
    {
        "family": {
            "name": "Mac Studio (M5 Max)",
            "platform": "apple_silicon",
            "gpu_backend": "metal",
            "os": "macOS",
            "suited_for": ["llm_inference", "video_editing", "music_production"],
            "summary": (
                "Apple's compact workstation. Unified memory with high bandwidth, "
                "near-silent, and the native home of Final Cut Pro and Logic Pro."
            ),
            "strengths": [
                "Up to 614 GB/s memory bandwidth: fast token generation once a model fits",
                "Hardware ProRes and H.264/HEVC encode and decode engines for video work",
                "Near-silent under sustained load, tiny footprint",
                "Runs local models well through MLX, llama.cpp, LM Studio and Ollama",
            ],
            "limitations": [
                "No CUDA: many training and research tools assume NVIDIA",
                "Memory and storage are fixed at purchase",
                "Weak for PC gaming",
            ],
        },
        "systems": [
            {
                "name": "Apple Mac Studio M5 Max 32-core GPU 36GB 512GB",
                "manufacturer": "Apple",
                "msrp_cents": 249_900,
                "chip": "M5 Max 18C/32G",
                "cpu_cores": 18,
                "gpu_cores": 32,
                "unified_memory_gb": 36,
                "gpu_addressable_memory_gb": 24,
                # The binned 32-core tier has a narrower memory bus; Apple
                # quotes 614 GB/s for the 40-core part only. Estimated.
                "memory_bandwidth_gbps": 460,
                "storage_gb": 512,
            },
            {
                "name": "Apple Mac Studio M5 Max 40-core GPU 48GB 1TB",
                "manufacturer": "Apple",
                "msrp_cents": 309_900,
                "chip": "M5 Max 18C/40G",
                "cpu_cores": 18,
                "gpu_cores": 40,
                "unified_memory_gb": 48,
                "gpu_addressable_memory_gb": 36,
                "memory_bandwidth_gbps": 614,
                "storage_gb": 1000,
            },
            {
                "name": "Apple Mac Studio M5 Max 40-core GPU 64GB 1TB",
                "manufacturer": "Apple",
                "msrp_cents": 349_900,
                "chip": "M5 Max 18C/40G",
                "cpu_cores": 18,
                "gpu_cores": 40,
                "unified_memory_gb": 64,
                "gpu_addressable_memory_gb": 48,
                "memory_bandwidth_gbps": 614,
                "storage_gb": 1000,
            },
            {
                "name": "Apple Mac Studio M5 Max 40-core GPU 128GB 1TB",
                "manufacturer": "Apple",
                "msrp_cents": 509_900,
                "chip": "M5 Max 18C/40G",
                "cpu_cores": 18,
                "gpu_cores": 40,
                "unified_memory_gb": 128,
                "gpu_addressable_memory_gb": 96,
                "memory_bandwidth_gbps": 614,
                "storage_gb": 1000,
            },
        ],
    },
    {
        "family": {
            "name": "Mac Studio (M5 Ultra)",
            "platform": "apple_silicon",
            "gpu_backend": "metal",
            "os": "macOS",
            "suited_for": ["llm_inference", "video_editing", "music_production"],
            "summary": (
                "Two M5 Max dies fused together: the most memory and bandwidth "
                "you can put on a desk without a server rack."
            ),
            "strengths": [
                "1.2 TB/s memory bandwidth, faster token generation than any other box here",
                "Up to 256GB of unified memory today, 512GB from late October 2026",
                "Handles 8K ProRes multicam timelines",
                "Near-silent under sustained load",
            ],
            "limitations": [
                "No CUDA: many training and research tools assume NVIDIA",
                "Expensive: memory upgrades are priced at Apple rates",
                "Weak for PC gaming",
            ],
        },
        "systems": [
            {
                "name": "Apple Mac Studio M5 Ultra 96GB 1TB",
                "manufacturer": "Apple",
                "msrp_cents": 549_900,
                "chip": "M5 Ultra",
                "unified_memory_gb": 96,
                "gpu_addressable_memory_gb": 72,
                "memory_bandwidth_gbps": 1200,
                "storage_gb": 1000,
            },
            {
                "name": "Apple Mac Studio M5 Ultra 256GB 1TB",
                "manufacturer": "Apple",
                "msrp_cents": 949_900,
                "chip": "M5 Ultra",
                "unified_memory_gb": 256,
                "gpu_addressable_memory_gb": 192,
                "memory_bandwidth_gbps": 1200,
                "storage_gb": 1000,
            },
        ],
    },
    {
        "family": {
            "name": "Ryzen AI Max+ 395 (Strix Halo)",
            "platform": "amd_strix_halo",
            "gpu_backend": "rocm",
            "os": "Windows 11 or Linux",
            "suited_for": ["llm_inference"],
            "summary": (
                "AMD's big APU in a small box: 128GB of shared memory, x86, and "
                "the usual choice of Windows or Linux."
            ),
            "strengths": [
                "Usually the cheapest way to get 96GB+ of GPU-addressable memory",
                "x86 with Windows or Linux, so ordinary PC software and games run",
                "Small, quiet, and far less power than a multi-GPU tower",
            ],
            "limitations": [
                "256 GB/s memory bandwidth: large models fit but generate tokens slowly",
                "ROCm support trails CUDA; some tools need workarounds or Vulkan",
                "Integrated GPU: roughly RTX 4060-class for gaming",
            ],
        },
        "systems": [
            {
                "name": "Framework Desktop Ryzen AI Max+ 395 128GB 1TB",
                "manufacturer": "Framework",
                "msrp_cents": 344_900,
                "chip": "Ryzen AI Max+ 395",
                "cpu_cores": 16,
                "gpu_cores": 40,
                "unified_memory_gb": 128,
                "gpu_addressable_memory_gb": 96,
                "memory_bandwidth_gbps": 256,
                "storage_gb": 1000,
                "tdp_watts": 140,
            },
            {
                # Price not confirmed for 2026; left for the ETL to fill.
                "name": "GMKtec EVO-X2 Ryzen AI Max+ 395 128GB 2TB",
                "manufacturer": "GMKtec",
                "msrp_cents": None,
                "chip": "Ryzen AI Max+ 395",
                "cpu_cores": 16,
                "gpu_cores": 40,
                "unified_memory_gb": 128,
                "gpu_addressable_memory_gb": 96,
                "memory_bandwidth_gbps": 256,
                "storage_gb": 2000,
                "tdp_watts": 140,
            },
        ],
    },
]


def _upsert_family(db, fields: dict) -> SystemFamily:
    family = db.query(SystemFamily).filter_by(name=fields["name"]).first()
    if family is None:
        family = SystemFamily(**fields)
        db.add(family)
    else:
        for key, value in fields.items():
            setattr(family, key, value)
    db.flush()
    return family


def _upsert_system(db, family: SystemFamily, fields: dict) -> None:
    system = db.query(System).filter_by(name=fields["name"]).first()
    if system is None:
        system = System(system_family_id=family.id, **fields)
        system.price_source = "msrp" if fields.get("msrp_cents") else None
        db.add(system)
    else:
        for key, value in fields.items():
            setattr(system, key, value)
        system.system_family_id = family.id


def seed_systems() -> None:
    db = SessionLocal()
    try:
        for entry in _FAMILIES:
            family = _upsert_family(db, entry["family"])
            for fields in entry["systems"]:
                _upsert_system(db, family, fields)
        db.commit()
        print(
            f"Seeded {len(_FAMILIES)} system families "
            f"({sum(len(e['systems']) for e in _FAMILIES)} systems)."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_systems()
