import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.document_repo import DocumentRepository
from app.documents.service import DocumentService
from app.api.dependencies import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/documents", tags=["Documents & Textbooks"])


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size_bytes: int
    page_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = DocumentService(session)
    doc = await service.ingest_pdf(file=file, user_id=current_user.id)
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status,
        error_message=doc.error_message,
        created_at=doc.created_at,
    )


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = DocumentRepository(session)
    docs = await repo.list_by_user(user_id=current_user.id, limit=limit, offset=offset)
    return [
        DocumentResponse(
            id=d.id,
            filename=d.filename,
            file_size_bytes=d.file_size_bytes,
            page_count=d.page_count,
            status=d.status,
            error_message=d.error_message,
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = DocumentRepository(session)
    doc = await repo.get_by_id(document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")

    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        status=doc.status,
        error_message=doc.error_message,
        created_at=doc.created_at,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = DocumentRepository(session)
    doc = await repo.get_by_id(document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")

    # Remove file from disk if exists
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    await repo.delete(document_id=document_id, user_id=current_user.id)
    return None
