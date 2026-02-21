import uuid
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func

from app.db.base import Base

class BenchmarkType(Base):
    __tablename__ = "benchmark_types"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)

    applicable_part_types = Column(ARRAY(String), nullable=False)

    # True for most, false for latency-like benchmarks
    higher_is_better = Column(Boolean, nullable=False, default=True, server_default="true")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

class CPUBenchmarkScores(BaseModel):

    # Single-thread
    cinebench_r24_single: Optional[float] = Field(
        None, description="Cinebench R24 single-core score",
    )
    geekbench_6_single: Optional[float] = Field(
        None, description="Geekbench 6 single-core score",
    )

    # Multi-thread
    cinebench_r24_multi: Optional[float] = Field(
        None, description="Cinebench R24 multi-core score",
    )
    geekbench_6_multi: Optional[float] = Field(
        None, description="Geekbench 6 multi-core score",
    )

    # For integrated graphics
    night_raid: Optional[float] = Field(
        None, description="3DMark Night Raid graphics score (iGPU)",
    )

    class Config:
        extra = "allow"   # Forward compatibility


class GPUBenchmarkScores(BaseModel):

    # Rasterization
    timespy: Optional[float] = Field(
        None, description="3DMark TimeSpy graphics score",
    )

    # Ray tracing
    port_royal: Optional[float] = Field(
        None, description="3DMark Port Royal score",
    )

    # Modern DX12 Ultimate
    speed_way: Optional[float] = Field(
        None, description="3DMark Speed Way score",
    )

    # Compute (AI/ML, creative rendering)
    geekbench_6_compute: Optional[float] = Field(
        None, description="Geekbench 6 GPU compute score (OpenCL/Vulkan)",
    )

    class Config:
        extra = "allow"   # Forward compatibility