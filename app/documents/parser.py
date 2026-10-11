import hashlib
from typing import List, Dict, Any, Tuple
import pymupdf
from pydantic import BaseModel
from app.core.logging import logger


class ExtractedPage(BaseModel):
    page_number: int  # 1-indexed
    text: str
    char_count: int


class ParsedPDFDocument(BaseModel):
    filename: str
    total_pages: int
    total_chars: int
    is_empty_or_scanned: bool
    pages: List[ExtractedPage]
    metadata: Dict[str, Any]


class PDFParser:
    """PDF parser using PyMuPDF preserving page numbers and metadata."""

    @staticmethod
    def parse_file(file_path: str, filename: str) -> ParsedPDFDocument:
        doc = pymupdf.open(file_path)
        total_pages = doc.page_count
        pages: List[ExtractedPage] = []
        total_chars = 0

        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "keywords": doc.metadata.get("keywords", ""),
            "producer": doc.metadata.get("producer", ""),
        }

        for page_idx in range(total_pages):
            page = doc.load_page(page_idx)
            text = page.get_text("text").strip()
            char_count = len(text)
            total_chars += char_count

            pages.append(
                ExtractedPage(
                    page_number=page_idx + 1,  # 1-indexed for student citations
                    text=text,
                    char_count=char_count,
                )
            )

        doc.close()

        # Scanned or image-only PDF detection: average < 30 chars per page
        is_empty_or_scanned = total_chars < 50 or (total_pages > 0 and (total_chars / total_pages) < 25)
        if is_empty_or_scanned:
            logger.warning(
                f"PDF '{filename}' appears empty or scanned without selectable text (total_chars={total_chars})."
            )

        return ParsedPDFDocument(
            filename=filename,
            total_pages=total_pages,
            total_chars=total_chars,
            is_empty_or_scanned=is_empty_or_scanned,
            pages=pages,
            metadata=metadata,
        )

    @staticmethod
    def compute_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
