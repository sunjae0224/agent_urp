from agent_urp.core.dep_graph import DepGraph
from agent_urp.core.models import Decision, ReadRef, StepKind, StepRecord, WriteRef


def _rec(seq, name, reads, writes):
    return StepRecord(id=f"r:{seq:04d}", run_id="r", seq=seq, name=name, occurrence=0,
                      kind=StepKind.TOOL, key_static=f"k{seq}", code_version="c",
                      input_hash=f"i{seq}", reads=reads, writes=writes, decision=Decision.LIVE)


def _graph():
    # 1 reads env → a1 ; 2 reads block budget + a1 → a2 ; 3 reads env → a3 ; 4 reads a2 + a3 → a4
    return DepGraph.from_steps([
        _rec(1, "flights", [ReadRef(kind="env", name="travel", version="e1")],
             [WriteRef(kind="artifact", name="a1", version="a1")]),
        _rec(2, "pick", [ReadRef(kind="block", name="budget", version="b1"),
                         ReadRef(kind="artifact", name="a1", version="a1")],
             [WriteRef(kind="artifact", name="a2", version="a2")]),
        _rec(3, "weather", [ReadRef(kind="env", name="travel", version="e1")],
             [WriteRef(kind="artifact", name="a3", version="a3")]),
        _rec(4, "plan", [ReadRef(kind="artifact", name="a2", version="a2"),
                         ReadRef(kind="artifact", name="a3", version="a3")],
             [WriteRef(kind="artifact", name="a4", version="a4")]),
    ])


def test_readers_and_first_dirty_seq():
    g = _graph()
    assert [r.name for r in g.readers_of("budget")] == ["pick"]
    assert [r.name for r in g.readers_of("travel")] == ["flights", "weather"]
    assert g.first_dirty_seq(["budget"]) == 2
    assert g.first_dirty_seq(["nobody"]) is None


def test_dirty_from_follows_artifacts():
    g = _graph()
    assert g.dirty_from(["budget"]) == {"r:0002", "r:0004"}
    assert g.dirty_from(["travel"]) == {"r:0001", "r:0002", "r:0003", "r:0004"}
    assert g.dirty_from(["nobody"]) == set()


def test_to_dot_mentions_steps():
    assert "pick" in _graph().to_dot()


def test_readers_of_sees_orchestration_reads():
    fetch = _rec(1, "fetch", [ReadRef(kind="env", name="kv", version="e1")],
                 [WriteRef(kind="artifact", name="a1", version="a1")])
    fetch = fetch.model_copy(update={
        "orchestration_reads": [ReadRef(kind="block", name="which", version="w1")]})
    use = _rec(2, "use", [ReadRef(kind="artifact", name="a1", version="a1")],
               [WriteRef(kind="artifact", name="a2", version="a2")])
    g = DepGraph.from_steps([fetch, use])
    assert [r.name for r in g.readers_of("which")] == ["fetch"]
    assert g.first_dirty_seq(["which"]) == 1
    assert g.dirty_from(["which"]) == {"r:0001", "r:0002"}
    assert g.g.has_edge("block:which@w1", "step:r:0001")
