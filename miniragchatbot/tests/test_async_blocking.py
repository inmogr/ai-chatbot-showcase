"""No blocking call in async code: encode runs in a worker thread (NFR-04, C-03, D-69)."""

from typing import Any

import pytest

from app.adapters.embedder.sentence_transformer import SentenceTransformerAdapter


class FakeModel:
    def encode(self, text: str, **_: Any) -> list[float]:
        return [0.25] * 384


async def test_embedding_inference_runs_in_thread_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatched: list[Any] = []

    async def spy_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
        dispatched.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "app.adapters.embedder.sentence_transformer.asyncio.to_thread", spy_to_thread
    )
    model = FakeModel()
    adapter = SentenceTransformerAdapter(model, "fake")  # type: ignore[arg-type]
    assert await adapter.embed_query("How many leave days?") == [0.25] * 384
    assert dispatched == [model.encode]  # the synchronous encode left the event loop
