from pydantic import BaseModel
from typing import Any

class ChatMessage(BaseModel):
    role: str # User or Assistant
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]