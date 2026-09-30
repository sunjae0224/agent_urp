"""Program runner with record/replay of step calls (spec §6): Temporal-style re-execution of the
orchestration, verifying/constructive-trace reuse of step results, and equivalence backdating.
Memo (constructive-trace) lookup is scoped to the current run and its ancestor runs (lineage), so
sibling replays of the same parent never reuse each other's records."""
from __future__ import annotations

import copy
import functools
import inspect
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_urp.core.context import ContextAssembler
from agent_urp.core.dep_graph import DepGraph
from agent_urp.core.equivalence import Level, equivalent
from agent_urp.core.hashing import content_hash
from agent_urp.core.models import (
    Artifact,
    Block,
    BlockKind,
    Decision,
    Durability,
    Edit,
    Policy,
    ReadRef,
    Run,
    SamplingIntent,
    StepKind,
    StepRecord,
    Usage,
    WriteRef,
)
from agent_urp.core.policies import choose_reuse
from agent_urp.core.trace_store import TraceStore
from agent_urp.llm.base import LLMBackend
from agent_urp.tools.env import VersionedEnv

Program = Callable[["StepContext"], Any]


class UnknownBlock(KeyError):
    pass


class UnknownEnv(KeyError):
    pass


class NotInStep(RuntimeError):
    pass


def code_version_of(fn: Callable[..., Any]) -> str:
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        src = getattr(fn, "__qualname__", repr(fn))
    return content_hash(src)


@dataclass
class _Frame:
    reads: dict[tuple[str, str], ReadRef] = field(default_factory=dict)
    writes: list[WriteRef] = field(default_factory=list)
    written: set[str] = field(default_factory=set)  # blocks set by this step: not reads
    usage: Usage = field(default_factory=Usage)
    llm_calls: int = 0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    run: Run
    steps: list[StepRecord]
    output: Any
    metrics: dict[str, Any]


def compute_metrics(records: Sequence[StepRecord]) -> dict[str, Any]:
    usage = sum((r.usage for r in records), Usage())
    by_decision = {d.value: sum(1 for r in records if r.decision == d) for d in Decision}
    return {
        "steps": len(records),
        "executed": [r.name for r in records if r.decision != Decision.REUSE],
        "reused": [r.name for r in records if r.decision == Decision.REUSE],
        "by_decision": by_decision,
        "llm_calls": sum(r.llm_calls for r in records),
        "tool_calls": sum(r.tool_calls for r in records),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cached_tokens": usage.cached_tokens,
    }


class StepContext:
    def __init__(self, runtime: Runtime, run: Run, policy: Policy, blocks: Sequence[Block],
                 envs: Sequence[VersionedEnv], parent_steps: Sequence[StepRecord],
                 first_dirty_seq: int | None) -> None:
        self._rt = runtime
        self.run = run
        self.policy = policy
        self.blocks: dict[str, Block] = {b.name: b for b in blocks}
        self.envs: dict[str, VersionedEnv] = {e.name: VersionedEnv.restore(e.name, e.state)
                                              for e in envs}
        self._parent = {(s.name, s.occurrence): s for s in parent_steps}
        self._first_dirty_seq = first_dirty_seq
        # Memo scope = this run + its ancestors, so sibling replays never feed each other.
        self._lineage = {run.id}
        pid = run.parent_run_id
        while pid is not None and pid not in self._lineage:
            self._lineage.add(pid)
            pid = runtime.store.get_run(pid).parent_run_id
        self._occ: dict[str, int] = {}
        self._seq = 0
        self._frame: _Frame | None = None
        self.records: list[StepRecord] = []

    # --- state access (records reads/writes when inside a step) ---------------
    def _block_obj(self, name: str) -> Block:
        b = self.blocks.get(name)
        if b is None:
            raise UnknownBlock(name)
        if self._frame is not None and name not in self._frame.written:
            self._frame.reads[("block", name)] = ReadRef(kind="block", name=name, version=b.version)
        return b

    def block(self, name: str) -> Any:
        return copy.deepcopy(self._block_obj(name).content)

    def set_block(self, name: str, content: Any) -> Block:
        if self._frame is None:
            raise NotInStep("set_block() is only allowed inside a step")
        old = self.blocks.get(name)
        new = Block.of(name, content, kind=old.kind if old else BlockKind.DERIVED,
                       durability=old.durability if old else Durability.MEDIUM)
        self._rt.store.put_block(new)
        self.blocks[name] = new
        self._frame.writes.append(WriteRef(kind="block", name=name, version=new.version))
        self._frame.written.add(name)
        return new

    def env(self, name: str) -> VersionedEnv:
        e = self.envs.get(name)
        if e is None:
            raise UnknownEnv(name)
        if self._frame is not None:
            self._frame.reads[("env", name)] = ReadRef(kind="env", name=name, version=e.version)
        return e

    def llm(self, blocks: Sequence[str], extra: str = "",
            params: Mapping[str, Any] | None = None) -> str:
        if self._frame is None:
            raise NotInStep("llm() is only allowed inside a step")
        prompt = self._rt.assembler.assemble([self._block_obj(n) for n in blocks], extra)
        resp = self._rt.llm.complete(prompt.text, dict(params or {}))
        self._frame.usage = self._frame.usage + resp.usage
        self._frame.llm_calls += 1
        self._frame.params.setdefault("llm", []).append(
            {"blocks": [list(b) for b in prompt.blocks], "params": dict(params or {})})
        return resp.text

    # --- the core: execute-or-reuse one step call -----------------------------
    def step(self, name: str, kind: StepKind, fn: Callable[..., Any], *,
             args: Mapping[str, Any] | None = None, code_version: str | None = None,
             sampling_intent: SamplingIntent = SamplingIntent.STABLE) -> Artifact:
        if self._frame is not None:
            raise NotInStep("nested steps are not supported")
        args = dict(args or {})
        occ = self._occ.get(name, 0)
        self._occ[name] = occ + 1
        # Artifact args keyed by parameter name, so swapped arguments never share a key.
        arts = {k: v.id for k, v in args.items() if isinstance(v, Artifact)}
        art_reads = [ReadRef(kind="artifact", name=i, version=i) for i in arts.values()]
        plain = {k: v for k, v in args.items() if k not in arts}
        cv = code_version or code_version_of(fn)
        key_static = content_hash({"name": name, "kind": kind.value, "code_version": cv,
                                   "artifacts": arts, "args": plain})
        state_hash = content_hash({"blocks": {n: b.version for n, b in self.blocks.items()},
                                   "envs": {n: e.version for n, e in self.envs.items()}})
        old = self._parent.get((name, occ))
        reuse = None
        if sampling_intent == SamplingIntent.STABLE:
            memo = [c for c in self._rt.store.memo_candidates(key_static)
                    if c.run_id in self._lineage]
            reuse = choose_reuse(self.policy, key_static=key_static, old=old,
                                 first_dirty_seq=self._first_dirty_seq,
                                 memo_candidates=memo, verify=self._verify,
                                 state_hash=state_hash)
        self._seq += 1
        seq = self._seq
        step_id = f"{self.run.id}:{seq:04d}"
        if reuse is not None:
            self._apply_writes(reuse)
            rec = reuse.model_copy(update={"id": step_id, "run_id": self.run.id, "seq": seq,
                                           "occurrence": occ, "decision": Decision.REUSE,
                                           "usage": Usage(), "llm_calls": 0, "tool_calls": 0,
                                           "equivalent_to": None, "reused_from": reuse.id})
            self._rt.store.record_step(rec)
            self.records.append(rec)
            return self._output_of(rec)

        frame = _Frame()
        self._frame = frame
        try:
            result = fn(self, **args)
        finally:
            self._frame = None
        out = Artifact.of(kind.value, result, created_by=step_id)
        self._rt.store.put_artifact(out)
        decision = Decision.LIVE if old is None else (
            Decision.REBUILD if kind == StepKind.ASSEMBLE else Decision.RERUN)
        equivalent_to = None
        if self.policy == Policy.DEP and old is not None and self._rt.level > Level.L0:
            old_out = self._output_of(old)
            if out.id != old_out.id and equivalent(out, old_out, self._rt.level):
                out, equivalent_to = old_out, old.id
        reads = art_reads + sorted(frame.reads.values(), key=lambda r: (r.kind, r.name))
        writes = frame.writes + [WriteRef(kind="artifact", name=out.id, version=out.id)]
        rec = StepRecord(
            id=step_id, run_id=self.run.id, seq=seq, name=name, occurrence=occ, kind=kind,
            key_static=key_static, reads=reads,
            params={"args": plain, "state_hash": state_hash, **frame.params},
            sampling_intent=sampling_intent, code_version=cv,
            input_hash=content_hash({"key_static": key_static, "reads": reads}),
            writes=writes, usage=frame.usage, decision=decision, equivalent_to=equivalent_to,
            llm_calls=frame.llm_calls, tool_calls=1 if kind == StepKind.TOOL else 0)
        self._rt.store.record_step(rec)
        self._rt.store.memo_put(rec)
        self.records.append(rec)
        return out

    def _verify(self, rec: StepRecord) -> bool:
        for r in rec.reads:
            if r.kind == "block":
                b = self.blocks.get(r.name)
                if b is None or b.version != r.version:
                    return False
            elif r.kind == "env":
                e = self.envs.get(r.name)
                if e is None or e.version != r.version:
                    return False
        return True

    def _apply_writes(self, rec: StepRecord) -> None:
        for w in rec.writes:
            if w.kind == "block":
                self.blocks[w.name] = self._rt.store.get_block(w.name, w.version)

    def _output_of(self, rec: StepRecord) -> Artifact:
        arts = [w for w in rec.writes if w.kind == "artifact"]
        return self._rt.store.get_artifact(arts[-1].name)


class Runtime:
    def __init__(self, store: TraceStore, llm: LLMBackend,
                 assembler: ContextAssembler | None = None, level: Level = Level.L0) -> None:
        self.store = store
        self.llm = llm
        self.assembler = assembler or ContextAssembler("naive")
        self.level = level

    def run(self, program: Program, blocks: Sequence[Block], envs: Sequence[VersionedEnv],
            policy: Policy = Policy.FULL, parent_run: Run | None = None,
            edit: Edit | None = None) -> RunResult:
        run = Run(id=uuid.uuid4().hex[:12], parent_run_id=parent_run.id if parent_run else None,
                  edit_id=edit.id if edit else None, policy=policy, layout=self.assembler.layout,
                  initial_blocks={b.name: b.version for b in blocks},
                  initial_envs={e.name: e.version for e in envs})
        for b in blocks:
            self.store.put_block(b)
        for e in envs:
            self.store.put_env_snapshot(*e.snapshot())
        self.store.put_run(run)
        parent_steps = self.store.get_steps(parent_run.id) if parent_run else []
        first_dirty_seq = None
        if parent_run is not None and edit is not None:
            first_dirty_seq = DepGraph.from_steps(parent_steps).first_dirty_seq([edit.target])
        ctx = StepContext(self, run, policy, blocks, envs, parent_steps, first_dirty_seq)
        output = program(ctx)
        metrics = compute_metrics(ctx.records)
        run.metrics = metrics
        self.store.update_run_metrics(run.id, metrics)
        return RunResult(run=run, steps=ctx.records, output=output, metrics=metrics)

    def replay(self, program: Program, parent_run_id: str, edit: Edit, policy: Policy) -> RunResult:
        parent = self.store.get_run(parent_run_id)
        blocks = [self.store.get_block(n, v) for n, v in parent.initial_blocks.items()]
        envs = [VersionedEnv.restore(n, self.store.get_env_snapshot(n, v))
                for n, v in parent.initial_envs.items()]
        if edit.target_kind == "block":
            idx = {b.name: i for i, b in enumerate(blocks)}
            if edit.target not in idx:
                raise UnknownBlock(edit.target)
            old = blocks[idx[edit.target]]
            new = Block.of(edit.target, edit.content, kind=old.kind, durability=old.durability)
            blocks[idx[edit.target]] = new
            edit = edit.model_copy(update={"old_version": old.version, "new_version": new.version})
        else:
            env = next((e for e in envs if e.name == edit.target), None)
            if env is None:
                raise UnknownEnv(edit.target)
            old_v = env.version
            env.update(edit.content)
            edit = edit.model_copy(update={"old_version": old_v, "new_version": env.version})
        self.store.put_edit(edit)
        return self.run(program, blocks, envs, policy, parent_run=parent, edit=edit)


def step(
    kind: StepKind = StepKind.TOOL, name: str | None = None,
    sampling_intent: SamplingIntent = SamplingIntent.STABLE,
) -> Callable[[Callable[..., Any]], Callable[..., Artifact]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Artifact]:
        cv = code_version_of(fn)
        step_name = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(ctx: StepContext, **kwargs: Any) -> Artifact:
            return ctx.step(step_name, kind, fn, args=kwargs, code_version=cv,
                            sampling_intent=sampling_intent)

        wrapper.__step_kind__ = kind  # type: ignore[attr-defined]
        return wrapper
    return deco
