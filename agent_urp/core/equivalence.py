"""Pluggable equivalence oracle (spec §6.3). v1 ships L0 (identity) and L1 (normalized)."""
from __future__ import annotations

import re
from enum import IntEnum
from typing import Any

from agent_urp.core.hashing import canonical_json
from agent_urp.core.models import Artifact

_WS = re.compile(r"\s+")


class Level(IntEnum):
    L0 = 0  # byte-identical (same artifact id)
    L1 = 1  # whitespace-collapsed strings, numbers as float, canonical JSON structure


def normalize(content: Any) -> Any:
    if isinstance(content, str):
        return _WS.sub(" ", content).strip()
    if isinstance(content, bool):
        return content
    if isinstance(content, (int, float)):
        return float(content)
    if isinstance(content, dict):
        return {str(k): normalize(v) for k, v in sorted(content.items(), key=lambda kv: str(kv[0]))}
    if isinstance(content, (list, tuple)):
        return [normalize(v) for v in content]
    return content


def equivalent(a: Artifact, b: Artifact, level: Level = Level.L0) -> bool:
    if a.id == b.id:
        return True
    if level == Level.L0 or a.kind != b.kind:
        return False
    return canonical_json(normalize(a.content)) == canonical_json(normalize(b.content))
