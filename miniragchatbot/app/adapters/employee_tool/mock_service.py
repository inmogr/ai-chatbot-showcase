"""Mock employee directory: three lookups run concurrently in a TaskGroup (FR-24…FR-27, D-33)."""

import asyncio
import logging
from typing import Any

from app.domain.constants import TOOL_TIMEOUT_SECONDS
from app.domain.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


class MockEmployeeService:
    """Satisfies EmployeeToolPort. Each fetch stands in for a ~1 s downstream API call."""

    def __init__(self, timeout: float = TOOL_TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    async def fetch_profile(self, user_id: str) -> dict[str, Any]:
        await asyncio.sleep(1)
        return {"name": "Jane Doe", "grade": "Senior"}

    async def fetch_manager(self, user_id: str) -> dict[str, Any]:
        await asyncio.sleep(1)
        return {"manager": "John Smith"}

    async def fetch_team(self, user_id: str) -> dict[str, Any]:
        await asyncio.sleep(1)
        return {"team_size": 8, "team_name": "Platform"}

    async def get_employee_context(self, user_id: str) -> dict[str, Any]:
        """All three fetches run at once (~1 s, not ~3 s). A failure or the timeout cancels the
        siblings — unlike plain `gather`, which leaves them running (D-33)."""
        try:
            async with asyncio.timeout(self._timeout), asyncio.TaskGroup() as group:
                profile = group.create_task(self.fetch_profile(user_id))
                manager = group.create_task(self.fetch_manager(user_id))
                team = group.create_task(self.fetch_team(user_id))
        except TimeoutError as exc:
            logger.warning("employee lookup timed out after %g s", self._timeout)
            raise ToolExecutionError() from exc
        except ExceptionGroup as group_error:
            kinds = sorted({type(error).__name__ for error in group_error.exceptions})
            logger.warning("employee lookup failed: %s", ", ".join(kinds))  # classes, not text
            raise ToolExecutionError() from group_error
        return {"profile": profile.result(), "manager": manager.result(), "team": team.result()}
