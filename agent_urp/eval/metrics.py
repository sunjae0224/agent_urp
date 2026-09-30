"""Per-run summary and stale-reuse / over-rerun audit against a scenario's ground truth."""
from __future__ import annotations

from typing import Any

from agent_urp.core.equivalence import Level, equivalent
from agent_urp.core.models import Artifact, Decision
from agent_urp.core.runtime import RunResult
from agent_urp.eval.scenarios import Scenario


def _content(output: Any) -> Any:
    """Output with every Artifact (also inside dicts/lists/tuples) replaced by its content:
    created_by differs between runs even when the content is the same."""
    if isinstance(output, Artifact):
        return output.content
    if isinstance(output, dict):
        return {k: _content(v) for k, v in output.items()}
    if isinstance(output, (list, tuple)):
        return [_content(v) for v in output]
    return output


def summarize(result: RunResult) -> dict[str, Any]:
    m = result.metrics
    return {"executed": len(m["executed"]), "reused": len(m["reused"]), "llm_calls": m["llm_calls"],
            "tool_calls": m["tool_calls"], "input_tokens": m["input_tokens"],
            "output_tokens": m["output_tokens"]}


def audit(result: RunResult, scenario: Scenario, oracle: RunResult,
          level: Level = Level.L0) -> dict[str, Any]:
    executed = {r.name for r in result.steps if r.decision != Decision.REUSE}
    reused = {r.name for r in result.steps if r.decision == Decision.REUSE}
    # compared at the run's equivalence level: L1 backdating may keep an L1-equal old output
    same = equivalent(Artifact.of("out", _content(result.output)),
                      Artifact.of("out", _content(oracle.output)), level)
    return {"stale_reuse": sorted(scenario.must_rerun & reused),
            "over_rerun": sorted(scenario.must_not_rerun & executed),
            "matches_full": same}
