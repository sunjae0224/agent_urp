from agent_urp.tools.db import db_query
from agent_urp.tools.env import VersionedEnv
from agent_urp.tools.search import search


def test_env_version_tracks_content_and_paths():
    e = VersionedEnv("kv", {"a": {"b": 1}})
    v0 = e.version
    assert e.get("a.b") == 1 and e.get("a.zz", "d") == "d"
    e.set("a.c", 2)
    assert e.get("a") == {"b": 1, "c": 2} and e.version != v0
    e.update({"x.y": 3})
    assert e.get("x.y") == 3
    name, version, state = e.snapshot()
    state["a"]["b"] = 999  # snapshot is a copy
    assert e.get("a.b") == 1 and version == e.version
    assert VersionedEnv.restore(name, {"a": {"b": 1, "c": 2}, "x": {"y": 3}}).version == e.version


def test_same_state_same_version():
    assert VersionedEnv("a", {"k": 1}).version == VersionedEnv("b", {"k": 1}).version


def test_search_matches_words_case_insensitively():
    e = VersionedEnv("docs", {"docs": [
        {"id": "d1", "title": "Jeju beach guide", "text": "sunny beaches"},
        {"id": "d2", "title": "Busan", "text": "harbor and beach"},
        {"id": "d3", "title": "Seoul", "text": "palaces"},
    ]})
    hits = search(e, "BEACH jeju")
    assert [h["id"] for h in hits] == ["d1", "d2"]
    assert search(e, "nothing") == []
    assert search(e, "beach", limit=1) == [hits[0]]


def test_db_query_filters_rows():
    e = VersionedEnv("travel", {"tables": {"hotels": [
        {"city": "Jeju", "name": "A"},
        {"city": "Busan", "name": "B"},
        {"city": "Jeju", "name": "C"},
    ]}})
    assert [r["name"] for r in db_query(e, "hotels", {"city": "Jeju"})] == ["A", "C"]
    assert len(db_query(e, "hotels")) == 3
    assert db_query(e, "missing") == []
