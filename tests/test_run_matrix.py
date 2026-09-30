from agent_urp.core.models import Policy
from agent_urp.eval.run_matrix import format_table, main, run_scenario
from agent_urp.eval.scenarios import SCENARIOS


def _by_policy(rows):
    return {r["policy"]: r for r in rows}


def test_s1_matrix_matches_spec_expectations():
    rows = _by_policy(run_scenario(SCENARIOS["S1"](), list(Policy)))
    assert rows["full"]["executed"] == 5 and rows["memo"]["executed"] == 5
    assert rows["suffix"]["executed"] == 3 and rows["dep"]["executed"] == 2
    assert all(r["matches_full"] and r["stale_reuse"] == [] for r in rows.values())
    assert rows["suffix"]["over_rerun"] == ["get_weather"] and rows["dep"]["over_rerun"] == []
    assert rows["dep"]["llm_calls"] == 2 and rows["dep"]["tool_calls"] == 0


def test_s5_noop_dep_reruns_one_step():
    rows = _by_policy(run_scenario(SCENARIOS["S5"](), [Policy.SUFFIX, Policy.DEP]))
    assert rows["dep"]["executed"] == 1 and rows["dep"]["over_rerun"] == []
    assert rows["suffix"]["over_rerun"] == ["compose_plan", "get_weather"]
    assert all(r["matches_full"] for r in rows.values())


def test_cli_prints_table(capsys):
    assert main(["--scenarios", "S1", "--policies", "full,dep"]) == 0
    out = capsys.readouterr().out
    assert "S1" in out and "dep" in out and "executed" in out
    assert "policy" in format_table([{"policy": "dep", "executed": 2}])
