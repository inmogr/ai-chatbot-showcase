"""Server composition root: the app factory and its lifespan (ARCHITECTURE §6, D-46)."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient

from app.adapters.embedder.sentence_transformer import (
    SentenceTransformerAdapter,
    load_sentence_transformer,
)
from app.adapters.employee_tool.mock_service import MockEmployeeService
from app.adapters.llm.openai_adapter import OpenAICompatibleLLMAdapter, make_llm_client
from app.adapters.vector_store.qdrant_reader import QdrantVectorReader
from app.config import ServerConfig
from app.domain.constants import AUTH_TIMEOUT_SECONDS, TURN_TIMEOUT_SECONDS
from app.domain.orchestrator import TurnOrchestrator
from app.domain.ports import EmployeeToolPort, LLMPort, QueryEmbedderPort, VectorReaderPort
from app.transport.websocket.routes import ChatRuntime, TurnRunner, router

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]
RuntimeFactory = Callable[[ServerConfig, TurnRunner], ChatRuntime]
APP_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def create_app(
    settings: ServerConfig | None = None,
    orchestrator: TurnRunner | None = None,
    use_lifespan: bool = True,
    *,
    auth_timeout: float = AUTH_TIMEOUT_SECONDS,
    turn_timeout: float = TURN_TIMEOUT_SECONDS,
) -> FastAPI:
    """Build the app. Importing this module loads no settings; the lifespan does (D-46)."""

    def runtime(config: ServerConfig, runner: TurnRunner) -> ChatRuntime:
        secret = config.jwt_secret.get_secret_value()
        return ChatRuntime(runner, secret, auth_timeout=auth_timeout, turn_timeout=turn_timeout)

    # No HTTP API exists, so the OpenAPI/docs routes are disabled (R-09).
    if use_lifespan:
        lifespan = _lifespan(settings, orchestrator, runtime)
        app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    else:
        if settings is None or orchestrator is None:
            raise ValueError("settings and orchestrator are required when the lifespan is skipped")
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.state.chat = runtime(settings, orchestrator)
    app.include_router(router)
    return app


def _lifespan(
    settings: ServerConfig | None, orchestrator: TurnRunner | None, runtime: RuntimeFactory
) -> Lifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _configure_app_logging()
        config = settings or ServerConfig()  # values come from the environment / .env
        if orchestrator is not None:
            app.state.chat = runtime(config, orchestrator)
            yield
            return
        async with production_orchestrator(config) as runner:
            app.state.chat = runtime(config, runner)
            yield

    return lifespan


def _configure_app_logging() -> None:
    """uvicorn configures only its own loggers, so `app.*` INFO records were dropped (R-12).
    Records still propagate to the root logger, where pytest's capture listens."""
    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(APP_LOG_FORMAT))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)


@asynccontextmanager
async def production_orchestrator(config: ServerConfig) -> AsyncIterator[TurnOrchestrator]:
    """Wire the real adapters, each typed against its port so mypy proves conformance.

    The collection health check runs before anything is served: a failure aborts startup and
    uvicorn exits with code 3 (D-25). Clients opened so far are closed on every path.
    """
    model = await asyncio.to_thread(load_sentence_transformer, config.embedding_model)
    adapter = SentenceTransformerAdapter(model, config.embedding_model)
    embedder: QueryEmbedderPort = adapter
    qdrant_key = config.qdrant_api_key.get_secret_value() if config.qdrant_api_key else None
    async with AsyncExitStack() as cleanup:
        qdrant = AsyncQdrantClient(url=config.qdrant_url, api_key=qdrant_key)
        cleanup.push_async_callback(qdrant.close)
        reader: VectorReaderPort = QdrantVectorReader(qdrant, config.qdrant_collection)
        await reader.verify_collection_health(adapter.dimension, config.embedding_model)
        endpoint = config.llm_endpoint()
        llm_client = make_llm_client(endpoint.base_url, endpoint.api_key)
        cleanup.push_async_callback(llm_client.close)
        llm: LLMPort = OpenAICompatibleLLMAdapter(
            llm_client, endpoint.model, config.max_tokens, extra_body=endpoint.extra_body
        )
        employee_tool: EmployeeToolPort = MockEmployeeService()
        yield TurnOrchestrator(embedder, reader, llm, employee_tool)


app = create_app()
