"""Perturbation scenarios: a workload + one edit + ground-truth sets of steps that
must / must not rerun."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from agent_urp.core.models import Block, Edit
from agent_urp.core.runtime import Program
from agent_urp.llm.base import LLMBackend
from agent_urp.tools.env import VersionedEnv
from agent_urp.workloads import trip_planner as tp


@dataclass
class Scenario:
    id: str
    description: str
    program: Program
    blocks: list[Block]
    envs: list[VersionedEnv]
    edit: Edit
    must_rerun: set[str] = field(default_factory=set)      # G: reusing any of these is stale reuse
    # controls: executing any of these is waste
    must_not_rerun: set[str] = field(default_factory=set)
    llm_factory: Callable[[], LLMBackend] = tp.scripted_llm


def S1_budget_edit() -> Scenario:
    return Scenario(
        id="S1", description="trip planner, budget 2000 -> 1200 USD", program=tp.program,
        blocks=tp.blocks(), envs=[tp.env()],
        edit=Edit.of("constraint", "constraint.budget", "block", "Total budget: at most 1200 USD"),
        must_rerun={"pick_hotel", "compose_plan"},
        must_not_rerun={"search_flights", "search_hotels", "get_weather"})


def S5_noop_edit() -> Scenario:
    return Scenario(
        id="S5", description="trip planner, budget rephrased with same meaning", program=tp.program,
        blocks=tp.blocks(), envs=[tp.env()],
        edit=Edit.of("constraint", "constraint.budget", "block", "Budget cap is 2000 USD in total"),
        must_rerun={"pick_hotel"},
        must_not_rerun={"search_flights", "search_hotels", "get_weather", "compose_plan"})


SCENARIOS: dict[str, Callable[[], Scenario]] = {"S1": S1_budget_edit, "S5": S5_noop_edit}
