"""Deterministic rule-based backend for offline tests and workloads."""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from agent_urp.core.models import Usage
from agent_urp.llm.base import LLMResponse

Responder = str | Callable[[str, "re.Match[str] | None"], str]
Rule = tuple[str | re.Pattern[str], Responder]


def _words(s: str) -> int:
    return len(s.split())


class ScriptedLLM:
    name = "scripted"

    def __init__(self, rules: Sequence[Rule], default: str = "OK") -> None:
        self._rules = [(re.compile(p, re.S) if isinstance(p, str) else p, r) for p, r in rules]
        self._default = default
        self.calls: list[str] = []

    def complete(self, prompt: str, params: Mapping[str, Any] | None = None) -> LLMResponse:
        self.calls.append(prompt)
        text = self._default
        for pattern, responder in self._rules:
            m = pattern.search(prompt)
            if m:
                text = responder(prompt, m) if callable(responder) else responder
                break
        return LLMResponse(
            text=text, usage=Usage(input_tokens=_words(prompt), output_tokens=_words(text))
        )
