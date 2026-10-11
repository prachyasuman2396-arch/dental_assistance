from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models.document import Document
from app.db.models.chunk import DocumentChunk


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: str,
        filename: str,
        file_path: str,
        file_size_bytes: int = 0,
        page_count: int = 0,
        status: str = "pending",
    ) -> Document:
        doc = Document(
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            status=status,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def get_by_id(self, document_id: str, user_id: str) -> Optional[Document]:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Document]:
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(desc(Document.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        document_id: str,
        status: str,
        page_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            return None
        doc.status = status
        if page_count is not None:
            doc.page_count = page_count
        if error_message is not None:
            doc.error_message = error_message
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def delete(self, document_id: str, user_id: str) -> bool:
        doc = await self.get_by_id(document_id, user_id)
        if not doc:
            return False
        await self.session.delete(doc)
        await self.session.commit()
        return True

    async def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.commit()

    async def get_chunks_by_document(self, document_id: str, user_id: str) -> List[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.user_id == user_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
