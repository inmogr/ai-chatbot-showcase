"""Architecture rules and port conformance (C-09, M-28, ARCHITECTURE §3, §5)."""

import ast
import inspect
from pathlib import Path

from app.adapters.embedder.sentence_transformer import SentenceTransformerAdapter
from app.adapters.employee_tool.mock_service import MockEmployeeService
from app.adapters.llm.openai_adapter import OpenAICompatibleLLMAdapter
from app.adapters.vector_store.qdrant_reader import QdrantVectorReader
from app.adapters.vector_store.qdrant_writer import QdrantVectorWriter
from app.domain.ports import (
    DocumentEmbedderPort,
    EmployeeToolPort,
    LLMPort,
    QueryEmbedderPort,
    VectorReaderPort,
    VectorWriterPort,
)

ROOT = Path(__file__).resolve().parents[1]
IO_LIBRARIES = (
    "fastapi",
    "starlette",
    "uvicorn",
    "qdrant_client",
    "openai",
    "sentence_transformers",
    "transformers",
    "torch",
    "pypdfium2",
    "rapidocr",
    "numpy",
    "jwt",
    "httpx",
    "websockets",
)
COMPOSITION_ROOTS = {"app.main", "scripts.ingest"}
RULES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (
        ("app.domain",),
        (*IO_LIBRARIES, "app.adapters", "app.transport", "app.ingestion", "app.config", "app.main"),
    ),
    (
        ("app.transport",),
        ("app.adapters", "app.ingestion", "app.config", "app.main", "qdrant_client", "openai"),
    ),
    (("app.adapters", "app.ingestion"), ("app.transport", "app.main")),
]


def starts(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def module_name(path: Path) -> str:
    parts = path.relative_to(ROOT).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def source_modules() -> dict[str, set[str]]:
    files = [*ROOT.glob("app/**/*.py"), *ROOT.glob("scripts/**/*.py")]
    return {module_name(path): imports_of(path) for path in files}


def test_clean_architecture_dependency_rules() -> None:
    modules = source_modules()
    assert "app.main" in modules
    layer_violations = [
        f"{module} imports {dep}"
        for module, deps in modules.items()
        for owners, forbidden in RULES
        if starts(module, owners)
        for dep in deps
        if starts(dep, forbidden)
    ]
    adapter_importers = {
        module
        for module, deps in modules.items()
        if not starts(module, ("app.adapters",))
        and any(starts(dep, ("app.adapters",)) for dep in deps)
    }
    assert layer_violations == []
    assert adapter_importers <= COMPOSITION_ROOTS


def test_openai_adapter_satisfies_stream_chat_protocol() -> None:
    # mypy proves the full signature where app/main.py assigns the adapter to an `LLMPort`
    # variable; this runtime check guards the parameter names and the async-generator shape.
    port = inspect.signature(LLMPort.stream_chat)
    adapter = inspect.signature(OpenAICompatibleLLMAdapter.stream_chat)
    assert list(adapter.parameters) == list(port.parameters)
    assert inspect.isasyncgenfunction(OpenAICompatibleLLMAdapter.stream_chat)


PORT_IMPLEMENTATIONS: list[tuple[type, type]] = [
    (DocumentEmbedderPort, SentenceTransformerAdapter),
    (VectorWriterPort, QdrantVectorWriter),
    (QueryEmbedderPort, SentenceTransformerAdapter),
    (VectorReaderPort, QdrantVectorReader),
    (EmployeeToolPort, MockEmployeeService),
]


def test_adapters_satisfy_their_ports() -> None:
    # Static proof: scripts/ingest.py passes these adapters where the ports are expected (mypy).
    for port, adapter in PORT_IMPLEMENTATIONS:
        for name, member in vars(port).items():
            if callable(member) and not name.startswith("_"):
                expected = inspect.signature(member)
                assert list(inspect.signature(getattr(adapter, name)).parameters) == list(
                    expected.parameters
                ), f"{adapter.__name__}.{name}"
