import pytest

from agent_urp.core.models import (
    Artifact,
    Block,
    Decision,
    Edit,
    Run,
    StepKind,
    StepRecord,
    WriteRef,
)
from agent_urp.core.trace_store import TraceStore


def _rec(run_id: str, seq: int, key: str = "k") -> StepRecord:
    return StepRecord(id=f"{run_id}:{seq:04d}", run_id=run_id, seq=seq, name="s", occurrence=0,
                      kind=StepKind.TOOL, key_static=key, code_version="c", input_hash=f"i{seq}",
                      writes=[WriteRef(kind="artifact", name="a", version="a")],
                      decision=Decision.LIVE)


def test_artifact_and_block_roundtrip():
    s = TraceStore()
    a = Artifact.of("text", {"x": [1, 2]})
    s.put_artifact(a)
    s.put_artifact(a)  # idempotent
    assert s.get_artifact(a.id) == a
    b = Block.of("goal", "go", durability="low")
    s.put_block(b)
    assert s.get_block("goal", b.version) == b
    with pytest.raises(KeyError):
        s.get_artifact("nope")


def test_env_snapshot_roundtrip():
    s = TraceStore()
    s.put_env_snapshot("kv", "v1", {"doc": "hi"})
    assert s.get_env_snapshot("kv", "v1") == {"doc": "hi"}


def test_run_edit_and_metrics():
    s = TraceStore()
    r = Run(id="r1", policy="full", initial_blocks={"goal": "v"})
    s.put_run(r)
    s.update_run_metrics("r1", {"steps": 3})
    assert s.get_run("r1").metrics == {"steps": 3}
    e = Edit.of("constraint", "goal", "block", "new")
    s.put_edit(e)
    assert s.get_edit(e.id) == e


def test_steps_ordered_by_seq_per_run():
    s = TraceStore()
    s.record_step(_rec("r1", 2))
    s.record_step(_rec("r1", 1))
    s.record_step(_rec("r2", 1))
    assert [x.seq for x in s.get_steps("r1")] == [1, 2]
    assert s.get_steps("nope") == []


def test_memo_candidates_newest_first_by_key():
    s = TraceStore()
    a, b, c = _rec("r1", 1, "k1"), _rec("r1", 2, "k1"), _rec("r1", 3, "k2")
    for x in (a, b, c):
        s.record_step(x)
        s.memo_put(x)
    assert [x.id for x in s.memo_candidates("k1")] == [b.id, a.id]
    assert s.memo_candidates("zzz") == []


def test_persists_to_file(tmp_path):
    p = tmp_path / "t.sqlite"
    s = TraceStore(p)
    s.put_artifact(Artifact.of("t", "x"))
    s.close()
    assert TraceStore(p).get_artifact(Artifact.of("t", "x").id).content == "x"
