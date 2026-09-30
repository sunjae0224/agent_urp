from enum import StrEnum

import pytest
from pydantic import BaseModel

from agent_urp.core.hashing import canonical_json, content_hash


class Color(StrEnum):
    RED = "red"


class M(BaseModel):
    b: int
    a: str


def test_canonical_json_sorts_keys_and_is_compact():
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'


def test_canonical_json_handles_models_enums_tuples_and_unicode():
    assert canonical_json(M(b=1, a="x")) == '{"a":"x","b":1}'
    assert canonical_json(Color.RED) == '"red"'
    assert canonical_json((1, 2)) == "[1,2]"
    assert canonical_json("한글") == '"한글"'


def test_content_hash_is_stable_and_32_hex():
    h1 = content_hash({"a": 1, "b": 2})
    h2 = content_hash({"b": 2, "a": 1})
    assert h1 == h2 and len(h1) == 32 and int(h1, 16) >= 0


def test_content_hash_differs_for_different_content():
    assert content_hash("a") != content_hash("b")


def test_content_hash_rejects_unserializable():
    with pytest.raises(TypeError):
        content_hash({1, 2})
    with pytest.raises(TypeError):
        content_hash(object())
