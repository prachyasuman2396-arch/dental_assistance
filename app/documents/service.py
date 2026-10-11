import os
import uuid
import aiofiles
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.models.document import Document
from app.db.models.chunk import DocumentChunk
from app.db.repositories.document_repo import DocumentRepository
from app.documents.parser import PDFParser
from app.rag.splitter import RecursiveTextSplitter
from app.rag.embeddings import get_embedding_provider


class DocumentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DocumentRepository(session)
        self.splitter = RecursiveTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self.embedding_provider = get_embedding_provider()

    async def ingest_pdf(self, file: UploadFile, user_id: str) -> Document:
        # 1. Validation
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")

        os.makedirs(settings.UPLOAD_STORAGE_DIR, exist_ok=True)
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        dest_path = os.path.join(settings.UPLOAD_STORAGE_DIR, unique_filename)

        # 2. Stream to disk and enforce size limit
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        file_size = 0

        async with aiofiles.open(dest_path, "wb") as out_file:
            while chunk := await file.read(1024 * 64):  # 64KB chunks
                file_size += len(chunk)
                if file_size > max_bytes:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                    )
                await out_file.write(chunk)

        # 3. Create initial document record
        doc_record = await self.repo.create(
            user_id=user_id,
            filename=file.filename,
            file_path=dest_path,
            file_size_bytes=file_size,
            status="processing",
        )

        # 4. Extract and chunk
        try:
            parsed = PDFParser.parse_file(dest_path, file.filename)
            if parsed.is_empty_or_scanned:
                logger.warning(f"Uploaded PDF {file.filename} has minimal or no selectable text.")

            chunks_to_insert: List[DocumentChunk] = []
            chunk_texts_for_embedding: List[str] = []
            chunk_index_counter = 0

            for page in parsed.pages:
                if not page.text.strip():
                    continue

                page_chunks = self.splitter.split_text(page.text)
                for chunk_text in page_chunks:
                    clean_text = chunk_text.strip()
                    if not clean_text:
                        continue

                    content_hash = PDFParser.compute_sha256(clean_text)
                    chunk_obj = DocumentChunk(
                        document_id=doc_record.id,
                        user_id=user_id,
                        chunk_index=chunk_index_counter,
                        page_number=page.page_number,
                        content=clean_text,
                        content_hash=content_hash,
                        chunk_metadata={
                            "filename": file.filename,
                            "page": page.page_number,
                            "char_count": len(clean_text),
                        },
                    )
                    chunks_to_insert.append(chunk_obj)
                    chunk_texts_for_embedding.append(clean_text)
                    chunk_index_counter += 1

            # 5. Batch generate embeddings
            if chunk_texts_for_embedding:
                logger.info(
                    f"Generating embeddings for {len(chunk_texts_for_embedding)} chunks from {file.filename}..."
                )
                embeddings = self.embedding_provider.embed_documents(chunk_texts_for_embedding)
                for chunk_obj, emb in zip(chunks_to_insert, embeddings):
                    chunk_obj.embedding = emb

                # 6. Bulk insert chunks
                await self.repo.add_chunks(chunks_to_insert)

            # 7. Update status to completed
            await self.repo.update_status(
                document_id=doc_record.id,
                status="completed",
                page_count=parsed.total_pages,
            )
            logger.info(
                f"Successfully indexed document {doc_record.id} with {len(chunks_to_insert)} chunks."
            )
            return doc_record

        except Exception as e:
            logger.error(f"Failed to process document {doc_record.id}: {e}", exc_info=True)
            await self.repo.update_status(
                document_id=doc_record.id,
                status="failed",
                error_message=str(e),
            )
            raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
