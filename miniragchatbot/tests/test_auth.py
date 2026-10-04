"""JWT verification and settings (FR-21, NFR-07, R-14, R-15, R-16, A-23)."""

import pytest
from conftest import TEST_SECRET, make_token, make_unsigned_token
from pydantic import ValidationError

from app.config import ServerConfig
from app.domain.models import UserClaims
from app.transport.websocket.auth import InvalidTokenError, decode_claims


def test_jwt_validation_strict_hs256_env_secret(settings: ServerConfig) -> None:
    secret = settings.jwt_secret.get_secret_value()
    claims = decode_claims(make_token("mgr-002", "hr", 2), secret)
    assert (claims.sub, claims.department, claims.level) == ("mgr-002", "hr", 2)
    assert isinstance(claims.exp, int)


def test_jwt_decode_expired_token() -> None:
    with pytest.raises(InvalidTokenError):
        decode_claims(make_token(exp_offset=-60), TEST_SECRET)
    # Inside the 10 s leeway the token is still accepted.
    assert decode_claims(make_token(exp_offset=-5), TEST_SECRET).sub == "emp-001"


def test_jwt_decode_unpinned_algorithm_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_claims(make_unsigned_token(), TEST_SECRET)
    with pytest.raises(InvalidTokenError):
        decode_claims(make_token(algorithm="HS512"), TEST_SECRET)


@pytest.mark.parametrize("value", [None, "", "   "], ids=["missing", "empty", "blank"])
def test_jwt_missing_secret_fails_fast(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk-placeholder")  # isolate the JWT_SECRET failure
    if value is None:
        monkeypatch.delenv("JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET", value)
    with pytest.raises(ValidationError, match="jwt_secret"):
        ServerConfig(_env_file=None)


def test_config_errors_never_echo_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    # Found by the slice-2 real run: pydantic echoed a truncated JWT_SECRET at startup (I-04).
    monkeypatch.setenv("JWT_SECRET", "super-secret-jwt-value-0123456789")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with pytest.raises(ValidationError) as raised:
        ServerConfig(_env_file=None)
    message = str(raised.value)
    assert "GROQ_API_KEY must be set" in message
    # pydantic truncates long inputs in the middle, so even a short prefix is a leak.
    assert "input_value" not in message
    assert "super-se" not in message


PROVIDER_ENV = (
    "LLM_PROVIDER",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "GROQ_EXTRA_PARAMS",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
)


def test_server_config_provider_key_and_model_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        ServerConfig(_env_file=None)  # default provider groq without a key
    monkeypatch.setenv("GROQ_API_KEY", "gsk-placeholder")
    groq = ServerConfig(_env_file=None).llm_endpoint()
    assert (groq.base_url, groq.model) == ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b")

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-placeholder")
    with pytest.raises(ValidationError, match="OPENAI_MODEL"):
        ServerConfig(_env_file=None)  # key without a model

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    assert ServerConfig(_env_file=None).llm_endpoint().base_url == "http://localhost:11434/v1"

    urls = {
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "openrouter": "https://openrouter.ai/api/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1/",
    }
    for provider, url in urls.items():
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv(f"{provider.upper()}_API_KEY", "key")
        monkeypatch.setenv(f"{provider.upper()}_MODEL", "model")
        assert ServerConfig(_env_file=None).llm_endpoint().base_url == url


def test_user_claims_validation_rules() -> None:
    base = {"sub": "u-1", "exp": 1, "department": "legal", "level": 7}
    assert UserClaims.model_validate(base).department == "legal"  # unknown departments accepted
    for bad in ({"department": ""}, {"sub": ""}, {"level": 0}):
        with pytest.raises(ValidationError):
            UserClaims.model_validate(base | bad)


def test_runtime_reprs_hide_secrets() -> None:
    # R-08: a logged or printed object must not reveal the JWT secret or a provider key.
    from app.config import LLMEndpoint
    from app.transport.websocket.routes import ChatRuntime

    runtime = ChatRuntime(runner=object(), jwt_secret="jwt-secret-value")  # type: ignore[arg-type]
    endpoint = LLMEndpoint("https://llm.test/v1", "provider-key-value", "model", None)
    assert "jwt-secret-value" not in repr(runtime)
    assert "provider-key-value" not in repr(endpoint)


def test_server_config_rejects_unknown_embedding_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-placeholder")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")  # only sentence-transformers exists (D-64)
    with pytest.raises(ValidationError, match="embedding_provider"):
        ServerConfig(_env_file=None)
