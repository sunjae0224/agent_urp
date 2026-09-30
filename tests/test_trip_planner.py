from agent_urp.core.models import Decision, Edit, Policy
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
