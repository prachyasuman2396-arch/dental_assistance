from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.conversation_repo import ConversationRepository
from app.api.dependencies import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = "New Study Session"
    metadata_json: Optional[dict] = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[float] = None
    citations: Optional[dict] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    title: str
    metadata_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    conv = await repo.create(
        user_id=current_user.id,
        title=req.title or "New Study Session",
        metadata_json=req.metadata_json,
    )
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        metadata_json=conv.metadata_json,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    convs = await repo.list_by_user(user_id=current_user.id, limit=limit, offset=offset)
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            metadata_json=c.metadata_json,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    conv = await repo.get_by_id(conversation_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    messages = await repo.get_messages(conversation_id, current_user.id)
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            provider=m.provider,
            model=m.model,
            tokens_used=m.tokens_used,
            latency_ms=m.latency_ms,
            citations=m.citations,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = ConversationRepository(session)
    deleted = await repo.delete(conversation_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")
    return None
