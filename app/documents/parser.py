import os
import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import pymupdf
from pydantic import BaseModel
from app.core.logging import logger


class ExtractedPage(BaseModel):
    page_number: int  # 1-indexed
    text: str
    char_count: int
    section_title: Optional[str] = None


class ParsedPDFDocument(BaseModel):
    filename: str
    total_pages: int
    total_chars: int
    is_empty_or_scanned: bool
    pages: List[ExtractedPage]
    metadata: Dict[str, Any]
    content_hash: str


class PDFParser:
    """Production-grade PDF parser using PyMuPDF preserving structure, page citations, and headings."""

    @staticmethod
    def validate_pdf_magic(file_path: str) -> bool:
        """Validate true PDF magic bytes '%PDF-' rather than relying on extension."""
        if not os.path.exists(file_path):
            return False
        try:
            with open(file_path, "rb") as f:
                header = f.read(5)
                return header.startswith(b"%PDF-")
        except Exception:
            return False

    @staticmethod
    def compute_file_sha256(file_path: str) -> str:
        """Compute SHA-256 hash of entire file for duplicate upload detection."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def compute_sha256(content: str) -> str:
        """Compute SHA-256 hash of a string chunk."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """
        Normalize extraction artifacts while preserving scientific terminology,
        equations, table structures, and paragraph boundaries.
        """
        if not raw_text:
            return ""

        # Normalize unicode non-breaking spaces
        text = raw_text.replace("\u00a0", " ").replace("\u200b", "")

        # Remove repetitive solitary page numbers on a line (e.g., "\n42\n")
        text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)

        # Normalize excessive blank lines (more than 2 consecutive newlines to 2)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Normalize multiple horizontal spaces to single space, except newlines
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    @staticmethod
    def detect_heading(page_text: str) -> Optional[str]:
        """Heuristic detection of chapter/section heading on a page."""
        lines = page_text.split("\n")
        for line in lines[:5]:
            trimmed = line.strip()
            # Explicit section/chapter prefix
            if re.match(r"^(chapter|section|module|unit|part)\s+\d+[:\.\s]?", trimmed, re.IGNORECASE):
                return trimmed[:100]
            # Markdown header format
            if trimmed.startswith("# ") or trimmed.startswith("## "):
                return trimmed.lstrip("#").strip()[:100]
            # Numbered title e.g. "3.2 Newton's Laws"
            if re.match(r"^\d+(\.\d+)+\s+[A-Z]", trimmed):
                return trimmed[:100]
        return None

    @classmethod
    def parse_file(cls, file_path: str, filename: str) -> ParsedPDFDocument:
        doc = pymupdf.open(file_path)
        total_pages = doc.page_count
        pages: List[ExtractedPage] = []
        total_chars = 0

        # Extract document table of contents if available
        toc = []
        try:
            toc = doc.get_toc()  # [[lvl, title, page], ...]
        except Exception:
            pass

        # Build page -> section mapping from TOC
        page_to_section: Dict[int, str] = {}
        if toc:
            for item in toc:
                if len(item) >= 3 and isinstance(item[2], int):
                    toc_page = item[2]
                    toc_title = str(item[1]).strip()
                    if toc_page not in page_to_section:
                        page_to_section[toc_page] = toc_title

        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "keywords": doc.metadata.get("keywords", ""),
            "producer": doc.metadata.get("producer", ""),
        }

        current_active_section = metadata.get("title") or "General"

        for page_idx in range(total_pages):
            page_num = page_idx + 1  # 1-indexed for student citations
            page = doc.load_page(page_idx)
            raw_text = page.get_text("text").strip()
            clean_text = cls.clean_text(raw_text)

            # Update section title if found in TOC or header
            if page_num in page_to_section:
                current_active_section = page_to_section[page_num]
            else:
                detected_h = cls.detect_heading(clean_text)
                if detected_h:
                    current_active_section = detected_h

            char_count = len(clean_text)
            total_chars += char_count

            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text=clean_text,
                    char_count=char_count,
                    section_title=current_active_section,
                )
            )

        doc.close()

        # Scanned or image-only PDF detection: average < 30 chars per page
        is_empty_or_scanned = total_chars < 50 or (total_pages > 0 and (total_chars / total_pages) < 25)
        if is_empty_or_scanned:
            logger.warning(
                f"PDF '{filename}' appears empty or scanned without selectable text (total_chars={total_chars})."
            )

        content_hash = cls.compute_file_sha256(file_path)

        return ParsedPDFDocument(
            filename=filename,
            total_pages=total_pages,
            total_chars=total_chars,
            is_empty_or_scanned=is_empty_or_scanned,
            pages=pages,
            metadata=metadata,
            content_hash=content_hash,
        )
