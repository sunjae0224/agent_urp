import pytest

from agent_urp.core.models import Block, Decision, Edit, Policy
from agent_urp.core.runtime import Runtime
from agent_urp.core.trace_store import TraceStore
from agent_urp.workloads import trip_planner as tp


def _names(res, decision):
    return [r.name for r in res.steps if r.decision == decision]


def test_base_run_picks_most_expensive_beach_hotel_within_budget():
    rt = Runtime(TraceStore(), tp.scripted_llm())
    res = rt.run(tp.program, tp.blocks(), [tp.env()])
    assert [r.name for r in res.steps] == ["search_flights", "search_hotels", "pick_hotel",
                                           "get_weather", "compose_plan"]
    expected = "PLAN: fly Jin Air ($180), stay at Ocean Grand, weather sunny, 24C"
    assert res.output.content == expected
    assert res.metrics["llm_calls"] == 2 and res.metrics["tool_calls"] == 3


def test_budget_edit_dep_reruns_only_dependents():
    rt = Runtime(TraceStore(), tp.scripted_llm())
    base = rt.run(tp.program, tp.blocks(), [tp.env()])
    edit = Edit.of("constraint", "constraint.budget", "block", "Total budget: at most 1200 USD")
    dep = rt.replay(tp.program, base.run.id, edit, Policy.DEP)
    assert _names(dep, Decision.RERUN) == ["pick_hotel", "compose_plan"]
    expected = "PLAN: fly Jin Air ($180), stay at Seaside Suites, weather sunny, 24C"
    assert dep.output.content == expected
    suffix = rt.replay(tp.program, base.run.id, edit, Policy.SUFFIX)
    assert _names(suffix, Decision.RERUN) == ["pick_hotel", "get_weather", "compose_plan"]
    assert suffix.output.content == dep.output.content


def test_noop_rephrase_cuts_off_after_pick_hotel():
    rt = Runtime(TraceStore(), tp.scripted_llm())
    base = rt.run(tp.program, tp.blocks(), [tp.env()])
    edit = Edit.of("constraint", "constraint.budget", "block", "Budget cap is 2000 USD in total")
    dep = rt.replay(tp.program, base.run.id, edit, Policy.DEP)
    assert _names(dep, Decision.RERUN) == ["pick_hotel"]
    assert dep.output.content == base.output.content


def _with_budget(text):
    return [Block.of(b.name, text, kind=b.kind, durability=b.durability)
            if b.name == "constraint.budget" else b for b in tp.blocks()]


def test_budget_with_thousands_separator_is_parsed():
    rt = Runtime(TraceStore(), tp.scripted_llm())
    res = rt.run(tp.program, _with_budget("Total budget: at most 1,200 USD"), [tp.env()])
    assert "stay at Seaside Suites" in res.output.content


def test_responders_fail_loudly_on_malformed_prompts():
    rt = Runtime(TraceStore(), tp.scripted_llm())
    with pytest.raises(ValueError, match="no budget in prompt"):
        rt.run(tp.program, _with_budget("Spend whatever it takes"), [tp.env()])
    with pytest.raises(ValueError, match=r"\[input\]"):
        tp.scripted_llm().complete('"task": "compose_plan" without an input block')


def test_no_flights_for_the_city_fails_loudly():
    env = tp.env()
    env.set("tables.flights", [f for f in env.get("tables.flights") if f["city"] != "Jeju"])
    with pytest.raises(ValueError, match="no flights for Jeju"):
        Runtime(TraceStore(), tp.scripted_llm()).run(tp.program, tp.blocks(), [env])
