import re

from agent_urp.llm.base import LLMBackend, LLMResponse
from agent_urp.llm.scripted import ScriptedLLM


def test_first_matching_rule_wins_and_usage_counts_words():
    llm = ScriptedLLM([
        (r"budget", "BUDGET RULE"),
        (re.compile(r"hotel", re.I), lambda prompt, m: f"HOTEL:{m.group(0)}"),
    ], default="DEFAULT")
    assert llm.complete("pick a Hotel").text == "HOTEL:Hotel"
    assert llm.complete("my budget hotel").text == "BUDGET RULE"
    r = llm.complete("nothing here")
    assert r.text == "DEFAULT" and r.usage.input_tokens == 2 and r.usage.output_tokens == 1
    assert llm.calls == ["pick a Hotel", "my budget hotel", "nothing here"]
    assert isinstance(llm, LLMBackend) and llm.name == "scripted"
    assert isinstance(r, LLMResponse)
