"""Reuse decision per policy (spec §6.2). Returns the record to reuse, or None to execute."""
from __future__ import annotations

from collections.abc import Callable

from agent_urp.core.models import Policy, StepRecord


def choose_reuse(policy: Policy, *, key_static: str, old: StepRecord | None,
                 first_dirty_seq: int | None, memo_candidates: list[StepRecord],
                 verify: Callable[[StepRecord], bool], state_hash: str) -> StepRecord | None:
    if policy == Policy.FULL:
        return None
    if policy == Policy.SUFFIX:  # LangGraph time-travel semantics: position only
        if old is not None and (first_dirty_seq is None or old.seq < first_dirty_seq):
            return old
        return None
    if policy == Policy.MEMO:  # LangGraph CachePolicy semantics: whole-state key
        for c in memo_candidates:
            if c.key_static == key_static and c.params.get("state_hash") == state_hash:
                return c
        return None
    if policy == Policy.DEP:
        if old is not None and old.key_static == key_static and verify(old):
            return old
        for c in memo_candidates:
            if c.key_static == key_static and verify(c):
                return c
        return None
    raise ValueError(f"unknown policy {policy!r}")
