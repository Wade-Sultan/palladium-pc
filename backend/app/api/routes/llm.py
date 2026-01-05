from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.llm.registry import get_engine

router = APIRouter(prefix="/llm", tags=["llm"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = Field(256, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    id: str
    created: int
    model: str
    output_text: str


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    engine = get_engine(req.model)

    output = engine.generate(
        prompt=req.prompt,
        system=req.system,
        max_new_tokens=req.max_tokens,
        temperature=req.temperature,
    )

    return GenerateResponse(
        id=f"gen_{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=req.model or "default",
        output_text=output,
    )
