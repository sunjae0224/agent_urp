import json
import os

import pytest

from agent_urp.llm.cassette import CassetteLLM, CassetteMiss
from agent_urp.llm.scripted import ScriptedLLM


def test_auto_records_then_replays_without_calling_inner(tmp_path):
    inner = ScriptedLLM([(r"hi", "HELLO")])
    c = CassetteLLM(tmp_path / "c.json", inner=inner)
    assert c.complete("hi there").text == "HELLO"
    assert c.complete("hi there").text == "HELLO"
    assert inner.calls == ["hi there"] and (c.hits, c.misses) == (1, 1)
    assert c.complete("hi there", params={"temperature": 1}).text == "HELLO"  # different key
    assert len(inner.calls) == 2


def test_persisted_and_reloaded(tmp_path):
    p = tmp_path / "c.json"
    CassetteLLM(p, inner=ScriptedLLM([(r".*", "X")])).complete("q")
    replay = CassetteLLM(p, mode="replay")
    assert replay.complete("q").text == "X" and replay.name == "cassette(scripted)"


def test_replay_mode_miss_raises(tmp_path):
    inner = ScriptedLLM([(r".*", "X")])
    c = CassetteLLM(tmp_path / "c.json", inner=inner, mode="replay")
    with pytest.raises(CassetteMiss):
        c.complete("never recorded")
    assert inner.calls == []


def test_record_mode_always_calls_inner(tmp_path):
    inner = ScriptedLLM([(r".*", "X")])
    c = CassetteLLM(tmp_path / "c.json", inner=inner, mode="record")
    c.complete("q")
    c.complete("q")
    assert len(inner.calls) == 2


def test_auto_without_inner_on_miss_raises(tmp_path):
    with pytest.raises(CassetteMiss):
        CassetteLLM(tmp_path / "c.json").complete("q")


@pytest.mark.parametrize("text", ["", "{\"_backend\": \"scri", "[]"])
def test_corrupt_file_raises_a_clear_error(tmp_path, text):
    p = tmp_path / "c.json"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=r"corrupt cassette file: .*c\.json"):
        CassetteLLM(p)


def test_save_replaces_the_file_atomically(tmp_path, monkeypatch):
    replaced = []
    real_replace = os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        real_replace(src, dst)
    monkeypatch.setattr(os, "replace", spy)
    p = tmp_path / "c.json"
    CassetteLLM(p, inner=ScriptedLLM([(r".*", "X")])).complete("q")
    assert replaced == [(f"{p}.tmp", str(p))]
    assert not (tmp_path / "c.json.tmp").exists()
    assert json.loads(p.read_text(encoding="utf-8"))["_backend"] == "scripted"
