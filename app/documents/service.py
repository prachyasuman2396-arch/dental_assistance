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
from app.rag.splitter import StructureAwareSplitter
from app.rag.embeddings import get_embedding_provider


class DocumentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DocumentRepository(session)
        self.splitter = StructureAwareSplitter(
            child_chunk_size=settings.CHUNK_SIZE,
            child_overlap=settings.CHUNK_OVERLAP,
            parent_chunk_size=1500,
            enable_parent_child=True,
        )
        self.embedding_provider = get_embedding_provider()

    async def ingest_pdf(self, file: UploadFile, user_id: str) -> Document:
        # 1. Extension validation
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

        # 3. Magic bytes validation (prevent disguised executables/scripts)
        if not PDFParser.validate_pdf_magic(dest_path):
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise HTTPException(status_code=400, detail="Invalid PDF file signature or corrupted file.")

        # 4. Check for duplicate upload by content hash
        file_hash = PDFParser.compute_file_sha256(dest_path)
        existing_doc = await self.repo.find_by_content_hash(user_id=user_id, content_hash=file_hash)
        if existing_doc:
            logger.info(f"Duplicate upload detected for user {user_id}: existing doc {existing_doc.id}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return existing_doc

        # 5. Create initial document record with provenance
        doc_record = await self.repo.create(
            user_id=user_id,
            filename=file.filename,
            file_path=dest_path,
            file_size_bytes=file_size,
            status="processing",
            content_hash=file_hash,
            mime_type="application/pdf",
            embedding_model=self.embedding_provider.model_name,
        )

        # 6. Extract with PyMuPDF, preserving structure & sections
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

                hierarchical_chunks = self.splitter.split_page(
                    text=page.text,
                    page_number=page.page_number,
                    section_title=page.section_title,
                )

                for h_chunk in hierarchical_chunks:
                    clean_text = h_chunk.content.strip()
                    if not clean_text:
                        continue

                    chunk_obj = DocumentChunk(
                        id=h_chunk.chunk_id,
                        document_id=doc_record.id,
                        user_id=user_id,
                        chunk_index=chunk_index_counter,
                        page_number=h_chunk.page_start,
                        parent_chunk_id=h_chunk.parent_chunk_id,
                        section_title=h_chunk.section_title,
                        page_start=h_chunk.page_start,
                        page_end=h_chunk.page_end,
                        content=clean_text,
                        content_hash=h_chunk.content_hash,
                        chunk_metadata={
                            "filename": file.filename,
                            "page": h_chunk.page_start,
                            "section": h_chunk.section_title,
                            "is_parent": h_chunk.is_parent,
                            "char_count": len(clean_text),
                        },
                    )
                    chunks_to_insert.append(chunk_obj)
                    # Embed all child and standalone chunks (and optionally parents)
                    chunk_texts_for_embedding.append(clean_text)
                    chunk_index_counter += 1

            # 7. Batch generate embeddings
            if chunk_texts_for_embedding:
                logger.info(
                    f"Generating embeddings for {len(chunk_texts_for_embedding)} chunks from {file.filename}..."
                )
                embeddings = self.embedding_provider.embed_documents(chunk_texts_for_embedding, batch_size=32)
                for chunk_obj, emb in zip(chunks_to_insert, embeddings):
                    chunk_obj.embedding = emb

                # 8. Bulk insert chunks
                await self.repo.add_chunks(chunks_to_insert)

            # 9. Update status to completed
            await self.repo.update_status(
                document_id=doc_record.id,
                status="completed",
                page_count=parsed.total_pages,
                content_hash=file_hash,
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
