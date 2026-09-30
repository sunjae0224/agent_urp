"""Data model: content-addressed artifacts/blocks and append-only step records (spec §5)."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_urp.core.hashing import content_hash


class StepKind(str, Enum):  # noqa: UP042
    LLM = "llm"
    TOOL = "tool"
    MEMORY = "memory"
    ASSEMBLE = "assemble"


class Decision(str, Enum):  # noqa: UP042
    REUSE = "reuse"
    REBUILD = "rebuild"
    RERUN = "rerun"
    LIVE = "live"  # executed with no matching record in the parent run


class Policy(str, Enum):  # noqa: UP042
    FULL = "full"
    SUFFIX = "suffix"
    MEMO = "memo"
    DEP = "dep"


class Durability(str, Enum):  # noqa: UP042
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BlockKind(str, Enum):  # noqa: UP042
    STATIC = "static"
    USER = "user"
    MEMORY = "memory"
    DERIVED = "derived"


class SamplingIntent(str, Enum):  # noqa: UP042
    STABLE = "stable"
    FRESH = "fresh"


class Artifact(BaseModel):
    id: str
    kind: str
    content: Any
    created_by: str | None = None

    @classmethod
    def of(cls, kind: str, content: Any, created_by: str | None = None) -> Artifact:
        return cls(id=content_hash({"kind": kind, "content": content}), kind=kind,
                   content=content, created_by=created_by)


class Block(BaseModel):
    name: str
    version: str
    content: Any
    kind: BlockKind = BlockKind.STATIC
    durability: Durability = Durability.MEDIUM
    derived_from: list[str] = Field(default_factory=list)

    @classmethod
    def of(cls, name: str, content: Any, kind: BlockKind = BlockKind.STATIC,
           durability: Durability = Durability.MEDIUM, derived_from: tuple[str, ...] = ()) -> Block:
        return cls(name=name, version=content_hash(content), content=content, kind=kind,
                   durability=durability, derived_from=list(derived_from))


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: float = 0.0

    def __add__(self, other: Usage) -> Usage:
        return Usage(input_tokens=self.input_tokens + other.input_tokens,
                     output_tokens=self.output_tokens + other.output_tokens,
                     cached_tokens=self.cached_tokens + other.cached_tokens,
                     latency_ms=self.latency_ms + other.latency_ms)


class ReadRef(BaseModel):
    kind: Literal["block", "artifact", "env"]
    name: str      # block name / artifact id / env name
    version: str   # block version / artifact id / env version


class WriteRef(BaseModel):
    kind: Literal["block", "artifact"]
    name: str
    version: str


class StepRecord(BaseModel):
    id: str
    run_id: str
    seq: int
    name: str
    occurrence: int
    kind: StepKind
    key_static: str
    reads: list[ReadRef] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    sampling_intent: SamplingIntent = SamplingIntent.STABLE
    code_version: str
    input_hash: str
    writes: list[WriteRef] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    decision: Decision
    equivalent_to: str | None = None   # backdating: old step whose output we adopted
    reused_from: str | None = None     # REUSE: the record we copied
    llm_calls: int = 0
    tool_calls: int = 0


class Edit(BaseModel):
    id: str
    kind: Literal["constraint", "tool_result", "memory", "system"]
    target: str
    target_kind: Literal["block", "env"]
    content: Any                       # new block content, or {path: value} updates for env
    old_version: str | None = None
    new_version: str | None = None

    @classmethod
    def of(cls, kind: str, target: str, target_kind: str, content: Any) -> Edit:
        return cls(id=content_hash({"kind": kind, "target": target, "target_kind": target_kind,
                                    "content": content}),
                   kind=kind, target=target, target_kind=target_kind, content=content)


class Run(BaseModel):
    id: str
    parent_run_id: str | None = None
    edit_id: str | None = None
    policy: Policy
    layout: str = "naive"
    initial_blocks: dict[str, str] = Field(default_factory=dict)  # name -> version
    initial_envs: dict[str, str] = Field(default_factory=dict)    # name -> version
    metrics: dict[str, Any] = Field(default_factory=dict)
