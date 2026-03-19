from pydantic import BaseModel
from typing import Any

class ChatMessage(BaseModel):
    role: str # User or Assistant
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class BuildProfile(BaseModel):
    primary_use: str        # "gaming" | "video_editing" | "local_llm" | "general"
    gaming_resolution: str | None = None  # "1080p" | "1440p" | "4k"
    budget_tier: str        # "entry" | "mid" | "high" | "elite"
    games: list[str] = []
    workloads: list[str] = []
    notes: str = ""

class ChatResponse(BaseModel):
    reply: str
    ready: bool
    build: dict[str, Any] | None = None  # full build object when ready
    build_key: str | None = None