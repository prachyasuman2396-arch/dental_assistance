import re
from typing import List
from app.core.config import settings


class RecursiveTextSplitter:
    """
    Robust recursive text splitter supporting hierarchical separators:
    double newline, single newline, sentences, spaces, characters.
    """
    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
        separators: List[str] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "; ", ", ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []

        chunks: List[str] = []
        self._split_recursive(text, self.separators, chunks)
        
        # Merge small chunks up to chunk_size and handle overlap
        return self._merge_splits(chunks)

    def _split_recursive(self, text: str, separators: List[str], final_chunks: List[str]) -> None:
        if len(text) <= self.chunk_size:
            final_chunks.append(text)
            return

        if not separators:
            # Base case: split by hard character slice
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                final_chunks.append(text[i : i + self.chunk_size])
            return

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)

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
                # Apply overlap by taking trailing chars of current
                if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                    overlap_prefix = current[-self.chunk_overlap :].strip()
                    current = f"{overlap_prefix} {s_clean}"
                else:
                    current = s_clean

        if current and (not merged or merged[-1] != current):
            merged.append(current)

        return merged
