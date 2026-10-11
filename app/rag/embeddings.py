import abc
from typing import List, Optional
from app.core.config import settings
from app.core.logging import logger


class BaseEmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text documents."""
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


class FastEmbedEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._dimension = settings.EMBEDDING_DIMENSION

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding
            logger.info(f"Loading FastEmbed model: {self._model_name}")
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        # FastEmbed returns a generator of numpy arrays
        embeddings_gen = model.embed(texts)
        return [emb.tolist() for emb in embeddings_gen]

    def embed_query(self, query: str) -> List[float]:
        results = self.embed_documents([query])
        return results[0] if results else [0.0] * self._dimension


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._dimension = 768  # text-embedding-004 default dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        from google import genai
        client = genai.Client(api_key=self._api_key)
        embeddings = []
        for text in texts:
            res = client.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
            embeddings.append(res.embedding.values)
        return embeddings

    def embed_query(self, query: str) -> List[float]:
        results = self.embed_documents([query])
        return results[0] if results else [0.0] * self._dimension


def get_embedding_provider() -> BaseEmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiEmbeddingProvider()
    return FastEmbedEmbeddingProvider()
