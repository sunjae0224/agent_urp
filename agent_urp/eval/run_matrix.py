"""CLI: run each scenario once, then replay its edit under every policy and print a
comparison table.
Usage: uv run python -m agent_urp.eval.run_matrix --scenarios S1,S5
       --policies full,suffix,memo,dep [--level 0|1] [--layout naive|stable_prefix] [--db PATH]"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from agent_urp.core.context import LAYOUTS, ContextAssembler
from agent_urp.core.equivalence import Level
from agent_urp.core.models import Policy
from agent_urp.core.runtime import Runtime
from agent_urp.core.trace_store import TraceStore
from agent_urp.eval.metrics import audit, summarize
from agent_urp.eval.scenarios import SCENARIOS, Scenario

COLUMNS = ["scenario", "policy", "executed", "reused", "llm_calls", "tool_calls", "input_tokens",
           "output_tokens", "stale_reuse", "over_rerun", "matches_full"]


def run_scenario(scenario: Scenario, policies: Sequence[Policy], level: Level = Level.L0,
                 layout: str = "naive", db_path: str = ":memory:") -> list[dict[str, Any]]:
    rt = Runtime(TraceStore(db_path), scenario.llm_factory(), ContextAssembler(layout), level)
    base = rt.run(scenario.program, scenario.blocks, scenario.envs, Policy.FULL)
    oracle = rt.replay(scenario.program, base.run.id, scenario.edit, Policy.FULL)
    rows = []
    for policy in policies:
        res = oracle if policy == Policy.FULL else rt.replay(scenario.program, base.run.id,
                                                             scenario.edit, policy)
        rows.append({"scenario": scenario.id, "policy": policy.value, **summarize(res),
                     **audit(res, scenario, oracle, level)})
    return rows


def format_table(rows: Sequence[dict[str, Any]]) -> str:
    cols = [c for c in COLUMNS if any(c in r for r in rows)]
    cells = [[str(r.get(c, "")) for c in cols] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    line = " | ".join(c.ljust(w) for c, w in zip(cols, widths, strict=True))
    sep = "-+-".join("-" * w for w in widths)
    body = [" | ".join(v.ljust(w) for v, w in zip(row, widths, strict=True)) for row in cells]
    return "\n".join([line, sep, *body])


def _name_list(valid: Sequence[str]) -> Callable[[str], list[str]]:
    """argparse type: comma-separated names, each one of `valid`."""
    def parse(text: str) -> list[str]:
        names = text.split(",")
        unknown = [n for n in names if n not in valid]
        if unknown:
            raise argparse.ArgumentTypeError(
                f"unknown {', '.join(unknown)} (valid: {', '.join(valid)})")
        return names
    return parse


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenarios", type=_name_list(list(SCENARIOS)), default=",".join(SCENARIOS))
    ap.add_argument("--policies", type=_name_list([p.value for p in Policy]),
                    default=",".join(p.value for p in Policy))
    ap.add_argument("--level", type=int, default=0, choices=[lv.value for lv in Level])
    ap.add_argument("--layout", default="naive", choices=LAYOUTS)
    ap.add_argument("--db", default=":memory:")
    ns = ap.parse_args(argv)
    if ns.db != ":memory:":
        Path(ns.db).parent.mkdir(parents=True, exist_ok=True)
    policies = [Policy(p) for p in ns.policies]
    rows: list[dict[str, Any]] = []
    for sid in ns.scenarios:
        rows += run_scenario(SCENARIOS[sid](), policies, Level(ns.level), ns.layout, ns.db)
    print(format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
