"""Dependency graph reconstructed from step records (spec §4):

block/env/artifact -> step -> artifact/block.
"""
from __future__ import annotations

from collections.abc import Iterable

import networkx as nx

from agent_urp.core.models import ReadRef, StepRecord, WriteRef


def _node(ref: ReadRef | WriteRef) -> str:
    if ref.kind == "artifact":
        return f"artifact:{ref.name}"
    return f"{ref.kind}:{ref.name}@{ref.version}"


class DepGraph:
    def __init__(self, steps: list[StepRecord]) -> None:
        self.steps = sorted(steps, key=lambda s: s.seq)
        self.by_id = {s.id: s for s in self.steps}
        self.g = nx.DiGraph()
        for s in self.steps:
            sid = f"step:{s.id}"
            self.g.add_node(sid, kind="step", name=s.name)
            for r in s.reads:
                self.g.add_edge(_node(r), sid)
            for w in s.writes:
                self.g.add_edge(sid, _node(w))

    @classmethod
    def from_steps(cls, steps: list[StepRecord]) -> DepGraph:
        return cls(steps)

    def readers_of(self, name: str) -> list[StepRecord]:
        return [s for s in self.steps
                if any(r.kind in ("block", "env") and r.name == name for r in s.reads)]

    def first_dirty_seq(self, names: Iterable[str]) -> int | None:
        seqs = [s.seq for n in names for s in self.readers_of(n)]
        return min(seqs) if seqs else None

    def dirty_from(self, names: Iterable[str]) -> set[str]:
        dirty: set[str] = set()
        for n in names:
            for s in self.readers_of(n):
                dirty.add(s.id)
                for d in nx.descendants(self.g, f"step:{s.id}"):
                    if d.startswith("step:"):
                        dirty.add(d[len("step:"):])
        return dirty

    def to_dot(self) -> str:
        lines = ["digraph deps {"]
        for n, data in self.g.nodes(data=True):
            label = data.get("name", n)
            shape = "box" if data.get("kind") == "step" else "ellipse"
            lines.append(f'  "{n}" [label="{label}", shape={shape}];')
        for a, b in self.g.edges:
            lines.append(f'  "{a}" -> "{b}";')
        lines.append("}")
        return "\n".join(lines)
