from agent_urp.core.models import (
    Artifact,
    Block,
    BlockKind,
    Decision,
    Durability,
    Edit,
    ReadRef,
    Run,
    SamplingIntent,
    StepKind,
    StepRecord,
    Usage,
    WriteRef,
)


def test_artifact_id_is_content_addressed():
    a = Artifact.of("text", "hello")
    b = Artifact.of("text", "hello", created_by="run:0001")
    c = Artifact.of("json", "hello")
    assert a.id == b.id and a.id != c.id and len(a.id) == 32


def test_block_version_changes_with_content_only():
    b1 = Block.of("goal", {"city": "Jeju"}, kind=BlockKind.USER, durability=Durability.LOW)
    b2 = Block.of("goal", {"city": "Jeju"})
    b3 = Block.of("goal", {"city": "Busan"})
    assert b1.version == b2.version and b1.version != b3.version
    assert b1.durability is Durability.LOW and b2.durability is Durability.MEDIUM


def test_usage_addition():
    u = Usage(input_tokens=1, output_tokens=2) + Usage(
        input_tokens=3, cached_tokens=4, latency_ms=1.5
    )
    assert (u.input_tokens, u.output_tokens, u.cached_tokens, u.latency_ms) == (4, 2, 4, 1.5)


def test_step_record_roundtrip_json():
    rec = StepRecord(
        id="r:0001", run_id="r", seq=1, name="s", occurrence=0, kind=StepKind.LLM,
        key_static="k", reads=[ReadRef(kind="block", name="system", version="v1")],
        params={"args": {}}, code_version="c", input_hash="i",
        writes=[WriteRef(kind="artifact", name="a1", version="a1")], decision=Decision.LIVE,
    )
    again = StepRecord.model_validate_json(rec.model_dump_json())
    assert again == rec and again.sampling_intent is SamplingIntent.STABLE and again.llm_calls == 0


def test_edit_of_sets_id_and_defaults():
    e = Edit.of("constraint", "constraint.budget", "block", "Total budget: at most 1200 USD")
    assert e.target_kind == "block" and e.new_version is None and len(e.id) == 32


def test_run_defaults():
    r = Run(id="r1", policy="dep")
    assert r.parent_run_id is None and r.initial_blocks == {} and r.metrics == {}
