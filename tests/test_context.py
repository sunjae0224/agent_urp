from agent_urp.core.context import ContextAssembler, Prompt, render_block
from agent_urp.core.models import Block, Durability


def _blocks():
    return [
        Block.of("constraint.budget", "at most 2000 USD", durability=Durability.LOW),
        Block.of("system", "You plan trips.", durability=Durability.HIGH),
        Block.of("goal", {"city": "Jeju"}, durability=Durability.MEDIUM),
    ]


def test_render_block_str_and_json():
    assert render_block(Block.of("system", "hi")) == "[system]\nhi"
    assert render_block(Block.of("goal", {"b": 1, "a": 2})) == '[goal]\n{"a": 2, "b": 1}'


def test_naive_keeps_given_order_and_appends_extra():
    p = ContextAssembler("naive").assemble(_blocks(), extra="go")
    assert isinstance(p, Prompt)
    assert [n for n, _ in p.blocks] == ["constraint.budget", "system", "goal"]
    assert p.text.startswith("[constraint.budget]\nat most 2000 USD\n\n[system]")
    assert p.text.endswith("\n\n[input]\ngo")


def test_stable_prefix_sorts_by_durability_stably():
    p = ContextAssembler("stable_prefix").assemble(_blocks())
    assert [n for n, _ in p.blocks] == ["system", "goal", "constraint.budget"]
    assert "[input]" not in p.text


def test_unknown_layout_rejected():
    import pytest
    with pytest.raises(ValueError):
        ContextAssembler("weird")
