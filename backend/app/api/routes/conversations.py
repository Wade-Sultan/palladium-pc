from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import verify_firebase_token
from app.core.db import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ConversationSummary

router = APIRouter(tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationSummary])
def get_conversations(
    user: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
) -> list[ConversationSummary]:
    """Return the authenticated user's conversation history, newest first."""
    firebase_uid = user.get("uid")

    db_user = db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    ).scalar_one_or_none()

    if not db_user:
        return []

    rows = db.execute(
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            Conversation.updated_at,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == db_user.id)
        .group_by(Conversation.id)
        .order_by(Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return [
        ConversationSummary(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            message_count=row.message_count,
        )
        for row in rows
    ]
