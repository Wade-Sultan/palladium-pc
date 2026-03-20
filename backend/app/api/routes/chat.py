from __future__ import annotations
 
import json
import logging
 
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
 
from app.schemas.chat import ChatMessage, ChatRequest
from app.services.chat_pipeline import run_chat_turn
 
logger = logging.getLogger(__name__)
 
router = APIRouter(tags=["chat"])
 
 
async def _event_stream(messages: list[ChatMessage]):
    """Async generator that yields SSE-formatted lines."""
    try:
        async for event in run_chat_turn(messages):
            line = f"data: {json.dumps(event)}\n\n"
            yield line
    except Exception:
        logger.exception("Chat pipeline error")
        error_event = json.dumps({
            "type": "token",
            "text": "\n\nSomething went wrong generating your recommendation. Please try again.",
        })
        yield f"data: {error_event}\n\n"
 
    yield "data: [DONE]\n\n"
 
 
@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """
    Stream a recommendation response for the given conversation.
 
    The frontend sends the full message history on every turn.
    The pipeline decides whether to elicit more info or recommend a build.
    """
    return StreamingResponse(
        _event_stream(req.messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
        },
    )