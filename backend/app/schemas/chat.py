import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Any

class ChatMessage(BaseModel):
    role: str # User or Assistant
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    conversation_id: str | None = None

class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int

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