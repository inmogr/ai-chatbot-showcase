"""Local embeddings with sentence-transformers (D-23); the model is loaded once and injected."""

import asyncio

from sentence_transformers import SentenceTransformer


def load_sentence_transformer(model_name: str) -> SentenceTransformer:
    """Blocking load (downloads ~130 MB on first use); the server calls it via asyncio.to_thread."""
    return SentenceTransformer(model_name)


class SentenceTransformerAdapter:
    """Satisfies DocumentEmbedderPort (and, from slice 4, QueryEmbedderPort)."""

    def __init__(self, model: SentenceTransformer, model_name: str) -> None:
        self._model = model
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        size = self._model.get_embedding_dimension()
        if size is None:
            raise ValueError(f"{self.model_name} does not report an embedding dimension")
        return int(size)

    async def embed_query(self, text: str) -> list[float]:
        """encode is synchronous CPU work (~7 ms): run it off the event loop (D-44)."""
        vector = await asyncio.to_thread(self._model.encode, text, convert_to_numpy=True)
        return [float(value) for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [[float(value) for value in vector] for vector in vectors]
