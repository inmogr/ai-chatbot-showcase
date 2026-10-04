"""Live provider checks (C-02, U-01): `uv run pytest -m live_llm` with a real key in .env."""

import time

import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.adapters.llm.openai_adapter import OpenAICompatibleLLMAdapter
from app.config import ServerConfig
from app.domain.models import TextDelta

pytestmark = pytest.mark.live_llm


@pytest.fixture
def live_adapter() -> OpenAICompatibleLLMAdapter:
    try:
        config = ServerConfig(_env_file=".env")
    except ValidationError:
        pytest.skip("needs JWT_SECRET and a real provider key in miniragchatbot/.env")
    endpoint = config.llm_endpoint()
    client = AsyncOpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)
    return OpenAICompatibleLLMAdapter(
        client, endpoint.model, config.max_tokens, extra_body=endpoint.extra_body
    )


async def test_live_streaming_token_cadence(live_adapter: OpenAICompatibleLLMAdapter) -> None:
    prompt = "Count from 1 to 40, one number per line, and nothing else."
    stamps = [
        time.monotonic()
        async for event in live_adapter.stream_chat([{"role": "user", "content": prompt}])
        if isinstance(event, TextDelta)
    ]
    assert len(stamps) > 5, "a real stream arrives as many deltas, not one chunk"
    print(f"{len(stamps)} deltas over {stamps[-1] - stamps[0]:.3f} s")  # logged only (D-82)


async def test_live_llm_invokes_employee_tool(live_adapter: OpenAICompatibleLLMAdapter) -> None:
    from app.domain.models import ToolCallRequest
    from app.domain.prompt import TOOLS, build_messages

    messages = build_messages("Who is my manager?", "emp-001")
    events = [e async for e in live_adapter.stream_chat(messages, tools=TOOLS, tool_choice="auto")]
    calls = [event for event in events if isinstance(event, ToolCallRequest)]
    assert [(c.name, c.parsed_arguments.get("user_id")) for c in calls] == [
        ("get_employee_context", "emp-001")
    ]
