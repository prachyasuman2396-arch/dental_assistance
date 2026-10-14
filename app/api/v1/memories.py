from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.repositories.memory_repo import MemoryRepository

router = APIRouter(prefix="/memories", tags=["Long-Term Memory"])


class MemoryItemResponse(BaseModel):
    id: str
    user_id: str
    memory_type: str
    content: str
    topic: Optional[str] = None
    importance: int
    metadata_json: Dict[str, Any] = {}
    created_at: str
    updated_at: str


class CreateMemoryRequest(BaseModel):
    memory_type: str = "saved_topic"
    topic: Optional[str] = None
    content: str
    importance: int = 1
    metadata_json: Optional[Dict[str, Any]] = None


@router.get("", response_model=List[MemoryItemResponse])
async def list_memories(
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List student's persistent learning memories."""
    repo = MemoryRepository(session)
    items = await repo.get_memories(user_id=current_user.id, memory_type=memory_type, limit=limit)
    now_iso = datetime.now(timezone.utc).isoformat()
    return [
        MemoryItemResponse(
            id=m.id,
            user_id=m.user_id,
            memory_type=m.memory_type,
            content=m.content,
            topic=m.topic,
            importance=m.importance,
            metadata_json=m.metadata_json or {},
            created_at=m.created_at.isoformat() if getattr(m, "created_at", None) else now_iso,
            updated_at=m.updated_at.isoformat() if getattr(m, "updated_at", None) else now_iso,
        )
        for m in items
    ]


@router.post("", response_model=MemoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    req: CreateMemoryRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Add a validated learning memory (e.g. revision topic, study goal, or approved summary)."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Memory content cannot be empty.")

    repo = MemoryRepository(session)
    mem = await repo.add_memory(
        user_id=current_user.id,
        memory_type=req.memory_type,
        content=req.content,
        topic=req.topic,
        importance=req.importance,
        metadata_json=req.metadata_json,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    return MemoryItemResponse(
        id=mem.id,
        user_id=mem.user_id,
        memory_type=mem.memory_type,
        content=mem.content,
        topic=mem.topic,
        importance=mem.importance,
        metadata_json=mem.metadata_json or {},
        created_at=mem.created_at.isoformat() if getattr(mem, "created_at", None) else now_iso,
        updated_at=mem.updated_at.isoformat() if getattr(mem, "updated_at", None) else now_iso,
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete a memory item ensuring user data isolation."""
    repo = MemoryRepository(session)
    deleted = await repo.delete_memory(memory_id=memory_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found or access denied.")
    return {"status": "success", "deleted_id": memory_id, "deleted": True}
