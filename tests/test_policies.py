from agent_urp.core.models import Decision, Policy, StepKind, StepRecord
from agent_urp.core.policies import choose_reuse


def _rec(seq, key="k", state="s"):
    return StepRecord(id=f"p:{seq:04d}", run_id="p", seq=seq, name="n", occurrence=0,
                      kind=StepKind.TOOL, key_static=key, code_version="c", input_hash=f"i{seq}",
                      decision=Decision.LIVE, params={"state_hash": state})


def _choose(policy, **kw):
    base = dict(key_static="k", old=None, first_dirty_seq=None, memo_candidates=[],
                verify=lambda r: True, state_hash="s")
    base.update(kw)
    return choose_reuse(policy, **base)


def test_full_never_reuses():
    assert _choose(Policy.FULL, old=_rec(1), memo_candidates=[_rec(1)]) is None


def test_suffix_reuses_by_position_only():
    old = _rec(2, key="different")
    assert _choose(Policy.SUFFIX, old=old, first_dirty_seq=3) is old
    assert _choose(Policy.SUFFIX, old=old, first_dirty_seq=2) is None
    assert _choose(Policy.SUFFIX, old=old, first_dirty_seq=None) is old
    assert _choose(Policy.SUFFIX, old=None, first_dirty_seq=None) is None


def test_memo_requires_exact_state_hash():
    a, b = _rec(1, state="other"), _rec(2, state="s")
    assert _choose(Policy.MEMO, memo_candidates=[a, b]) is b
    assert _choose(Policy.MEMO, memo_candidates=[a]) is None


def test_dep_prefers_verified_old_then_memo():
    old, other = _rec(1), _rec(5)
    assert _choose(Policy.DEP, old=old, memo_candidates=[other]) is old
    assert _choose(Policy.DEP, old=_rec(1, key="x"), memo_candidates=[other]) is other
    assert _choose(Policy.DEP, old=old, memo_candidates=[other], verify=lambda r: False) is None
