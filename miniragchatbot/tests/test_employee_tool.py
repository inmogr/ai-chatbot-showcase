"""The parallel mock tool: three 1 s lookups in ~1 s, not ~3 s (FR-24…FR-27, NFR-01, D-33)."""

import asyncio
import logging
import time
from typing import Any

import pytest

from app.adapters.employee_tool.mock_service import MockEmployeeService
from app.domain.exceptions import ToolExecutionError


class SpyService(MockEmployeeService):
    """Records which fetches started and finished."""

    def __init__(self, fail_manager: bool = False, timeout: float = 2.0) -> None:
        super().__init__(timeout=timeout)
        self.fail_manager = fail_manager
        self.started: list[str] = []
        self.finished: list[str] = []
        self.cancelled: list[str] = []

    async def fetch_profile(self, user_id: str) -> dict[str, Any]:
        self.started.append("profile")
        try:
            result = await super().fetch_profile(user_id)
        except asyncio.CancelledError:
            self.cancelled.append("profile")
            raise
        self.finished.append("profile")
        return result

    async def fetch_manager(self, user_id: str) -> dict[str, Any]:
        self.started.append("manager")
        if self.fail_manager:
            await asyncio.sleep(0.05)
            raise RuntimeError("manager service down")
        result = await super().fetch_manager(user_id)
        self.finished.append("manager")
        return result

    async def fetch_team(self, user_id: str) -> dict[str, Any]:
        self.started.append("team")
        try:
            result = await super().fetch_team(user_id)
        except asyncio.CancelledError:
            self.cancelled.append("team")
            raise
        self.finished.append("team")
        return result


async def test_employee_tool_executes_parallel_under_1_35s() -> None:
    service = SpyService()
    started = time.perf_counter()
    await service.get_employee_context("emp-001")
    elapsed = time.perf_counter() - started
    assert sorted(service.started) == ["manager", "profile", "team"]
    assert elapsed < 1.35, f"{elapsed:.3f} s — sequential awaits would take ~3 s"


async def test_employee_tool_returns_brief_payloads() -> None:
    assert await MockEmployeeService().get_employee_context("emp-001") == {
        "profile": {"name": "Jane Doe", "grade": "Senior"},
        "manager": {"manager": "John Smith"},
        "team": {"team_size": 8, "team_name": "Platform"},
    }


async def test_tool_subtask_failure_raises_catalog_error() -> None:
    failing = SpyService(fail_manager=True)
    with pytest.raises(ToolExecutionError) as raised:
        await failing.get_employee_context("emp-001")
    assert raised.value.message == "Failed to execute employee lookup."
    assert failing.finished == []
    assert sorted(failing.cancelled) == ["profile", "team"]  # TaskGroup cancels; gather would not
    with pytest.raises(ToolExecutionError):
        await SpyService(timeout=0.05).get_employee_context("emp-001")  # the 2 s ceiling, shrunk


async def test_tool_failures_log_their_kind(caplog: pytest.LogCaptureFixture) -> None:
    # R-20: both failures read "Failed to execute employee lookup." to the user; the log differs.
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ToolExecutionError):
            await SpyService(fail_manager=True).get_employee_context("emp-001")
        with pytest.raises(ToolExecutionError):
            await SpyService(timeout=0.05).get_employee_context("emp-001")
    assert "employee lookup failed: RuntimeError" in caplog.text
    assert "employee lookup timed out after 0.05 s" in caplog.text
    assert "manager service down" not in caplog.text  # class names only, never messages
