import abc
import hashlib
from typing import List, Optional, Dict
from collections import OrderedDict
from app.core.config import settings
from app.core.logging import logger


class EmbeddingCache:
    """In-memory LRU embedding cache to prevent redundant embedding computation."""
    def __init__(self, capacity: int = 5000):
        self.capacity = capacity
        self.cache: OrderedDict[str, List[float]] = OrderedDict()

    def get(self, key: str) -> Optional[List[float]]:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, key: str, vector: List[float]) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
            self.cache[key] = vector

    def make_key(self, model_name: str, text: str) -> str:
        return hashlib.sha256(f"{model_name}:{text.strip()}".encode("utf-8")).hexdigest()


# Shared global embedding cache
_GLOBAL_EMBEDDING_CACHE = EmbeddingCache(capacity=5000)


class BaseEmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embed a list of text documents with batching and caching."""
        pass

    @abc.abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        pass

    @property
    def model_name(self) -> str:
        """Embedding model identifier."""
        return "default-embedding-model"


class FastEmbedEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._dimension = settings.EMBEDDING_DIMENSION
        self.cache = _GLOBAL_EMBEDDING_CACHE

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            logger.info(f"Loading FastEmbed model: {self._model_name}")
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        # 1. Check cache
        for idx, text in enumerate(texts):
            key = self.cache.make_key(self._model_name, text)
            cached_vec = self.cache.get(key)
            if cached_vec is not None and len(cached_vec) == self._dimension:
                results[idx] = cached_vec
            else:
                missing_indices.append(idx)
                missing_texts.append(text)

        # 2. Compute missing in batches
        if missing_texts:
            model = self._get_model()
            for b_start in range(0, len(missing_texts), batch_size):
                b_slice = missing_texts[b_start : b_start + batch_size]
                b_indices = missing_indices[b_start : b_start + batch_size]

                embeddings_gen = model.embed(b_slice)
                for emb_np, orig_idx, txt in zip(embeddings_gen, b_indices, b_slice):
                    vec = emb_np.tolist()
                    if len(vec) != self._dimension:
                        logger.warning(f"Embedding dimension mismatch: expected {self._dimension}, got {len(vec)}")
                    key = self.cache.make_key(self._model_name, txt)
                    self.cache.put(key, vec)
                    results[orig_idx] = vec

        return [r if r is not None else [0.0] * self._dimension for r in results]

    def embed_query(self, query: str) -> List[float]:
        key = self.cache.make_key(self._model_name, query)
        cached = self.cache.get(key)
        if cached:
            return cached
        results = self.embed_documents([query])
        return results[0] if results else [0.0] * self._dimension


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model_name = "text-embedding-004"
        self._dimension = 768  # text-embedding-004 default dimension
        self.cache = _GLOBAL_EMBEDDING_CACHE

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        for idx, text in enumerate(texts):
            key = self.cache.make_key(self._model_name, text)
            cached_vec = self.cache.get(key)
            if cached_vec is not None and len(cached_vec) == self._dimension:
                results[idx] = cached_vec
            else:
                missing_indices.append(idx)
                missing_texts.append(text)

        if missing_texts:
            from google import genai
            client = genai.Client(api_key=self._api_key)
            for idx, text in zip(missing_indices, missing_texts):
                try:
                    res = client.models.embed_content(
                        model=self._model_name,
                        contents=text,
                    )
                    vec = res.embedding.values
                    key = self.cache.make_key(self._model_name, text)
                    self.cache.put(key, vec)
                    results[idx] = vec
                except Exception as e:
                    logger.error(f"Gemini embed error for text: {e}")
                    results[idx] = [0.0] * self._dimension

        return [r if r is not None else [0.0] * self._dimension for r in results]

    def embed_query(self, query: str) -> List[float]:
        key = self.cache.make_key(self._model_name, query)
        cached = self.cache.get(key)
        if cached:
            return cached
        results = self.embed_documents([query])
        return results[0] if results else [0.0] * self._dimension


def get_embedding_provider() -> BaseEmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiEmbeddingProvider()
    return FastEmbedEmbeddingProvider()
