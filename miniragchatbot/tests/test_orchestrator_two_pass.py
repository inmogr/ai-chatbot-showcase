"""Two LLM passes around one tool call, with the IDOR check in code (FR-22, FR-23, D-32, D-52)."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from conftest import FakeEmployeeTool, FakeQueryEmbedder, FakeVectorReader, ScriptedLLM

from app.domain.events import StreamTextEvent, TurnDoneEvent
from app.domain.exceptions import LLMUnavailableError, ToolExecutionError
from app.domain.models import TextDelta, ToolCallRequest, UserClaims
from app.domain.orchestrator import TurnOrchestrator

# Literal expectations (ARCHITECTURE §4, §7.1), not imports, so a changed text or schema fails.
IDOR_DENIAL_TEXT = "Access denied: caller may only query their own context."
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_employee_context",
            "description": "Get the authenticated employee's own profile (name, grade), manager "
            "and team.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The caller's user ID."}
                },
                "required": ["user_id"],
            },
        },
    }
]

USER = UserClaims(sub="emp-001", exp=1, department="hr", level=1)


def call(
    user_id: Any = "emp-001", name: str = "get_employee_context", cid: str = "c1"
) -> ToolCallRequest:
    args = {} if user_id is None else {"user_id": user_id}
    return ToolCallRequest(id=cid, name=name, raw_arguments=json.dumps(args), parsed_arguments=args)


async def run(llm: ScriptedLLM, tool: FakeEmployeeTool) -> list[Any]:
    orchestrator = TurnOrchestrator(FakeQueryEmbedder(), FakeVectorReader(), llm, tool)
    return [event async for event in orchestrator.run_turn("Who is my manager?", USER)]


async def test_turn_invokes_employee_context_on_personal_query() -> None:
    log: list[str] = []
    llm = ScriptedLLM([[TextDelta("Let me check. "), call()], [TextDelta("John Smith.")]], log=log)
    tool = FakeEmployeeTool(log=log)
    events = await run(llm, tool)
    assert events == [
        StreamTextEvent("Let me check. "),
        StreamTextEvent("John Smith."),
        TurnDoneEvent(),
    ]
    # RF-4: text emitted before the call streams before the tool runs; then pass 2.
    assert log == ["llm1", "text:Let me check. ", "tool", "llm2", "text:John Smith."]
    first, second = llm.calls
    assert second["messages"][: len(first["messages"])] == first["messages"]  # excerpts carry over
    assert (first["tools"], first["tool_choice"]) == (TOOLS, "auto")
    assert (second["tools"], second["tool_choice"]) == (TOOLS, "none")  # no second tool round
    assistant, tool_message = second["messages"][-2:]
    assert assistant["tool_calls"][0]["function"]["name"] == "get_employee_context"
    assert tool_message == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": json.dumps(FakeEmployeeTool.RESULT),
    }
    assert tool.calls == ["emp-001"]


@pytest.mark.parametrize(("requested", "allowed"), [("emp-001", True), ("exec-003", False)])
async def test_tool_idor_validation_against_jwt_sub(requested: str, allowed: bool) -> None:
    llm = ScriptedLLM([[call(requested)], [TextDelta("answer")]])
    tool = FakeEmployeeTool()
    events = await run(llm, tool)
    assert events[-1] == TurnDoneEvent()  # a denial is not an error frame
    tool_message = llm.calls[1]["messages"][-1]
    if allowed:
        assert tool.calls == ["emp-001"]
    else:
        assert tool.calls == []  # no lookup ever runs for another user
        assert tool_message["content"] == IDOR_DENIAL_TEXT


async def test_only_first_tool_call_is_executed() -> None:
    llm = ScriptedLLM([[call(cid="first"), call(cid="second")], [TextDelta("ok")]])
    tool = FakeEmployeeTool()
    await run(llm, tool)
    assert tool.calls == ["emp-001"]
    echoed = llm.calls[1]["messages"][-2]["tool_calls"]
    assert [entry["id"] for entry in echoed] == ["first"]


@pytest.mark.parametrize(
    "bad_call",
    [call(name="drop_database"), call(user_id=None), call(user_id=42)],
    ids=["unknown_tool", "missing_user_id", "non_string_user_id"],
)
async def test_invalid_tool_request_maps_to_lookup_error(
    bad_call: ToolCallRequest, caplog: pytest.LogCaptureFixture
) -> None:
    tool = FakeEmployeeTool()
    with caplog.at_level(logging.WARNING), pytest.raises(ToolExecutionError):
        await run(ScriptedLLM([[bad_call], [TextDelta("never")]]), tool)
    assert tool.calls == []
    assert "invalid tool request" in caplog.text  # the reason reaches the server log (R-20)


async def test_pass_two_tool_call_without_text_raises_unavailable() -> None:
    # R-18: a provider that ignores tool_choice="none" must not end the turn with a bare `done`.
    llm = ScriptedLLM([[TextDelta("Let me check. "), call()], [call(cid="again")]])
    orchestrator = TurnOrchestrator(
        FakeQueryEmbedder(), FakeVectorReader(), llm, FakeEmployeeTool()
    )
    events: list[Any] = []
    with pytest.raises(LLMUnavailableError):
        async for event in orchestrator.run_turn("Who is my manager?", USER):
            events.append(event)
    assert events == [StreamTextEvent("Let me check. ")]  # no TurnDoneEvent


async def test_pass_two_text_with_a_stray_tool_call_still_answers() -> None:
    llm = ScriptedLLM([[call()], [TextDelta("John Smith."), call(cid="again")]])
    assert await run(llm, FakeEmployeeTool()) == [StreamTextEvent("John Smith."), TurnDoneEvent()]


class TrackingLLM:
    """Pass 1 asks for the tool; pass 2 streams two deltas. Records which streams were closed."""

    def __init__(self) -> None:
        self.opened = 0
        self.closed: list[int] = []

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[Any, None]:
        self.opened += 1
        number = self.opened
        try:
            if number == 1:
                yield call()
            else:
                yield TextDelta("John ")
                yield TextDelta("Smith.")
        finally:
            self.closed.append(number)


async def test_closing_the_turn_during_pass_two_closes_that_stream() -> None:
    # The pass-2 stream is consumed inside aclosing too (D-62): an abandoned turn closes it now.
    llm = TrackingLLM()
    orchestrator = TurnOrchestrator(
        FakeQueryEmbedder(), FakeVectorReader(), llm, FakeEmployeeTool()
    )
    turn = orchestrator.run_turn("Who is my manager?", USER)
    assert await anext(turn) == StreamTextEvent("John ")
    await turn.aclose()
    assert llm.closed == [1, 2]
