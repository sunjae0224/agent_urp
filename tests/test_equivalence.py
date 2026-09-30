from agent_urp.core.equivalence import Level, equivalent, normalize
from agent_urp.core.models import Artifact


def test_l0_is_identity_of_ids():
    a, b = Artifact.of("t", "x "), Artifact.of("t", "x")
    assert equivalent(a, Artifact.of("t", "x "), Level.L0)
    assert not equivalent(a, b, Level.L0)


def test_l1_normalizes_whitespace_and_numbers():
    assert normalize("  a   b \n c ") == "a b c"
    assert normalize({"k": 1, "j": [2.0, " x "]}) == {"j": [2.0, "x"], "k": 1.0}
    assert equivalent(Artifact.of("t", "a  b"), Artifact.of("t", "a b"), Level.L1)
    assert equivalent(Artifact.of("t", {"n": 1}), Artifact.of("t", {"n": 1.0}), Level.L1)
    assert not equivalent(Artifact.of("t", "a"), Artifact.of("t", "b"), Level.L1)


def test_l1_still_distinguishes_kinds():
    assert not equivalent(Artifact.of("t", "a"), Artifact.of("u", "a"), Level.L1)
