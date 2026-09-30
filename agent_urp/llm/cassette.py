"""Record/replay wrapper: hash(backend, prompt, params) -> response, stored as one JSON file."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from agent_urp.core.hashing import content_hash
from agent_urp.llm.base import LLMBackend, LLMResponse

Mode = Literal["auto", "record", "replay"]


class CassetteMiss(KeyError):
    pass


class CassetteLLM:
    def __init__(
        self, path: str | Path, inner: LLMBackend | None = None, mode: Mode = "auto"
    ) -> None:
        self.path = Path(path)
        self.inner = inner
        self.mode = mode
        self.hits = 0
        self.misses = 0
        self._data: dict[str, Any] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        inner_name = inner.name if inner is not None else self._data.get("_backend", "none")
        self.name = f"cassette({inner_name})"

    def _key(self, prompt: str, params: Mapping[str, Any] | None) -> str:
        backend = self.inner.name if self.inner is not None else self._data.get("_backend", "none")
        return content_hash({"backend": backend, "prompt": prompt, "params": dict(params or {})})

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=1, sort_keys=True),
                             encoding="utf-8")

    def complete(self, prompt: str, params: Mapping[str, Any] | None = None) -> LLMResponse:
        key = self._key(prompt, params)
        if self.mode != "record" and key in self._data:
            self.hits += 1
            return LLMResponse.model_validate(self._data[key]["response"])
        self.misses += 1
        if self.mode == "replay" or self.inner is None:
            raise CassetteMiss(key)
        resp = self.inner.complete(prompt, params)
        self._data["_backend"] = self.inner.name
        self._data[key] = {
            "prompt": prompt, "params": dict(params or {}), "response": resp.model_dump()
        }
        self._save()
        return resp
