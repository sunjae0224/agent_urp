"""S1 workload: 5-step trip planner with a budget constraint (spec §8.1).
Step order is chosen so that get_weather (budget-independent) comes AFTER pick_hotel:
SUFFIX must rerun it, DEP reuses it."""
from __future__ import annotations

import json
import re

from agent_urp.core.models import Artifact, Block, BlockKind, Durability, StepKind
from agent_urp.core.runtime import StepContext, step
from agent_urp.llm.scripted import ScriptedLLM
from agent_urp.tools.db import db_query
from agent_urp.tools.env import VersionedEnv


def blocks() -> list[Block]:
    return [
        Block.of("system",
                 "You are a travel planning assistant. Answer in the exact format requested.",
                 kind=BlockKind.STATIC, durability=Durability.HIGH),
        Block.of("goal", {"city": "Jeju", "nights": 2}, kind=BlockKind.USER,
                 durability=Durability.MEDIUM),
        Block.of("constraint.budget", "Total budget: at most 2000 USD", kind=BlockKind.USER,
                 durability=Durability.LOW),
        Block.of("memory.prefs", "User prefers hotels on the beach; dislikes hostels.",
                 kind=BlockKind.MEMORY, durability=Durability.MEDIUM),
    ]


def env() -> VersionedEnv:
    return VersionedEnv("travel", {
        "tables": {
            "flights": [
                {"city": "Jeju", "airline": "Jin Air", "price": 180},
                {"city": "Jeju", "airline": "Korean Air", "price": 260},
                {"city": "Busan", "airline": "Jin Air", "price": 90},
            ],
            "hotels": [
                {"city": "Jeju", "name": "Ocean Grand", "price_per_night": 700, "beach": True},
                {"city": "Jeju", "name": "Seaside Suites", "price_per_night": 260, "beach": True},
                {"city": "Jeju", "name": "Harbor Inn", "price_per_night": 150, "beach": True},
                {"city": "Jeju", "name": "City Hostel", "price_per_night": 40, "beach": False},
                {"city": "Busan", "name": "Bay View", "price_per_night": 200, "beach": True},
            ],
        },
        "weather": {"Jeju": "sunny, 24C", "Busan": "cloudy, 21C"},
    })


@step(kind=StepKind.TOOL)
def search_flights(ctx: StepContext, city: str) -> list[dict]:
    flights = sorted(db_query(ctx.env("travel"), "flights", {"city": city}),
                     key=lambda f: f["price"])
    if not flights:  # later steps quote the cheapest flight
        raise ValueError(f"no flights for {city}")
    return flights


@step(kind=StepKind.TOOL)
def search_hotels(ctx: StepContext, city: str) -> list[dict]:
    return db_query(ctx.env("travel"), "hotels", {"city": city})


@step(kind=StepKind.LLM)
def pick_hotel(ctx: StepContext, hotels: Artifact, flights: Artifact) -> str:
    extra = json.dumps({"task": "pick_hotel", "hotels": hotels.content,
                        "flight_price": flights.content[0]["price"],
                        "nights": ctx.block("goal")["nights"]}, sort_keys=True)
    return ctx.llm(["system", "constraint.budget", "memory.prefs"], extra=extra)


@step(kind=StepKind.TOOL)
def get_weather(ctx: StepContext, city: str) -> str:
    return ctx.env("travel").get(f"weather.{city}", "unknown")


@step(kind=StepKind.LLM)
def compose_plan(ctx: StepContext, flights: Artifact, hotel: Artifact, weather: Artifact) -> str:
    extra = json.dumps({"task": "compose_plan", "airline": flights.content[0]["airline"],
                        "flight_price": flights.content[0]["price"],
                        "hotel": hotel.content.removeprefix("HOTEL: "),
                        "weather": weather.content}, sort_keys=True)
    return ctx.llm(["system", "goal"], extra=extra)


def program(ctx: StepContext) -> Artifact:
    city = ctx.block("goal")["city"]
    flights = search_flights(ctx, city=city)
    hotels = search_hotels(ctx, city=city)
    hotel = pick_hotel(ctx, hotels=hotels, flights=flights)
    weather = get_weather(ctx, city=city)
    return compose_plan(ctx, flights=flights, hotel=hotel, weather=weather)


_BUDGET = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{3,6})\s*USD")  # 2000 USD or 1,200 USD


def _budget(prompt: str) -> int:
    m = _BUDGET.search(prompt)
    if m is None:
        raise ValueError("no budget in prompt")
    return int(m.group(1).replace(",", ""))


def _extra(prompt: str) -> dict:
    _, found, data = prompt.partition("[input]\n")
    if not found:
        raise ValueError("no [input] block in prompt")
    return json.loads(data)


def _pick_hotel(prompt: str, m: re.Match[str] | None) -> str:
    budget = _budget(prompt)
    data = _extra(prompt)
    best = None
    for h in data["hotels"]:
        total = data["flight_price"] + h["price_per_night"] * data["nights"]
        if (h["beach"] and total <= budget
                and (best is None or h["price_per_night"] > best["price_per_night"])):
            best = h
    return f"HOTEL: {best['name'] if best else 'NONE'}"


def _compose_plan(prompt: str, m: re.Match[str] | None) -> str:
    d = _extra(prompt)
    return (f"PLAN: fly {d['airline']} (${d['flight_price']}), stay at {d['hotel']}, "
            f"weather {d['weather']}")


def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM([
        (r'"task": "pick_hotel"', _pick_hotel),
        (r'"task": "compose_plan"', _compose_plan),
    ])
