"""Settings from the environment and `.env` in the working directory (ARCHITECTURE §9, D-47)."""

from dataclasses import dataclass, field
from typing import Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["groq", "gemini", "openrouter", "ollama", "openai", "anthropic"]

PROVIDER_BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1/",
}
OLLAMA_PLACEHOLDER_KEY = "ollama"  # the OpenAI SDK requires a key string; Ollama ignores it


@dataclass(frozen=True)
class LLMEndpoint:
    """Where and how the single OpenAI-compatible adapter reaches the selected provider."""

    base_url: str
    api_key: str = field(repr=False)  # never printed (R-08)
    model: str
    extra_body: dict[str, Any] | None


class ServerConfig(BaseSettings):
    """Server settings; startup fails fast on a missing secret or an incomplete provider."""

    # hide_input_in_errors: a failed validation must not echo raw inputs (JWT_SECRET, API keys)
    # into the startup log — pydantic would otherwise print a truncated repr of every value.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    jwt_secret: SecretStr
    llm_provider: Provider = "groq"
    max_tokens: int = Field(default=1500, ge=1)
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
    groq_extra_params: dict[str, Any] | None = None
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = ""
    embedding_provider: Literal["sentence-transformers"] = "sentence-transformers"  # D-64
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "acme_policies"

    @field_validator("jwt_secret")
    @classmethod
    def _secret_not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("JWT_SECRET must not be empty")
        return value

    @model_validator(mode="after")
    def _selected_provider_is_complete(self) -> Self:
        name = self.llm_provider.upper()
        key, model = self._provider_credentials()
        if not model:
            raise ValueError(f"{name}_MODEL must be set when LLM_PROVIDER={self.llm_provider}")
        if self.llm_provider != "ollama" and not key:
            raise ValueError(f"{name}_API_KEY must be set when LLM_PROVIDER={self.llm_provider}")
        return self

    def llm_endpoint(self) -> LLMEndpoint:
        """The selected provider's endpoint; `GROQ_EXTRA_PARAMS` is sent only to Groq (D-35)."""
        key, model = self._provider_credentials()
        if self.llm_provider == "ollama":
            base_url = f"{self.ollama_base_url.rstrip('/')}/v1"
        else:
            base_url = PROVIDER_BASE_URLS[self.llm_provider]
        extra = self.groq_extra_params if self.llm_provider == "groq" else None
        return LLMEndpoint(base_url, key or OLLAMA_PLACEHOLDER_KEY, model, extra)

    def _provider_credentials(self) -> tuple[str, str]:
        credentials = {
            "groq": (self.groq_api_key, self.groq_model),
            "gemini": (self.gemini_api_key, self.gemini_model),
            "openrouter": (self.openrouter_api_key, self.openrouter_model),
            "ollama": (SecretStr(""), self.ollama_model),
            "openai": (self.openai_api_key, self.openai_model),
            "anthropic": (self.anthropic_api_key, self.anthropic_model),
        }
        key, model = credentials[self.llm_provider]
        return key.get_secret_value(), model


class IngestConfig(BaseSettings):
    """Ingestion settings; never reads JWT_SECRET or provider keys (D-47)."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    docs_dir: str = "./docs"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "acme_policies"
    embedding_provider: Literal["sentence-transformers"] = (
        "sentence-transformers"  # only one (D-64)
    )
    embedding_model: str = "BAAI/bge-small-en-v1.5"
