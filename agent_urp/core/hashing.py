"""Canonical JSON serialization and content-addressed hashing."""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        bad = [k for k in obj if not isinstance(k, str)]
        if bad:  # no silent str() coercion: {1: x} and {"1": x} must not hash the same
            raise TypeError(f"dict keys must be str, got {type(bad[0]).__name__} {bad[0]!r}")
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    raise TypeError(f"not JSON-serializable: {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    return json.dumps(_jsonable(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(obj: Any) -> str:
    data = canonical_json(obj).encode("utf-8")
    return hashlib.blake2b(data, digest_size=16).hexdigest()
