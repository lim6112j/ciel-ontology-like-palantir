"""Agent definitions: prompt, allowed actions/functions, and loop limits."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentKind(StrEnum):
    INTAKE = "intake"
    DISPATCH = "dispatch"
    EXCEPTION = "exception"
    COPILOT = "copilot"


class AgentDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=r"^[a-z][a-zA-Z0-9]*$")
    displayName: str
    description: str | None = None
    kind: AgentKind
    systemPrompt: str
    model: str | None = None
    fallbackModel: str | None = None
    temperature: float = 0.1
    maxTurns: int = 12
    maxTokens: int = 4096
    #: Actions this agent may propose. Empty means none.
    allowedActionTypes: list[str] = Field(default_factory=list)
    #: Read functions this agent may call via `run_function`.
    allowedFunctions: list[str] = Field(default_factory=list)
    #: Upper bound on proposals created per invocation.
    maxProposals: int = 5
    #: Tool result page size cap (context hygiene for browsing agents).
    maxPageSize: int = 20
