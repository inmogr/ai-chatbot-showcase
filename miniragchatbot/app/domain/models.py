"""Domain types: validated identity claims (D-11, D-57) and LLM stream events (D-31)."""

import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class UserClaims(BaseModel):
    """Claims of a verified JWT. Only these drive RBAC and the tool's IDOR check."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    sub: NonEmptyStr
    exp: int
    department: NonEmptyStr
    level: Annotated[StrictInt, Field(ge=1)]


class EmployeeContextArgs(BaseModel):
    """The employee tool's one argument, validated from the model's JSON."""

    user_id: StrictStr


@dataclass(frozen=True)
class RbacScope:
    """What the reader turns into the Qdrant filter; built only from verified claims."""

    department: str
    level: int


@dataclass(frozen=True)
class TextDelta:
    """A piece of answer text from the LLM stream, forwarded as soon as it arrives."""

    text: str


@dataclass(frozen=True)
class ToolCallRequest:
    """A complete tool call assembled from streamed fragments."""

    id: str
    name: str
    raw_arguments: str
    parsed_arguments: dict[str, Any] = field(default_factory=dict)


LLMStreamEvent = TextDelta | ToolCallRequest


@dataclass(frozen=True)
class PolicyChunk:
    """One indexed chunk with the RBAC metadata the brief requires on every chunk."""

    text: str
    department: str
    access_level: int
    source_file: str
    page: int
    chunk_index: int
    model_name: str = ""

    @property
    def point_id(self) -> str:
        """Deterministic id, so a re-run rewrites the same points (D-24)."""
        name = f"file://{self.source_file}/{self.page}#{self.chunk_index}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, name))
