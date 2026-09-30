import pytest
from pydantic import BaseModel

from agent_urp.core.context import ContextAssembler
from agent_urp.core.equivalence import Level
from agent_urp.core.models import (
    Artifact,
    Block,
    Decision,
    Durability,
    Edit,
    Policy,
    SamplingIntent,
    StepKind,
)
from agent_urp.core.runtime import (
    EnvMutatedInStep,
    NotInStep,
    Runtime,
    UnknownBlock,
    UnknownEnv,
    step,
)
from agent_urp.core.trace_store import TraceStore
from agent_urp.llm.scripted import ScriptedLLM
from agent_urp.tools.env import VersionedEnv


def _summarize_rule(prompt, m):
    extra = prompt.split("[input]\n", 1)[1]
    return f"SUMMARY: {extra.strip()}" + ("  " if "verbose" in prompt else "")


@step(kind=StepKind.TOOL)
def fetch(ctx, key: str):
    return ctx.env("kv").get(key)


@step(kind=StepKind.LLM)
def summarize(ctx, data: Artifact):
    return ctx.llm(["system", "style"], extra=str(data.content))


@step(kind=StepKind.TOOL)
def count(ctx, data: Artifact):
    return len(str(data.content))


@step(kind=StepKind.TOOL)
def polish(ctx, s: Artifact):
    return s.content.strip().upper()


def program(ctx):
    d = fetch(ctx, key="doc")
    s = summarize(ctx, data=d)
    c = count(ctx, data=d)
    p = polish(ctx, s=s)
    return {"summary": p.content, "count": c.content}


def _blocks(style="terse"):
    return [Block.of("system", "You summarize.", durability=Durability.HIGH),
            Block.of("style", style, durability=Durability.LOW),
            Block.of("unused", "nobody reads me")]


def _env():
    return VersionedEnv("kv", {"doc": "hello world"})


def _runtime(level=Level.L0):
    return Runtime(TraceStore(), ScriptedLLM([(r".*", _summarize_rule)]),
                   ContextAssembler("naive"), level)


def _names(result, decision=None):
    return [r.name for r in result.steps if decision is None or r.decision == decision]


def test_first_run_records_everything_as_live():
    rt = _runtime()
    res = rt.run(program, _blocks(), [_env()])
    assert res.output == {"summary": "SUMMARY: HELLO WORLD", "count": 11}
    assert _names(res) == ["fetch", "summarize", "count", "polish"]
    assert all(r.decision == Decision.LIVE for r in res.steps)
    fetch_rec, sum_rec = res.steps[0], res.steps[1]
    assert [r.kind for r in fetch_rec.reads] == ["env"] and fetch_rec.tool_calls == 1
    assert {(r.kind, r.name) for r in sum_rec.reads} == {("artifact", fetch_rec.writes[-1].name),
                                                          ("block", "system"), ("block", "style")}
    assert sum_rec.llm_calls == 1 and sum_rec.usage.input_tokens > 0
    assert res.metrics["llm_calls"] == 1 and res.metrics["tool_calls"] == 3
    assert rt.store.get_run(res.run.id).initial_blocks["style"] == _blocks()[1].version


def test_replay_policies_on_style_edit():
    rt = _runtime()
    base = rt.run(program, _blocks(), [_env()])
    edit = Edit.of("constraint", "style", "block", "verbose")
    dep = rt.replay(program, base.run.id, edit, Policy.DEP)
    assert _names(dep, Decision.REUSE) == ["fetch", "count"]
    assert _names(dep, Decision.RERUN) == ["summarize", "polish"]
    assert dep.run.parent_run_id == base.run.id and dep.run.edit_id == edit.id
    suffix = rt.replay(program, base.run.id, edit, Policy.SUFFIX)
    assert _names(suffix, Decision.REUSE) == ["fetch"]
    memo = rt.replay(program, base.run.id, edit, Policy.MEMO)
    assert _names(memo, Decision.REUSE) == []
    full = rt.replay(program, base.run.id, edit, Policy.FULL)
    assert _names(full, Decision.REUSE) == [] and full.output == dep.output == suffix.output
    assert rt.store.get_edit(edit.id).old_version == _blocks()[1].version


def test_l1_backdating_stops_propagation():
    rt = _runtime(Level.L1)
    base = rt.run(program, _blocks(), [_env()])
    edit = Edit.of("constraint", "style", "block", "verbose")
    dep = rt.replay(program, base.run.id, edit, Policy.DEP)
    assert _names(dep, Decision.RERUN) == ["summarize"]
    assert _names(dep, Decision.REUSE) == ["fetch", "count", "polish"]
    assert dep.steps[1].equivalent_to == base.steps[1].id
    rt0 = _runtime(Level.L0)
    base0 = rt0.run(program, _blocks(), [_env()])
    assert _names(rt0.replay(program, base0.run.id, edit, Policy.DEP), Decision.RERUN) == \
        ["summarize", "polish"]


def test_undo_edit_reuses_everything():
    rt = _runtime()
    base = rt.run(program, _blocks(), [_env()])
    e1 = Edit.of("constraint", "style", "block", "verbose")
    mid = rt.replay(program, base.run.id, e1, Policy.DEP)
    back = rt.replay(program, mid.run.id, Edit.of("constraint", "style", "block", "terse"),
                     Policy.DEP)
    assert _names(back, Decision.REUSE) == ["fetch", "summarize", "count", "polish"]
    assert back.output == base.output


def test_env_edit_invalidates_tool_readers():
    rt = _runtime()
    base = rt.run(program, _blocks(), [_env()])
    dep = rt.replay(program, base.run.id, Edit.of("tool_result", "kv", "env", {"doc": "bye"}),
                    Policy.DEP)
    assert _names(dep, Decision.RERUN) == ["fetch", "summarize", "count", "polish"]
    assert dep.output["summary"] == "SUMMARY: BYE"


def test_suffix_target_never_read():
    rt = _runtime()
    base = rt.run(program, _blocks(), [_env()])
    edit = Edit.of("system", "unused", "block", "still unread")
    assert _names(rt.replay(program, base.run.id, edit, Policy.SUFFIX), Decision.REUSE) == \
        ["fetch", "summarize", "count", "polish"]
    assert _names(rt.replay(program, base.run.id, edit, Policy.DEP), Decision.REUSE) == \
        ["fetch", "summarize", "count", "polish"]


def test_unknown_block_edit_raises():
    rt = _runtime()
    base = rt.run(program, _blocks(), [_env()])
    with pytest.raises(UnknownBlock):
        rt.replay(program, base.run.id, Edit.of("constraint", "nope", "block", "x"), Policy.DEP)


def test_same_step_twice_tracks_occurrence():
    def prog(ctx):
        a = fetch(ctx, key="doc")
        b = fetch(ctx, key="other")
        return [a.content, b.content]
    rt = _runtime()
    base = rt.run(prog, _blocks(), [VersionedEnv("kv", {"doc": "x", "other": "y"})])
    assert [(r.name, r.occurrence) for r in base.steps] == [("fetch", 0), ("fetch", 1)]
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "style", "block", "v"), Policy.DEP)
    assert _names(dep, Decision.REUSE) == ["fetch", "fetch"] and dep.output == ["x", "y"]


def test_fresh_sampling_intent_never_reuses():
    @step(kind=StepKind.LLM, sampling_intent=SamplingIntent.FRESH)
    def sample(ctx):
        return ctx.llm(["system"], extra="draw")

    def prog(ctx):
        return sample(ctx).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "unused", "block", "z"), Policy.DEP)
    assert _names(dep, Decision.RERUN) == ["sample"]


def test_control_flow_divergence_is_live_and_memo_reuses_moved_step():
    def prog(ctx):
        if ctx.block("style") == "skip":
            return count(ctx, data=fetch(ctx, key="doc")).content
        d = fetch(ctx, key="doc")
        summarize(ctx, data=d)
        return count(ctx, data=d).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "style", "block", "skip"), Policy.DEP)
    assert [(r.name, r.decision) for r in dep.steps] == \
        [("fetch", Decision.REUSE), ("count", Decision.REUSE)]


def test_llm_outside_step_raises_and_non_json_return_raises():
    rt = _runtime()
    with pytest.raises(NotInStep):
        rt.run(lambda ctx: ctx.llm(["system"]), _blocks(), [_env()])

    @step(kind=StepKind.TOOL)
    def bad(ctx):
        return {1, 2}
    with pytest.raises(TypeError):
        rt.run(lambda ctx: bad(ctx), _blocks(), [_env()])


def test_set_block_records_write_and_is_restored_on_reuse():
    @step(kind=StepKind.MEMORY)
    def remember(ctx):
        ctx.set_block("memory.note", "seen " + str(ctx.env("kv").get("doc")))
        return "ok"

    @step(kind=StepKind.LLM)
    def use_note(ctx):
        return ctx.llm(["memory.note"], extra="x")

    def prog(ctx):
        remember(ctx)
        return use_note(ctx).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    assert base.steps[0].writes[0].kind == "block" and base.steps[0].writes[0].name == "memory.note"
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "unused", "block", "z"), Policy.DEP)
    assert _names(dep, Decision.REUSE) == ["remember", "use_note"] and dep.output == base.output


def test_swapped_artifact_args_rerun_instead_of_stale_reuse():
    @step(kind=StepKind.TOOL)
    def combine(ctx, a: Artifact, b: Artifact):
        return f"{a.content}|{b.content}"

    def prog(ctx):
        return combine(ctx, a=fetch(ctx, key="x"), b=fetch(ctx, key="y")).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [VersionedEnv("kv", {"x": "1", "y": "2"})])
    assert base.output == "1|2"
    swap = Edit.of("tool_result", "kv", "env", {"x": "2", "y": "1"})
    dep = rt.replay(prog, base.run.id, swap, Policy.DEP)
    full = rt.replay(prog, base.run.id, swap, Policy.FULL)
    assert dep.output == full.output == "2|1"
    assert _names(dep, Decision.RERUN) == ["fetch", "fetch", "combine"]


def test_reading_back_own_block_write_is_not_a_read():
    @step(kind=StepKind.MEMORY)
    def jot(ctx):
        ctx.set_block("memory.note", "jotted")
        return ctx.block("memory.note")

    def prog(ctx):
        return jot(ctx).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    assert base.output == "jotted" and base.steps[0].reads == []
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "unused", "block", "z"), Policy.DEP)
    assert _names(dep, Decision.REUSE) == ["jot"] and dep.output == base.output


def test_nested_step_raises():
    @step(kind=StepKind.TOOL)
    def outer(ctx):
        return fetch(ctx, key="doc").content

    rt = _runtime()
    with pytest.raises(NotInStep):
        rt.run(lambda ctx: outer(ctx), _blocks(), [_env()])


def test_unknown_env_raises():
    rt = _runtime()
    with pytest.raises(UnknownEnv):
        rt.run(lambda ctx: ctx.env("missing"), _blocks(), [_env()])
    base = rt.run(program, _blocks(), [_env()])
    with pytest.raises(UnknownEnv):
        rt.replay(program, base.run.id, Edit.of("tool_result", "nope", "env", {"a": 1}), Policy.DEP)


def test_sibling_replays_do_not_share_memo():
    rt = _runtime()
    base = rt.run(program, _blocks(), [_env()])
    edit = Edit.of("constraint", "style", "block", "verbose")
    for policy in (Policy.DEP, Policy.MEMO):
        first = rt.replay(program, base.run.id, edit, policy)
        second = rt.replay(program, base.run.id, edit, policy)
        decisions = [(r.name, r.decision) for r in first.steps]
        assert Decision.RERUN in {d for _, d in decisions}
        assert [(r.name, r.decision) for r in second.steps] == decisions


def test_tuple_result_is_canonical_in_both_paths():
    @step(kind=StepKind.TOOL)
    def pair(ctx):
        return (1, 2)

    @step(kind=StepKind.TOOL)
    def show(ctx, p: Artifact):
        return f"{ctx.block('style')}:{p.content!r}"

    def prog(ctx):
        return show(ctx, p=pair(ctx)).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    edit = Edit.of("constraint", "style", "block", "loud")  # unrelated to pair: only show reads it
    dep = rt.replay(prog, base.run.id, edit, Policy.DEP)
    full = rt.replay(prog, base.run.id, edit, Policy.FULL)
    assert _names(dep, Decision.REUSE) == ["pair"] and _names(dep, Decision.RERUN) == ["show"]
    assert dep.output == full.output == "loud:[1, 2]"


def test_pydantic_model_result_is_a_dict_in_both_paths():
    class Point(BaseModel):
        x: int
        y: int

    @step(kind=StepKind.TOOL)
    def origin(ctx):
        return Point(x=0, y=0)

    def prog(ctx):
        return origin(ctx).content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "unused", "block", "z"), Policy.DEP)
    assert _names(dep, Decision.REUSE) == ["origin"]
    assert type(base.output) is dict and type(dep.output) is dict
    assert base.output == dep.output == {"x": 0, "y": 0}


def test_set_block_stores_a_copy():
    @step(kind=StepKind.MEMORY)
    def keep(ctx):
        notes = ["a"]
        ctx.set_block("memory.notes", notes)
        notes.append("b")
        return ctx.block("memory.notes")

    rt = _runtime()
    assert rt.run(lambda ctx: keep(ctx).content, _blocks(), [_env()]).output == ["a"]


def test_run_inputs_are_canonical_so_base_matches_replay():
    @step(kind=StepKind.TOOL)
    def show(ctx):
        return f"{ctx.block('pair')!r} {ctx.env('kv').get('pair')!r}"

    def prog(ctx):
        return show(ctx).content
    rt = _runtime()
    base = rt.run(prog, _blocks() + [Block.of("pair", (1, 2))],
                  [VersionedEnv("kv", {"pair": (3, 4)})])
    edit = Edit.of("constraint", "unused", "block", "z")
    dep = rt.replay(prog, base.run.id, edit, Policy.DEP)
    full = rt.replay(prog, base.run.id, edit, Policy.FULL)
    assert _names(dep, Decision.REUSE) == ["show"]
    assert dep.output == full.output == "[1, 2] [3, 4]"


def test_suffix_sees_orchestration_reads():
    def prog(ctx):
        return fetch(ctx, key=ctx.block("which")).content
    rt = _runtime()
    base = rt.run(prog, _blocks() + [Block.of("which", "doc")],
                  [VersionedEnv("kv", {"doc": "x", "other": "y"})])
    assert [(r.kind, r.name) for r in base.steps[0].orchestration_reads] == [("block", "which")]
    edit = Edit.of("constraint", "which", "block", "other")
    suffix = rt.replay(prog, base.run.id, edit, Policy.SUFFIX)
    full = rt.replay(prog, base.run.id, edit, Policy.FULL)
    assert suffix.output == full.output == "y"
    assert _names(suffix, Decision.RERUN) == ["fetch"]


def test_dep_ignores_orchestration_reads_and_reuse_records_current_ones():
    def prog(ctx):
        ctx.block("style")
        return fetch(ctx, key="doc").content
    rt = _runtime()
    base = rt.run(prog, _blocks(), [_env()])
    dep = rt.replay(prog, base.run.id, Edit.of("constraint", "style", "block", "verbose"),
                    Policy.DEP)
    assert _names(dep, Decision.REUSE) == ["fetch"]
    assert [r.version for r in dep.steps[0].orchestration_reads] == \
        [Block.of("style", "verbose").version]


def test_read_before_own_write_is_still_a_read():
    @step(kind=StepKind.MEMORY)
    def restyle(ctx):
        before = ctx.block("style")
        ctx.set_block("style", before + "!")
        return ctx.block("style")

    rt = _runtime()
    res = rt.run(lambda ctx: restyle(ctx).content, _blocks(), [_env()])
    assert res.output == "terse!"
    assert [(r.kind, r.name, r.version) for r in res.steps[0].reads] == \
        [("block", "style", _blocks()[1].version)]


def test_set_block_outside_step_raises():
    rt = _runtime()
    with pytest.raises(NotInStep):
        rt.run(lambda ctx: ctx.set_block("memory.note", "x"), _blocks(), [_env()])


def test_backdating_only_under_dep():
    rt = _runtime(Level.L1)
    base = rt.run(program, _blocks(), [_env()])
    edit = Edit.of("constraint", "style", "block", "verbose")
    for policy in (Policy.SUFFIX, Policy.MEMO, Policy.FULL):
        res = rt.replay(program, base.run.id, edit, policy)
        assert all(r.equivalent_to is None for r in res.steps)
        assert "polish" in _names(res, Decision.RERUN)


def test_env_mutation_inside_step_raises():
    @step(kind=StepKind.TOOL)
    def poke(ctx):
        ctx.env("kv").set("doc", "changed")
        return "ok"

    rt = _runtime()
    with pytest.raises(EnvMutatedInStep, match=r"poke.*kv"):
        rt.run(lambda ctx: poke(ctx), _blocks(), [_env()])
