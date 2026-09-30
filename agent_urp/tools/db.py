"""Mock table lookup over env['tables'][table] with equality filters."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_urp.tools.env import VersionedEnv


def db_query(env: VersionedEnv, table: str, where: Mapping[str, Any] | None = None) -> list[dict]:
    rows = env.get(f"tables.{table}", []) or []
    where = dict(where or {})
    return [r for r in rows if all(r.get(k) == v for k, v in where.items())]
