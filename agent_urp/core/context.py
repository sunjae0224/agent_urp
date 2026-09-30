"""Prompt assembly from named, versioned blocks with a pluggable layout policy (spec §7.1)."""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from agent_urp.core.models import Block, Durability

LAYOUTS = ("naive", "stable_prefix")
_RANK = {Durability.HIGH: 0, Durability.MEDIUM: 1, Durability.LOW: 2}


@dataclass(frozen=True)
class Prompt:
    text: str
    blocks: tuple[tuple[str, str], ...]  # (name, version) in layout order


def render_block(b: Block) -> str:
    body = b.content if isinstance(b.content, str) else json.dumps(b.content, sort_keys=True,
                                                                     ensure_ascii=False)
    return f"[{b.name}]\n{body}"


class ContextAssembler:
    def __init__(self, layout: str = "naive") -> None:
        if layout not in LAYOUTS:
            raise ValueError(f"unknown layout {layout!r}; expected one of {LAYOUTS}")
        self.layout = layout

    def assemble(self, blocks: Sequence[Block], extra: str = "") -> Prompt:
        ordered = list(blocks)
        if self.layout == "stable_prefix":
            ordered.sort(key=lambda b: _RANK[b.durability])  # stable sort keeps ties in given order
        parts = [render_block(b) for b in ordered]
        if extra:
            parts.append(f"[input]\n{extra}")
        return Prompt(text="\n\n".join(parts), blocks=tuple((b.name, b.version) for b in ordered))
