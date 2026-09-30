"""Mock external state with a content-addressed version, so tool reads can be
recorded as env@version.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from agent_urp.core.hashing import content_hash


class VersionedEnv:
    def __init__(self, name: str, state: dict[str, Any] | None = None) -> None:
        self.name = name
        self.state: dict[str, Any] = copy.deepcopy(state) if state else {}

    @property
    def version(self) -> str:
        return content_hash(self.state)

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self.state
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return copy.deepcopy(node)

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node = self.state
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = copy.deepcopy(value)

    def update(self, changes: Mapping[str, Any]) -> None:
        for path, value in changes.items():
            self.set(path, value)

    def snapshot(self) -> tuple[str, str, Any]:
        return self.name, self.version, copy.deepcopy(self.state)

    @classmethod
    def restore(cls, name: str, state: Any) -> VersionedEnv:
        return cls(name, state)
