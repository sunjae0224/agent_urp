from agent_urp.core.equivalence import Level
from agent_urp.core.models import Block, Edit, Policy, StepKind
from agent_urp.core.runtime import Runtime, step
from agent_urp.core.trace_store import TraceStore
from agent_urp.eval.metrics import audit
from agent_urp.eval.scenarios import Scenario
from agent_urp.llm.scripted import ScriptedLLM
from agent_urp.tools.env import VersionedEnv


@step(kind=StepKind.TOOL)
def fetch(ctx, key: str):
    return ctx.env("kv").get(key)


@step(kind=StepKind.LLM)
def say(ctx):
    return ctx.llm(["style"])


def _runtime(level=Level.L0):  # verbose style -> same words, extra whitespace
    return Runtime(TraceStore(), ScriptedLLM([("verbose", "Hello  world")], default="Hello world"),
                   level=level)


def _scenario(program, edit):
    return Scenario(id="T", description="unit", program=program, blocks=[], envs=[], edit=edit)


def test_artifacts_inside_containers_are_compared_by_content():
    def prog(ctx):
        art = fetch(ctx, key="doc")
        return {"a": art, "b": [art]}
    rt = _runtime()
    base = rt.run(prog, [Block.of("style", "terse")], [VersionedEnv("kv", {"doc": "hi"})])
    edit = Edit.of("constraint", "style", "block", "verbose")
    oracle = rt.replay(prog, base.run.id, edit, Policy.FULL)
    dep = rt.replay(prog, base.run.id, edit, Policy.DEP)
    assert dep.output != oracle.output  # same content, different producer (created_by)
    assert audit(dep, _scenario(prog, edit), oracle)["matches_full"] is True


def test_matches_full_compares_at_the_given_level():
    def prog(ctx):
        return say(ctx)
    rt = _runtime(Level.L1)
    base = rt.run(prog, [Block.of("style", "terse")], [])
    edit = Edit.of("constraint", "style", "block", "verbose")
    oracle = rt.replay(prog, base.run.id, edit, Policy.FULL)
    dep = rt.replay(prog, base.run.id, edit, Policy.DEP)  # L1 backdating keeps the old text
    assert (dep.output.content, oracle.output.content) == ("Hello world", "Hello  world")
    assert audit(dep, _scenario(prog, edit), oracle)["matches_full"] is False
    assert audit(dep, _scenario(prog, edit), oracle, Level.L1)["matches_full"] is True
