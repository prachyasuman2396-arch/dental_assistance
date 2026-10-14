import re
from typing import List, Optional, Set
from app.rag.vector_store import RetrievedChunk
from app.core.logging import logger


class ContextCompressor:
    """
    Contextual compression & parent expansion.
    Selects the most informative sentences within retrieved chunks,
    eliminates redundant filler, and respects strict token budgets.
    """
    def __init__(self, max_characters_budget: int = 6000):
        self.max_characters_budget = max_characters_budget

    def compress_chunk(self, chunk: RetrievedChunk, query: str) -> str:
        """
        Extractively filter sentences in chunk, keeping those most relevant
        to the student's question while preserving scientific context and negations.
        """
        text = chunk.content.strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) <= 2:
            return text

        query_terms = set(w.lower() for w in re.findall(r"\w+", query) if len(w) > 2)
        if not query_terms:
            return text

        scored_sentences = []
        for idx, sentence in enumerate(sentences):
            s_clean = sentence.strip()
            if not s_clean:
                continue
            s_lower = s_clean.lower()
            match_count = sum(1 for term in query_terms if term in s_lower)

            # Preserve statements with crucial academic qualifiers / negations
            qualifiers = ["however", "therefore", "contraindicated", "not", "except", "defined as", "namely"]
            has_qualifier = any(q in s_lower for q in qualifiers)

            score = match_count + (0.5 if has_qualifier else 0.0)
            scored_sentences.append((score, idx, s_clean))

        # Select only sentences with direct keyword / concept matches
        selected_indices: Set[int] = {idx for score, idx, _ in scored_sentences if score > 0}

        # Fallback: if no individual sentence matched, keep entire text
        if not selected_indices:
            return text

        sorted_indices = sorted(selected_indices)
        compressed_text = " ".join(sentences[i] for i in sorted_indices)
        return compressed_text

    def compress_candidates(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        max_budget: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """Compress a list of retrieved candidate chunks under character/token budget."""
        budget = max_budget or self.max_characters_budget
        compressed_chunks: List[RetrievedChunk] = []
        used_chars = 0

        for chunk in chunks:
            compressed_content = self.compress_chunk(chunk, query)
            chunk_len = len(compressed_content)

            if used_chars + chunk_len > budget and compressed_chunks:
                # If budget exceeded, truncate or break
                remaining = budget - used_chars
                if remaining > 200:
                    compressed_chunk = chunk.model_copy(
                        update={"content": compressed_content[:remaining] + "..."}
                    )
                    compressed_chunks.append(compressed_chunk)
                break

            compressed_chunk = chunk.model_copy(update={"content": compressed_content})
            compressed_chunks.append(compressed_chunk)
            used_chars += chunk_len

        return compressed_chunks
