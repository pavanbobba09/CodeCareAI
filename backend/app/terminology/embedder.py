"""Sentence embeddings for vector search: BAAI/bge-small-en-v1.5, 384 dimensions."""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.db.models import EMBEDDING_DIM

MODEL_NAME = "BAAI/bge-small-en-v1.5"
CACHE_DIR = Path.home() / ".cache" / "fastembed"


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class BgeEmbedder:
    """Runs bge-small via fastembed (ONNX, no torch). The model downloads on first use."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(CACHE_DIR))

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [v.tolist() for v in self._model.embed(texts, batch_size=256)]
        if vectors and len(vectors[0]) != EMBEDDING_DIM:
            raise ValueError(f"{MODEL_NAME} returned {len(vectors[0])} dims, want {EMBEDDING_DIM}")
        return vectors


@lru_cache
def get_embedder() -> Embedder:
    return BgeEmbedder()
