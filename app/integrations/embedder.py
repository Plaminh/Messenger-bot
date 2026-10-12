"""Embedding generator using multilingual-e5-small (384 dimensions).

Embeddings are normalized and generated asynchronously off the main event loop
using asyncio.to_thread. Applies 'query: ' and 'passage: ' prefixes per model design.
"""

import asyncio
import zlib
from typing import Any, List, Optional
import numpy as np

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

EMBEDDING_DIM = 384


class EmbedderUnavailableError(RuntimeError):
    """Raised when the embedding model cannot be loaded and dummy vectors are not allowed."""


class TextEmbedder:
    """Manages sentence-transformers embedding generation."""

    def __init__(self, model_name: Optional[str] = None, allow_dummy: Optional[bool] = None) -> None:
        self.model_name = model_name
        # None => read EMBEDDING_ALLOW_DUMMY from settings (default False)
        self._allow_dummy = allow_dummy
        self._model: Any = None
        self._lock = asyncio.Lock()

    def _dummy_allowed(self) -> bool:
        if self._allow_dummy is not None:
            return self._allow_dummy
        try:
            return bool(get_settings().EMBEDDING_ALLOW_DUMMY)
        except Exception:
            return False

    def _load_model(self) -> Any:
        """Synchronously load model into memory."""
        if self._model is not None:
            return self._model

        model_to_load = self.model_name
        if not model_to_load:
            try:
                settings = get_settings()
                model_to_load = settings.EMBEDDING_MODEL
            except Exception:
                model_to_load = "intfloat/multilingual-e5-small"

        logger.info("Lazy-loading embedding model: %s", model_to_load)
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_to_load, device="cpu")
        except Exception as exc:
            if not self._dummy_allowed():
                logger.error("Could not load embedding model %s: %s", model_to_load, exc)
                raise EmbedderUnavailableError(
                    f"Cannot load embedding model '{model_to_load}': {exc}"
                ) from exc
            logger.warning(
                "Could not load sentence_transformers (%s). Using dummy vectors (EMBEDDING_ALLOW_DUMMY=true).",
                exc,
            )
            self._model = None
        return self._model

    async def preload(self) -> None:
        """Load the model off the event loop (call at startup to fail fast)."""
        await asyncio.to_thread(self._load_model)

    def _sync_encode(self, texts: list[str]) -> list[list[float]]:
        """Synchronous CPU worker to encode text into normalized vectors."""
        model = self._load_model()
        if model is None:
            # Deterministic, text-dependent vectors for offline/unit tests only
            results = []
            for text in texts:
                rng = np.random.default_rng(seed=zlib.crc32(text.encode("utf-8")))
                vec = rng.standard_normal(EMBEDDING_DIM)
                norm = np.linalg.norm(vec)
                results.append((vec / norm).tolist())
            return results

        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query with 'query: ' prefix."""
        prefixed = f"query: {text.strip()}"
        vectors = await asyncio.to_thread(self._sync_encode, [prefixed])
        return vectors[0]

    async def embed_passage(self, text: str) -> list[float]:
        """Embed a passage or fact with 'passage: ' prefix."""
        prefixed = f"passage: {text.strip()}"
        vectors = await asyncio.to_thread(self._sync_encode, [prefixed])
        return vectors[0]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple passages."""
        if not texts:
            return []
        prefixed = [f"passage: {t.strip()}" for t in texts]
        return await asyncio.to_thread(self._sync_encode, prefixed)


# Module-level singleton
_embedder_instance: Optional[TextEmbedder] = None


def get_embedder() -> TextEmbedder:
    """Return shared TextEmbedder instance."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = TextEmbedder()
    return _embedder_instance


def set_embedder(embedder: Optional[TextEmbedder]) -> None:
    """Inject embedder instance (for tests)."""
    global _embedder_instance
    _embedder_instance = embedder
