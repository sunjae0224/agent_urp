"""Per-run summary and stale-reuse / over-rerun audit against a scenario's ground truth."""
from __future__ import annotations

from typing import Any

from agent_urp.core.models import Artifact, Decision
from agent_urp.core.runtime import RunResult
from agent_urp.eval.scenarios import Scenario


def _content(output: Any) -> Any:
    return output.content if isinstance(output, Artifact) else output


def summarize(result: RunResult) -> dict[str, Any]:
    m = result.metrics
    return {"executed": len(m["executed"]), "reused": len(m["reused"]), "llm_calls": m["llm_calls"],
            "tool_calls": m["tool_calls"], "input_tokens": m["input_tokens"],
            "output_tokens": m["output_tokens"]}


def audit(result: RunResult, scenario: Scenario, oracle: RunResult) -> dict[str, Any]:
    executed = {r.name for r in result.steps if r.decision != Decision.REUSE}
    reused = {r.name for r in result.steps if r.decision == Decision.REUSE}
    return {"stale_reuse": sorted(scenario.must_rerun & reused),
            "over_rerun": sorted(scenario.must_not_rerun & executed),
            "matches_full": _content(result.output) == _content(oracle.output)}
