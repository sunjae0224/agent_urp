"""Backend-agnostic LLM interface: every backend returns text plus token usage."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from agent_urp.core.models import Usage


class LLMResponse(BaseModel):
    text: str
    usage: Usage


@runtime_checkable
class LLMBackend(Protocol):
    name: str

    def complete(self, prompt: str, params: Mapping[str, Any] | None = None) -> LLMResponse: ...
