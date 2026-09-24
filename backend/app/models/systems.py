"""Complete machines sold whole: DGX Spark, Mac Studio, Strix Halo mini PCs.

WHY A SYSTEM IS A PC_PARTS ROW. Everything retail already hangs off pc_parts:
Amazon listings attach by part_id, the pricing ETL walks pc_parts by
part_type, commerce resolves listings for a part id, and the frontend fetches
listings per part. Making a system its own polymorphic subtype buys all of that
unchanged, where a free-standing table would need a parallel copy of each.
Nothing in the component pipeline selects pc_parts without a part_type filter,
so a system row cannot leak into a CPU or GPU candidate set.

WHY THERE IS A FAMILY. The same shape as gpu_chipsets: every GB10 box (NVIDIA's
Founders Edition, ASUS, Dell, HP, Lenovo, MSI) is one machine as far as a model
running on it can tell, and one eBay search for "DGX Spark" is right for all of
them. The family carries what is shared (backend, OS, listings for the group,
the pitch copy); the variant carries what differs (memory, storage, price).
Price lives only on the variant, unlike gpu_chipsets: here memory and storage
change it by thousands, so there is no one family price to quote.

WHAT A FAMILY IS GOOD FOR IS DATA, NOT CODE. `suited_for` says which workloads
a family may be offered for, and the fit rules read it rather than knowing that
"Macs are for video" or "training needs CUDA". Those are true today and will not
stay true: a ROCm release, a new chip or a price cut changes them, and an admin
edit should be enough to follow. The same goes for the OS: offers match the
user's stated OS against `os`, not against a list of brands.

Memory is the load-bearing spec. `gpu_addressable_memory_gb` is recorded
separately from `unified_memory_gb` because the two differ on most of these
platforms (OS reservations, driver limits), and the fit check compares a
model's memory floor against the addressable figure, never the headline one.
Where each number came from is recorded in app/seeds/seed_systems.py.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.pcparts import PCPart


class SystemWorkload(str, enum.Enum):
    """Values of SystemFamily.suited_for: the offers a family may appear in."""

    LLM_INFERENCE = "llm_inference"
    LLM_TRAINING = "llm_training"
    VIDEO_EDITING = "video_editing"
    MUSIC_PRODUCTION = "music_production"
    GAMING = "gaming"


class SystemFamily(Base):
    __tablename__ = "system_families"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)  # e.g. "DGX Spark (GB10)"
    # A label for grouping in admin, e.g. "nvidia_gb10". Deliberately not an
    # enum and never branched on: a new platform must not need a code change.
    platform = Column(String(30), nullable=False)
    # Matched against ai_workloads.gpu_backends, the same vocabulary, so a
    # workload the catalog publishes for some backends only rules the others out.
    gpu_backend = Column(String(20), nullable=False)  # "cuda" | "metal" | "rocm"
    # Free text, matched against the OS a user names ("windows", "linux",
    # "macos" and their synonyms; see fit._OS_WORDS).
    os = Column(String(50), nullable=False)  # e.g. "DGX OS (Ubuntu)", "macOS"
    # SystemWorkload values. A family is only ever offered for these.
    suited_for = Column(ARRAY(String), nullable=False, server_default="{}")

    # Customer-facing copy for the offer card. Curated, not generated: these
    # are claims about a product, and a model paraphrasing them is how a
    # comparison ends up promising something the box cannot do.
    summary = Column(Text, nullable=True)
    strengths = Column(ARRAY(String), nullable=True)
    limitations = Column(ARRAY(String), nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    variants = relationship("System", back_populates="family")


class System(PCPart):
    __tablename__ = "systems"

    id = Column(
        UUID(as_uuid=True),
        ForeignKey("pc_parts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    system_family_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_families.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    chip = Column(String(100), nullable=False)  # e.g. "M5 Ultra 32C/80G"
    cpu_cores = Column(Integer, nullable=True)
    gpu_cores = Column(Integer, nullable=True)
    unified_memory_gb = Column(Integer, nullable=False)
    gpu_addressable_memory_gb = Column(Integer, nullable=False)
    # Per variant, not per family: binned tiers of one chip can differ here,
    # and bandwidth, not capacity, sets tokens per second once a model fits.
    memory_bandwidth_gbps = Column(Integer, nullable=False)
    storage_gb = Column(Integer, nullable=True)
    tdp_watts = Column(Integer, nullable=True)

    family = relationship("SystemFamily", back_populates="variants")

    @property
    def specs(self) -> dict:
        return {
            "chip": self.chip,
            "unified_memory_gb": self.unified_memory_gb,
            "gpu_memory_gb": self.gpu_addressable_memory_gb,
            "bandwidth_gbps": self.memory_bandwidth_gbps,
            "storage_gb": self.storage_gb,
        }

    __mapper_args__ = {"polymorphic_identity": "system"}
