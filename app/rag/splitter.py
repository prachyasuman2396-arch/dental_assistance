import re
import uuid
import hashlib
from typing import List, Optional, Tuple
from pydantic import BaseModel
from app.core.config import settings


class HierarchicalChunk(BaseModel):
    chunk_id: str
    parent_chunk_id: Optional[str] = None
    content: str
    page_start: int
    page_end: int
    section_title: Optional[str] = None
    is_parent: bool = False
    content_hash: str


class RecursiveTextSplitter:
    """
    Robust recursive text splitter supporting hierarchical separators:
    double newline, single newline, sentences, spaces, characters.
    """
    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
        separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "; ", ", ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        chunks: List[str] = []
        self._split_recursive(text, self.separators, chunks)
        return self._merge_splits(chunks)

    def _split_recursive(self, text: str, separators: List[str], final_chunks: List[str]) -> None:
        if len(text) <= self.chunk_size:
            final_chunks.append(text)
            return

        if not separators:
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                final_chunks.append(text[i : i + self.chunk_size])
            return

        separator = separators[0]
        remaining_separators = separators[1:]

        splits = list(text) if separator == "" else text.split(separator)

        current_doc = []
        total_len = 0

        for s in splits:
            item = s if separator == "" else s + separator
            if total_len + len(item) > self.chunk_size and current_doc:
                combined = "".join(current_doc).strip()
                if combined:
                    if len(combined) > self.chunk_size:
                        self._split_recursive(combined, remaining_separators, final_chunks)
                    else:
                        final_chunks.append(combined)
                current_doc = [item]
                total_len = len(item)
            else:
                current_doc.append(item)
                total_len += len(item)

        if current_doc:
            combined = "".join(current_doc).strip()
            if combined:
                if len(combined) > self.chunk_size:
                    self._split_recursive(combined, remaining_separators, final_chunks)
                else:
                    final_chunks.append(combined)

    def _merge_splits(self, splits: List[str]) -> List[str]:
        merged: List[str] = []
        current = ""

        for s in splits:
            s_clean = s.strip()
            if not s_clean:
                continue

            if not current:
                current = s_clean
            elif len(current) + len(s_clean) + 1 <= self.chunk_size:
                current = f"{current} {s_clean}"
            else:
                merged.append(current)
                if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                    overlap_prefix = current[-self.chunk_overlap :].strip()
                    current = f"{overlap_prefix} {s_clean}"
                else:
                    current = s_clean

        if current and (not merged or merged[-1] != current):
            merged.append(current)

        return merged


class StructureAwareSplitter:
    """
    Structure-aware, hierarchical chunker that preserves section headings,
    paragraph cohesion, and generates optional parent-child chunk relationships.
    """
    def __init__(
        self,
        child_chunk_size: int = 500,
        child_overlap: int = 100,
        parent_chunk_size: int = 1500,
        enable_parent_child: bool = True,
    ):
        self.child_splitter = RecursiveTextSplitter(chunk_size=child_chunk_size, chunk_overlap=child_overlap)
        self.parent_splitter = RecursiveTextSplitter(chunk_size=parent_chunk_size, chunk_overlap=200)
        self.enable_parent_child = enable_parent_child

    def split_page(
        self,
        text: str,
        page_number: int,
        section_title: Optional[str] = None,
    ) -> List[HierarchicalChunk]:
        """Split a page into chunks, establishing parent-child links when configured."""
        if not text.strip():
            return []

        chunks: List[HierarchicalChunk] = []

        if not self.enable_parent_child or len(text) <= self.child_splitter.chunk_size:
            # Simple structure-aware chunks
            child_texts = self.child_splitter.split_text(text)
            for c_text in child_texts:
                c_clean = c_text.strip()
                if not c_clean:
                    continue
                c_id = str(uuid.uuid4())
                c_hash = hashlib.sha256(c_clean.encode("utf-8")).hexdigest()
                chunks.append(
                    HierarchicalChunk(
                        chunk_id=c_id,
                        parent_chunk_id=None,
                        content=c_clean,
                        page_start=page_number,
                        page_end=page_number,
                        section_title=section_title,
                        is_parent=False,
                        content_hash=c_hash,
                    )
                )
            return chunks

        # Parent-child chunking
        parent_texts = self.parent_splitter.split_text(text)
        for p_text in parent_texts:
            p_clean = p_text.strip()
            if not p_clean:
                continue

            p_id = str(uuid.uuid4())
            p_hash = hashlib.sha256(p_clean.encode("utf-8")).hexdigest()

            # Create parent chunk
            parent_chunk = HierarchicalChunk(
                chunk_id=p_id,
                parent_chunk_id=None,
                content=p_clean,
                page_start=page_number,
                page_end=page_number,
                section_title=section_title,
                is_parent=True,
                content_hash=p_hash,
            )
            chunks.append(parent_chunk)

            # Generate child chunks within this parent
            child_texts = self.child_splitter.split_text(p_clean)
            for c_text in child_texts:
                c_clean = c_text.strip()
                if not c_clean:
                    continue
                c_id = str(uuid.uuid4())
                c_hash = hashlib.sha256(c_clean.encode("utf-8")).hexdigest()
                chunks.append(
                    HierarchicalChunk(
                        chunk_id=c_id,
                        parent_chunk_id=p_id,  # Link child to parent
                        content=c_clean,
                        page_start=page_number,
                        page_end=page_number,
                        section_title=section_title,
                        is_parent=False,
                        content_hash=c_hash,
                    )
                )

        return chunks
